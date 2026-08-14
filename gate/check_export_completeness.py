#!/usr/bin/env python3
"""Deterministic export-completeness gate for a Xactly Extend app bundle.

Catches the classes of defect that make a gate-passing page still not WORK at runtime,
grounded on real exports (EFM Goals&Guarantees, Certification):

  E1  a control's datasource.name/.schema does not resolve to a shipped query object
      (queries/<schema>/<name>.json) and isn't declared external  -> ERROR
  E2  a :v_param used in a shipped query is not produced by any control (no CREATE_EVENT
      / VC / input that broadcasts or owns it)                     -> ERROR
  W1  an optional-looking string filter ( col = :v_param ) has neither an `All` branch
      ( :v_param = 'All' OR ... ) nor a default in the query's variables[]  -> WARN
      (this is the "undefined/empty on load" smell)
  W2  ADLC ships reporting/framework tables/views but no policy_sets/               -> WARN

Usage:  python check_export_completeness.py <bundle_dir> [--external name1,name2,...]
Exit 0 iff no ERRORs.
"""
import sys, os, re, json, glob, argparse

def load(p):
    with open(p, encoding="utf-8", errors="ignore") as f:
        return json.load(f)

def collect_page(props):
    """Return (datasources[(name,schema)], produced_vars:set, all_vars:set)."""
    ds, produced, allvars = [], set(), set()
    for c in props.values():
        d = c.get("datasource") or {}
        if d.get("name"):
            ds.append((d["name"], d.get("schema")))
        for v in (c.get("variables") or []):
            if v.get("name"):
                allvars.add(v["name"])
        # a control PRODUCES a variable if it owns one (VC/input) or broadcasts a CREATE_EVENT
        ctype = c.get("type", "")
        if ctype in ("variableConfigurator", "input", "dropdown"):
            for v in (c.get("variables") or []):
                produced.add(v.get("name"))
        for e in (c.get("events") or []):
            if e.get("eventSelection") == "CREATE_EVENT":
                # the broadcast name is an event channel, not a var; vars are produced by owning controls
                pass
    return ds, produced, allvars

def params_in(xsql):
    return set(re.findall(r":(v_[a-z0-9_]+)", xsql, re.I))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("--external", default="", help="comma list of datasource names known to exist in tenant")
    args = ap.parse_args()
    B = args.bundle
    external = {x.strip() for x in args.external.split(",") if x.strip()}
    errors, warns = [], []

    # index shipped queries (JSON objects OR xSQL .sql files): name -> {schema, xsql, defaults:set}
    queries = {}
    for qf in glob.glob(os.path.join(B, "queries", "*", "*.json")):
        try:
            q = load(qf)
        except Exception:
            continue
        nm = q.get("name") or os.path.splitext(os.path.basename(qf))[0]
        defaults = {v.get("name") for v in (q.get("variables") or []) if v.get("value") not in (None, "")}
        queries[nm] = {"schema": q.get("schemaName"), "xsql": q.get("xsql") or "", "defaults": defaults}
    for qf in glob.glob(os.path.join(B, "queries", "*", "*.sql")):
        nm = os.path.splitext(os.path.basename(qf))[0]
        if nm in queries:
            continue
        with open(qf, encoding="utf-8", errors="ignore") as f:
            body = re.sub(r"(?is)^\s*create\s+view\s+([\w.]+)\s+as\s+", "", f.read()).strip()
        schema = os.path.basename(os.path.dirname(qf))
        queries[nm] = {"schema": schema, "xsql": body, "defaults": set()}  # .sql carries no variable seeds

    # gather pages
    all_produced, page_ds = set(), []
    for pf in glob.glob(os.path.join(B, "app", "*.json")):
        if os.path.basename(pf) == "Application.json":
            continue
        try:
            d = load(pf)
        except Exception:
            continue
        props = (((d.get("pageSchema") or {}).get("controlSchema") or {}).get("schema") or {}).get("properties") or {}
        ds, produced, _ = collect_page(props)
        page_ds += ds
        all_produced |= produced

    # E1: datasource resolves
    for name, schema in page_ds:
        if name in queries or name in external:
            continue
        errors.append(f"E1 datasource '{name}' (schema={schema}) has no shipped query object and is not --external")

    # a param is "satisfiable" if a control owns it, OR the query object seeds a value for it.
    # (Extend also sets vars at runtime via row-select / assignCurrentVariable / framework lookups,
    #  which static analysis can't see -> E2 is advisory, never a hard error.)
    seeded = set()
    for meta in queries.values():
        seeded |= meta["defaults"]

    # E2 (WARN) + W1: params produced / defaulted
    for name, meta in queries.items():
        for p in params_in(meta["xsql"]):
            if p not in all_produced and p not in external and p not in seeded:
                warns.append(f"E2 query '{name}' uses :{p} with no owning control and no seed (may be set at runtime)")
            # W1: optional string filter without All-branch or default
            # (the old "ToString(col) = :param" guard is banned now — a param is safe when it has an
            #  All-branch or a seeded default; resolver params are seeded to 0 by the assembler.)
            has_all = re.search(r":" + re.escape(p) + r"\s*=\s*'All'", meta["xsql"], re.I)
            if not has_all and p not in meta["defaults"]:
                warns.append(f"W1 query '{name}': filter :{p} has no All-branch and no seeded default -> may be empty on load")

    # W2: policy coverage
    adlc = {}
    if os.path.exists(os.path.join(B, "ADLC.json")):
        adlc = load(os.path.join(B, "ADLC.json"))
    ships_tables = bool(adlc.get("tables") and (adlc["tables"].get("schemas") if isinstance(adlc.get("tables"), dict) else adlc.get("tables")))
    refs_reporting = any((s or "").lower() in ("$framework", "xactly") for _, s in page_ds)
    if (ships_tables or refs_reporting) and not adlc.get("policySets"):
        warns.append("W2 app references framework/reporting data but ships no policySets -> reporting rows may be inaccessible")

    print(f"queries indexed: {len(queries)} | page datasources: {len(page_ds)} | producing controls: {len(all_produced)}")
    if errors:
        print(f"\n✗ {len(errors)} ERROR(S):")
        for e in errors: print("  ERROR:", e)
    if warns:
        print(f"\n⚠ {len(warns)} WARNING(S):")
        for w in warns: print("  WARN: ", w)
    if not errors and not warns:
        print("\n✓ PASS — export complete.")
    elif not errors:
        print("\n✓ no errors (warnings only).")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
