#!/usr/bin/env python3
"""Build control_shapes.json: per control type, the key set real exports agree on.

Ground truth comes from genuine Xactly exports, never from our own output.
Required = keys present on EVERY real instance of that type. Known = union.
"""
import json, glob, os, sys, collections

TABLE_SOURCES = [
    "~/Downloads/EFM_Goals_Guarantees_extend/reference_existing_export/tables/schemas/*/*.json",
    "~/Documents/ExtendBuilderCertification_Raj/tables/schemas/*/*.json",
]

SOURCES = [
    "~/Downloads/EFM_Goals_Guarantees_extend/reference_existing_export/app/*.json",
    "~/Documents/Nokia/*.json",
    "~/Documents/ExtendBuilderCertification_Raj/app/*.json",
    "~/Documents/seller_dashboard_prod/seller_dashboard_page_main.json",
    "~/Documents/Incentive_Statement/incent_stmt_page.PROD.prebugfix.json",
    "~/Downloads/PayPalSalesCompensationHubTest-*/app/*.json",
]

def controls(o, out):
    if isinstance(o, dict):
        if "controlId" in o and isinstance(o.get("type"), str):
            out.append(o)
        for v in o.values(): controls(v, out)
    elif isinstance(o, list):
        for v in o: controls(v, out)

def main():
    per = collections.defaultdict(list)
    files = 0
    for pat in SOURCES:
        for f in glob.glob(os.path.expanduser(pat)):
            if os.path.basename(f) == "Application.json": continue
            try: j = json.load(open(f))
            except Exception: continue
            found = []; controls(j, found)
            if found: files += 1
            for c in found: per[c["type"]].append(set(c.keys()))
    cat = {}
    for t, keysets in sorted(per.items()):
        req = set.intersection(*keysets)
        known = set.union(*keysets)
        cat[t] = {"instances": len(keysets), "required": sorted(req), "known": sorted(known)}
    # table schemas: key set + the column dataTypes the platform actually accepts
    tbl_keysets, coltypes, colkeys, tfiles = [], set(), [], 0
    for pat in TABLE_SOURCES:
        for f in glob.glob(os.path.expanduser(pat)):
            try: j = json.load(open(f))
            except Exception: continue
            if not j.get("tableName"): continue
            tfiles += 1
            # source-bound Incent mirrors carry `using` and no real columns
            if j.get("using"): continue
            tbl_keysets.append(set(j.keys()))
            for c in j.get("columns") or []:
                coltypes.add(c.get("dataType", {}).get("type"))
                colkeys.append(set(c.keys()))
    tables = {"instances": len(tbl_keysets),
              "required": sorted(set.intersection(*tbl_keysets)) if tbl_keysets else [],
              "known": sorted(set.union(*tbl_keysets)) if tbl_keysets else [],
              "column_required": sorted(set.intersection(*colkeys)) if colkeys else [],
              "column_types": sorted(t for t in coltypes if t)}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "control_shapes.json")
    json.dump({"_source_files": files, "types": cat, "table_schema": tables},
              open(out, "w"), indent=2)
    print(f"table schemas: {tables['instances']} real | column types: {tables['column_types']}")
    print(f"{files} real export files | {len(cat)} control types")
    for t, m in sorted(cat.items(), key=lambda x: -x[1]["instances"])[:12]:
        print(f"  {t:22} n={m['instances']:4}  required={len(m['required']):2}  known={len(m['known'])}")
    print("wrote", out)

if __name__ == "__main__":
    main()
