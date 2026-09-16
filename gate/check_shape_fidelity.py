#!/usr/bin/env python3
"""check_shape_fidelity.py — does each control carry the keys the platform expects?

The other gates check wiring, behaviour and import. None of them notice a control
that is well-formed, correctly wired, and simply MISSING A KEY the renderer needs.
That is how the Seller Dashboard shipped a tabContainer with four tabs that
rendered nothing: every `tab` was missing
`innerCanvasMappings: {"pageSchema": "appElements"}`, and all four gates passed.

Ground truth is `control_shapes.json`, built by build_shape_catalog.py from 16
genuine Xactly export files - never from our own output.

  F1  a control omits a key present on EVERY real instance of its type -> ERROR
  F2  a control carries a key seen on NO real instance of its type     -> WARN
      (invented field, or a genuinely new platform key - check before trusting)
  F3  the control type does not appear in any real export              -> WARN
  F4  a table schema omits a key every real table schema carries       -> ERROR
  F5  a column declares a dataType no real schema uses                 -> ERROR
  F6  a control references fields but declares no datasource           -> ERROR
  F7  a control binds a field its datasource query does not return     -> ERROR
      (the chart bound q1_y..q4_y after the view stopped returning them)
  F8  a data-bound table/Custom declares no component variables (R18)  -> ERROR
      Seller Dashboard v3.5 declared 35 columns as "NUMBER"; the real type is
      DECIMAL and NUMBER is not a Xactly type, so the $framework tables were
      never created and every runner failed silently.

Usage:  python check_shape_fidelity.py <bundle_dir | page.json> [--catalog PATH]
Exit 0 iff no ERRORs.
"""
import sys, os, re, json, glob, argparse, collections

ERRORS, WARNS = [], []

# Keys that legitimately vary per instance and must never be demanded.
# R18: chart/composedChart have NO variables key at all - demanding one produces
# invalid JSON. accessRoles/privileges are frequently null-and-omitted.
IGNORE = {"seriesColors", "intl"}
PER_TYPE_EXEMPT = {
    "chart": {"variables"}, "composedChart": {"variables"},
}
# Keys that only make sense on a control that HAS a datasource. Real exports
# happen to be datasource-heavy, so a naive intersection demands these of every
# header Custom and every static-value VC, which is wrong. Requiring them only
# when a datasource is present keeps the check that matters - R18: a data-bound
# control that ships columns[] but no variables[] renders with every Component
# Variable box empty.
DATASOURCE_COMPANIONS = {"datasource", "columns", "pagination",
                         "whereClauseVariable", "valueField", "variables"}

def controls(o, out, path="root"):
    if isinstance(o, dict):
        if "controlId" in o and isinstance(o.get("type"), str):
            out.append((path, o))
        for k, v in o.items(): controls(v, out, path)
    elif isinstance(o, list):
        for v in o: controls(v, out, path)

def check_page(page, label, cat):
    found = []
    controls(page, found, label)
    for _, c in found:
        t = c["type"]
        meta = cat.get(t)
        name = c.get("internalName") or c.get("title") or c.get("controlData") or c["controlId"][:8]
        if not meta:
            WARNS.append(f"F3 {label}: control type {t!r} appears in no real export - shape unverified")
            continue
        exempt = PER_TYPE_EXEMPT.get(t, set()) | IGNORE
        # Controls that legitimately render without data (headers, labels,
        # loaders, buttons) are excused the datasource companions. A
        # variableConfigurator is NOT: all 186 real instances carry a datasource
        # and a valueField, and a static-value VC appears in no real export - so
        # a seed must be a one-row view, the way production seeds its pills.
        if not (c.get("datasource") or {}).get("name") and t != "variableConfigurator":
            exempt |= DATASOURCE_COMPANIONS
        missing = sorted(set(meta["required"]) - set(c) - exempt)
        if missing:
            ERRORS.append(f"F1 {label}: {t} {str(name)[:34]!r} is missing {missing} - present on all "
                          f"{meta['instances']} real instances of this type")
        unknown = sorted(set(c) - set(meta["known"]) - IGNORE)
        if unknown:
            WARNS.append(f"F2 {label}: {t} {str(name)[:34]!r} carries {unknown}, seen on none of the "
                         f"{meta['instances']} real instances")

# assigned by the platform at table creation - externalTableName embeds the
# tenant's business id (biz_1223 / biz_14259 differ per tenant) and the suffix is
# generated, so a bundle cannot supply either
PLATFORM_ASSIGNED = {"externalTableName", "externalTableSuffix"}


def check_tables(bundle_dir, cat):
    meta = cat.get("table_schema")
    if not meta: return
    for f in glob.glob(os.path.join(bundle_dir, "tables", "schemas", "*", "*.json")):
        try: j = json.load(open(f))
        except Exception: continue
        rel = os.path.relpath(f, bundle_dir)
        if j.get("using"):        # Incent source mirror, not a real table
            continue
        missing = sorted(set(meta["required"]) - set(j) - PLATFORM_ASSIGNED)
        if missing:
            ERRORS.append(f"F4 {rel}: table schema is missing {missing} - present on all "
                          f"{meta['instances']} real table schemas")
        for c in j.get("columns") or []:
            t = (c.get("dataType") or {}).get("type")
            if t not in meta["column_types"]:
                ERRORS.append(f"F5 {rel}: column {c.get('name')!r} declares dataType {t!r}; "
                              f"real schemas only use {meta['column_types']}")


def outer_aliases(sql):
    """Columns a view actually returns: the top-level SELECT alias list."""
    up = sql.upper(); i = up.find("SELECT")
    if i < 0: return set()
    d, start, end = 0, i + 6, len(sql)
    for j in range(start, len(sql)):
        ch = sql[j]
        if ch == "(": d += 1
        elif ch == ")": d -= 1
        elif d == 0 and re.match(r"(?i)\s*\bFROM\b", sql[j:j + 6]) and sql[j - 1] in " \n\t":
            end = j; break
    parts, d, cur = [], 0, ""
    for ch in sql[start:end]:
        if ch == "(": d += 1
        elif ch == ")": d -= 1
        if ch == "," and d == 0: parts.append(cur); cur = ""
        else: cur += ch
    parts.append(cur)
    out = set()
    for p in parts:
        p = " ".join(p.split())
        m = re.search(r"(?i)\bAS\s+([A-Za-z_]\w*)\s*$", p)
        if m: out.add(m.group(1).lower())
        elif p: out.add(p.split()[-1].split(".")[-1].lower())
    return out


def check_bindings(bundle_dir):
    """F6/F7/F8 - does every field a control names actually come back?"""
    Q = {}
    for f in glob.glob(os.path.join(bundle_dir, "queries", "*", "*.json")):
        try: j = json.load(open(f))
        except Exception: continue
        if j.get("name"): Q[j["name"]] = outer_aliases(j.get("xsql") or "")
    for pg in glob.glob(os.path.join(bundle_dir, "app", "*.json")):
        if os.path.basename(pg) == "Application.json": continue
        found = []; controls(json.load(open(pg)), found, os.path.basename(pg)[:12])
        for label, c in found:
            t = c.get("type"); nm = c.get("internalName") or c.get("controlData") or c["controlId"][:8]
            ds = (c.get("datasource") or {}).get("name")
            fields = {v.get("boundToField") for v in (c.get("variables") or [])}
            fields |= {x.get("field") for x in (c.get("columns") or [])}
            fields |= {(c.get("valueField") or {}).get("name"),
                       (c.get("displayField") or {}).get("name")}
            fields = {f for f in fields if f}
            if fields and not ds:
                ERRORS.append(f"F6 {label}: {t} {str(nm)[:34]!r} references {sorted(fields)[:4]} "
                              f"but declares no datasource")
                continue
            if not ds or ds not in Q: continue
            have = Q[ds]
            for fld in sorted(fields):
                if fld.lower() not in have:
                    ERRORS.append(f"F7 {label}: {t} {str(nm)[:34]!r} binds {fld!r}, which {ds} "
                                  f"does not return")
            if t in ("table", "Custom") and not (c.get("variables") or []):
                ERRORS.append(f"F8 {label}: {t} {str(nm)[:34]!r} is bound to {ds} but declares no "
                              f"component variables (R18)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--catalog", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                      "control_shapes.json"))
    a = ap.parse_args()
    cat = json.load(open(a.catalog))["types"]
    pages = ([p for p in glob.glob(os.path.join(a.target, "app", "*.json"))
              if os.path.basename(p) != "Application.json"]
             if os.path.isdir(a.target) else [a.target])
    for p in sorted(pages):
        check_page(json.load(open(p)), os.path.basename(p)[:12], cat)
    if os.path.isdir(a.target):
        check_tables(a.target, json.load(open(a.catalog)))
        check_bindings(a.target)
    print(f"catalog: {len(cat)} types | pages checked: {len(pages)}")
    for w in WARNS: print(f"  WARN : {w}")
    if ERRORS:
        print(f"\n✗ {len(ERRORS)} ERROR(S):")
        for e in ERRORS: print(f"  ERROR: {e}")
        print("\n✗ FAIL - controls do not match the shapes real exports use.")
        return 1
    print(f"\n✓ PASS - control shapes match real exports" + (f" ({len(WARNS)} warning(s))." if WARNS else "."))
    return 0

if __name__ == "__main__":
    sys.exit(main())
