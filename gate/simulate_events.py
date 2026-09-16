#!/usr/bin/env python3
"""simulate_events.py — run the page's event graph and report what breaks.

The other gates ask "is this well-formed?". This one asks "what actually happens
when the page loads?" It replays the load path and reports, per control, which
of its parameters are still unbound at the moment it fires.

Every rule is a defect class observed on shipped pages (Seller Dashboard v3.0-v3.2,
ClaimRequest), each of which passed every other gate:

  S1  a control fires while a :v_param its datasource/xSQL needs is still unbound
      -> ERROR   (the "undefined tiles / empty on load" class)
  S2  a control BINDs a channel no control CREATEs                     -> ERROR
  S3  a channel has more than one producer (ambiguous ordering)        -> ERROR
      ...unless every producer is a variableConfigurator, which is the pill
      idiom: one VC per choice, each owning the same variable, exactly one
      firing per click. Verified in ~/Documents/seller_dashboard_prod.  -> WARN
  S4  a channel is CREATEd and nothing binds it (dead wiring)          -> WARN
  S5  a data control is unreachable on the load path and has no user
      trigger - it will never populate                                 -> WARN
  S6  the PageLoader's hideLoader is gated behind an xSQLRunner chain
      -> ERROR   (Seller Dashboard v3.2: any slow or failing DML left a
                  full-screen spinner forever. Hide on shell readiness.)
  S7  a :v_param is used somewhere but produced by no control          -> ERROR
  S8  a control binds a datasource that is not shipped as a query and is
      not declared external -> ERROR   (the control renders permanently empty)
  S9  a query is shipped, no control binds it, AND no other query selects
      from it -> WARN. A base view joined by other views is not orphaned -
      production's seller_measure_map is joined 12 times and bound to nothing.
  S10 an optional-looking filter ( col = :v_param ) has neither an 'All'
      branch nor a seeded default -> WARN   (the "empty on load" smell)
  S11 the app ships tables or reads framework/xactly data but declares no
      policySets -> WARN   (reporting rows may be inaccessible)

A param counts as satisfied if a control owns it OR the query object seeds a
value for it in variables[] - Extend also sets variables at runtime in ways
static analysis cannot see, so seeds are honoured rather than flagged.

BROADCAST SEMANTICS (confirmed against a live tenant 2026-09-05 - getting this
wrong produces a flood of false positives):
  * a dropdown/input broadcasts its CREATE channel ONLY on a user selection,
    never on a refresh - so its channel cannot fire during load;
  * $onTabOpen is likewise a user action and cannot precede load;
  * a variableConfigurator with a static value bound to $onPageLoad DOES
    broadcast at load. That asymmetry is the whole game.

Usage:  python simulate_events.py <bundle_dir | page.json> [--queries DIR] [--trace]
Exit 0 iff no ERRORs.
"""
import sys, os, re, json, glob, argparse, collections

LOAD_EVENT = "$onPageLoad"
USER_EVENTS = {"$onTabOpen", "$onComponentSeen", "$onModalOpen"}
SYSTEM_EVENTS = {LOAD_EVENT} | USER_EVENTS
# controls whose CREATE channel is a user gesture, not a load-time broadcast
USER_DRIVEN = {"dropdown", "input", "date", "dateTime", "checkbox", "radioButton",
               "actionDropdown", "button", "workflowButton", "xSQLButton"}
DATA_TYPES = {"table", "chart", "composedChart", "tile", "Custom", "pivot-table",
              "gridSummary", "list", "gauge_chart", "mosaic", "sheet"}

ERRORS, WARNS, TRACE = [], [], []
# datasource name -> [(page, control)] across every page in the bundle. S9 has to
# be judged over the WHOLE bundle: a query bound on page 3 is not orphaned just
# because page 1 does not use it.
USED_DS = collections.defaultdict(list)
DS_SCHEMAS = set()


def collect_controls(page):
    """Every control, including tab children. Walking only the top-level
    properties map misses nested controls entirely - that mistake understated a
    real audit by 7 controls."""
    out = {}
    def walk(o):
        if isinstance(o, dict):
            if "controlId" in o and "type" in o:
                name = o.get("internalName") or o.get("title") or str(o["controlId"])[:8]
                out[o["controlId"]] = (name, o)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(page)
    return out


def load_queries(qdir):
    """name -> {params, defaults, xsql}. Handles both bundle shapes (.json, .sql).

    `defaults` are params the query object seeds a value for in variables[] - a
    seeded param is satisfiable without any control owning it.
    """
    q = {}
    if not qdir or not os.path.isdir(qdir): return q
    for f in glob.glob(os.path.join(qdir, "**", "*.json"), recursive=True):
        try: j = json.load(open(f))
        except Exception: continue
        if "xsql" in j and j.get("name"):
            body = j["xsql"] or ""
            q[j["name"]] = {"params": set(re.findall(r":(v_\w+)", body)),
                            "defaults": {v.get("name") for v in (j.get("variables") or [])
                                         if v.get("name") and v.get("value") is not None},
                            "xsql": body}
    for f in glob.glob(os.path.join(qdir, "**", "*.sql"), recursive=True):
        body = open(f, encoding="utf-8", errors="ignore").read()
        m = re.search(r"(?is)create\s+(?:or\s+replace\s+)?view\s+[\w$]+\.(\w+)", body)
        if m and m.group(1) not in q:
            # a .sql view carries no variable seeds
            q[m.group(1)] = {"params": set(re.findall(r":(v_\w+)", body)),
                             "defaults": set(), "xsql": body}
    return q


def params_needed(ctrl, queries):
    ps = set()
    if ctrl.get("type") == "xSQLRunner":
        ps |= set(re.findall(r":(v_\w+)", ctrl.get("xSQL") or ""))
    ds = (ctrl.get("datasource") or {}).get("name")
    if ds: ps |= (queries.get(ds) or {}).get("params", set())
    return ps


def simulate(page, queries, want_trace=False, page_label=""):
    ctrls = collect_controls(page)
    binds, creates = collections.defaultdict(set), collections.defaultdict(set)
    for cid, (_, c) in ctrls.items():
        for e in c.get("events") or []:
            (binds if e.get("eventSelection") == "BIND_EVENT" else creates)[cid].add(e.get("name"))
        # a Custom fires channels from its markup: data-xactly-event="chan".
        # Production pages do not mirror these in events[], so read the HTML or
        # every consumer of a pick channel looks like an orphan BIND.
        for chan in re.findall(r'data-xactly-event="([^"]+)"', c.get("controlData") or ""):
            creates[cid].add(chan)

    producers = collections.defaultdict(list)
    for cid, chans in creates.items():
        for ch in chans: producers[ch].append(cid)
    consumers = collections.defaultdict(list)
    for cid, chans in binds.items():
        for ch in chans: consumers[ch].append(cid)

    for ch, who in sorted(consumers.items()):
        if ch not in producers and ch not in SYSTEM_EVENTS:
            ERRORS.append(f"S2 channel '{ch}' is bound by {len(who)} control(s) but no control creates it "
                          f"(e.g. {ctrls[who[0]][0]!r})")
    for ch, who in sorted(producers.items()):
        if len(who) > 1:
            all_vc = all(ctrls[c][1].get("type") == "variableConfigurator" for c in who)
            msg = (f"S3 channel '{ch}' has {len(who)} producers "
                   f"({[ctrls[c][0] for c in who]})")
            if all_vc:
                WARNS.append(msg + " - fine if this is the pill idiom (one VC per "
                                   "choice, exactly one firing per click)")
            else:
                ERRORS.append(msg + " - firing order is undefined")
        if ch not in consumers:
            WARNS.append(f"S4 channel '{ch}' is created by {ctrls[who[0]][0]!r} but nothing binds it")

    # --- replay the load path -------------------------------------------------
    # only non-user-driven controls broadcast during load
    html_chans = {cid: set(re.findall(r'data-xactly-event="([^"]+)"',
                                      ctrls[cid][1].get("controlData") or ""))
                  for cid in ctrls}
    # a click channel cannot fire during load, whatever control carries it
    load_creates = {cid: (set() if ctrls[cid][1].get("type") in USER_DRIVEN
                          else ch - html_chans.get(cid, set()))
                    for cid, ch in creates.items()}
    round_of = {cid: 0 for cid in ctrls if binds[cid] & {LOAD_EVENT}}
    changed = True
    while changed:
        changed = False
        live = {ch for cid in round_of for ch in load_creates.get(cid, set())} | {LOAD_EVENT}
        nxt = max(round_of.values()) + 1 if round_of else 0
        for cid in ctrls:
            if cid not in round_of and binds[cid] & live:
                round_of[cid] = nxt; changed = True

    var_round = {}
    for cid, (_, c) in ctrls.items():
        if cid in round_of:
            for v in c.get("variables") or []:
                if v.get("name"):
                    var_round[v["name"]] = min(var_round.get(v["name"], 10**6), round_of[cid])

    for cid, (nm, c) in ctrls.items():
        dsrc = c.get("datasource") or {}
        if dsrc.get("name"):
            USED_DS[dsrc["name"]].append((page_label, nm))
            DS_SCHEMAS.add(dsrc.get("schema"))

    all_produced = {v["name"] for _, c in ctrls.values() for v in (c.get("variables") or []) if v.get("name")}
    used = set()
    for cid, (_, c) in ctrls.items(): used |= params_needed(c, queries)
    seeded = set()
    for meta in queries.values(): seeded |= meta.get("defaults", set())
    for v in sorted(used - all_produced - seeded):
        ERRORS.append(f"S7 :{v} is used but no control produces it and no query seeds it")

    for cid, (nm, c) in sorted(ctrls.items(), key=lambda x: round_of.get(x[0], 10**6)):
        if cid not in round_of: continue
        need = params_needed(c, queries)
        late = sorted(p for p in need if var_round.get(p, 10**6) >= round_of[cid])
        if want_trace:
            TRACE.append(f"  r{round_of[cid]:<3} {nm[:44]:44} {c.get('type','')[:16]:16} "
                         f"needs={len(need)} unbound={late if late else '-'}")
        if late:
            ERRORS.append(f"S1 {nm!r} ({c.get('type')}) fires at round {round_of[cid]} with "
                          f"{len(late)} unbound parameter(s): {late}")

    for cid, (nm, c) in ctrls.items():
        if cid in round_of or c.get("type") not in DATA_TYPES: continue
        if not (binds[cid] & USER_EVENTS) and not binds[cid]:
            continue  # purely static (header/label) - fine
        if not (binds[cid] & USER_EVENTS):
            WARNS.append(f"S5 {nm!r} ({c.get('type')}) is never reached on the load path "
                         f"and has no user trigger - it will not populate")

    # --- S6: is the loader gated behind DML? ----------------------------------
    for cid, (nm, c) in ctrls.items():
        if c.get("type") != "PageLoader": continue
        hide = {e["name"] for e in (c.get("events") or [])
                if e.get("eventSelection") == "BIND_EVENT" and "hideLoader" in (e.get("handlers") or [])}
        safe = []
        for ch in hide:
            seen, stack, via_dml = set(), list(producers.get(ch, [])), False
            while stack:
                p = stack.pop()
                if p in seen: continue
                seen.add(p)
                if ctrls[p][1].get("type") == "xSQLRunner": via_dml = True; break
                for up in binds.get(p, set()):
                    stack.extend(producers.get(up, []))
            if not via_dml: safe.append(ch)
        if hide and not safe:
            ERRORS.append(
                f"S6 {nm!r} only hides on {sorted(hide)}, and every one of those is produced "
                f"downstream of an xSQLRunner. A slow or failing DML statement leaves a "
                f"full-screen loader forever. Hide on shell readiness (identity/period bound, "
                f"no DML) and let data controls carry their own wait.")
    return ctrls, round_of


def check_datasources(queries, external=()):
    """S8/S9 - run ONCE over the whole bundle, after every page is walked.

    S8 is a hard runtime failure: a control whose datasource does not resolve
    renders empty forever, and no page-level gate notices. S9 is drift - three
    orphaned queries had to be found by hand on Seller Dashboard v3.4 before
    this existed.
    """
    external = {e.strip() for e in external if e and e.strip()}
    for ds in sorted(USED_DS):
        if ds not in queries and ds not in external:
            where = USED_DS[ds][0]
            ERRORS.append(f"S8 datasource {ds!r} is bound by {len(USED_DS[ds])} control(s) "
                          f"(e.g. {where[1]!r} on {where[0]}) but no query of that name ships "
                          f"in the bundle - the control will render empty. Declare it with "
                          f"--external if it already exists in the tenant.")
    joined = set()
    for name, meta in queries.items():
        for other in queries:
            if other != name and re.search(r"(?i)\b(from|join)\s+[\w$]*\.?%s\b" % re.escape(other),
                                           meta.get("xsql", "")):
                joined.add(other)
    for q in sorted(queries):
        if q not in USED_DS and q not in joined:
            WARNS.append(f"S9 query {q!r} ships in the bundle but no control binds it "
                         f"and no other query selects from it")


def check_query_hygiene(queries):
    """S10 - a filter with neither an All-branch nor a seeded default renders
    empty until the user touches something. Folded in from the retired
    check_export_completeness.py (W1)."""
    for name, meta in sorted(queries.items()):
        for p in sorted(meta.get("params", set())):
            # the bypass idiom is an OR'd equality against ANY literal sentinel, not just the word All
            bypass = re.search(r":" + re.escape(p) + r"\s*=\s*'[^']*'", meta.get("xsql", ""), re.I)
            if not bypass and p not in meta.get("defaults", set()):
                WARNS.append(f"S10 query {name!r}: filter :{p} has no All-branch and no seeded "
                             f"default - may be empty on load")


def check_policy_coverage(bundle_dir, ds_schemas):
    """S11 - framework/reporting data with no policy sets is often unreadable for
    the very roles the app targets. Folded in from check_export_completeness.py (W2)."""
    adlc_p = os.path.join(bundle_dir, "ADLC.json")
    if not os.path.exists(adlc_p): return
    try: adlc = json.load(open(adlc_p))
    except Exception: return
    tables = adlc.get("tables") or {}
    ships_tables = bool(tables.get("schemas") if isinstance(tables, dict) else tables)
    refs_reporting = any((s or "").lower() in ("$framework", "xactly") for s in ds_schemas)
    if (ships_tables or refs_reporting) and not adlc.get("policySets"):
        WARNS.append("S11 app ships tables or reads framework/xactly data but declares no "
                     "policySets - reporting rows may be inaccessible to the target roles")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="bundle dir or a single page .json")
    ap.add_argument("--queries", default=None)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--external", default="",
                    help="comma-separated datasources that live in the tenant, not the bundle")
    a = ap.parse_args()

    if os.path.isdir(a.target):
        pages = sorted(p for p in glob.glob(os.path.join(a.target, "app", "*.json"))
                       if os.path.basename(p) != "Application.json")
        qdir = a.queries or os.path.join(a.target, "queries")
    else:
        pages, qdir = [a.target], a.queries
    queries = load_queries(qdir)

    for p in pages:
        del TRACE[:]
        page = json.load(open(p))
        print(f"--- {os.path.basename(p)}")
        ctrls, ro = simulate(page, queries, a.trace, os.path.basename(p))
        print(f"    {len(ctrls)} controls (incl. nested) | {len(ro)} reached on load | "
              f"{len(queries)} queries indexed")
        if a.trace:
            for t in TRACE: print(t)

    if os.path.isdir(a.target) or a.queries:
        check_datasources(queries, a.external.split(","))
        check_query_hygiene(queries)
    if os.path.isdir(a.target):
        check_policy_coverage(a.target, DS_SCHEMAS)
    for w in WARNS: print(f"  WARN : {w}")
    if ERRORS:
        print(f"\n✗ {len(ERRORS)} ERROR(S):")
        for e in ERRORS: print(f"  ERROR: {e}")
        print("\n✗ FAIL - the page does not behave correctly on load.")
        return 1
    print(f"\n✓ PASS - load path is sound" + (f" ({len(WARNS)} warning(s))." if WARNS else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
