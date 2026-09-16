#!/usr/bin/env python3
"""check_gold_shape.py — does a page match a gold shape_manifest for its app class?

Used to keep the builder from drifting away from the finalized seller/comp dashboard
patterns while still allowing non-comp apps to skip the check.

Usage:
  python gate/check_gold_shape.py <page.json> --manifest evals/golden/comp_dashboard/shape_manifest.json
  python gate/check_gold_shape.py <bundle_dir> --manifest ...

Exit 0 iff no ERRORs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ERRORS, WARNS = [], []


def walk_controls(obj, out=None):
    out = out if out is not None else []
    if isinstance(obj, dict):
        if isinstance(obj.get("type"), str) and "controlId" in obj:
            out.append(obj)
        for v in obj.values():
            walk_controls(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_controls(v, out)
    return out


def all_events(controls):
    creates, binds = set(), set()
    for c in controls:
        for e in c.get("events") or []:
            name = e.get("name") or ""
            sel = e.get("eventSelection")
            if sel == "CREATE_EVENT":
                creates.add(name)
            elif sel == "BIND_EVENT":
                binds.add(name)
    return creates, binds


def owned_vars(controls):
    names = set()
    for c in controls:
        for v in c.get("variables") or []:
            if isinstance(v, dict) and v.get("name") and not v.get("boundToField"):
                names.add(v["name"])
    return names


def load_page(path):
    if os.path.isdir(path):
        app = os.path.join(path, "app")
        pages = []
        if os.path.isdir(app):
            for fn in os.listdir(app):
                if fn.endswith(".json") and fn != "Application.json":
                    with open(os.path.join(app, fn), encoding="utf-8") as f:
                        pages.append(json.load(f))
        if not pages:
            raise SystemExit(f"no page JSON under {path}/app")
        return pages
    with open(path, encoding="utf-8") as f:
        return [json.load(f)]


def check_page(page, manifest, label="page"):
    controls = walk_controls(page)
    types = {c.get("type") for c in controls}
    creates, binds = all_events(controls)
    vars_owned = owned_vars(controls)

    for t in manifest.get("required_types") or []:
        if t not in types:
            ERRORS.append(f"G1 {label}: missing required control type {t!r}")

    for ev in manifest.get("required_create_events") or []:
        if ev not in creates:
            ERRORS.append(f"G2 {label}: missing CREATE_EVENT {ev!r} (bootstrap / gate spine)")

    # PageLoader hide on data_ready
    loaders = [c for c in controls if c.get("type") == "PageLoader"]
    if loaders:
        hide_ok = False
        for L in loaders:
            for e in L.get("events") or []:
                if e.get("name") == "data_ready" and "hideLoader" in (e.get("handlers") or []):
                    hide_ok = True
        if not hide_ok:
            ERRORS.append(f"G3 {label}: PageLoader must BIND data_ready → hideLoader (gold spine)")

    # seeds
    for pat in manifest.get("required_patterns") or []:
        if pat.get("id") == "seed_vars":
            need = set(pat.get("owned_vars_any") or [])
            if need and not (need & vars_owned):
                ERRORS.append(f"G4 {label}: expected seed vars among {sorted(need)}; owned={sorted(vars_owned)}")
        if pat.get("id") == "team_gate":
            for ev in pat.get("events") or []:
                if ev not in creates:
                    ERRORS.append(f"G5 {label}: team gate missing CREATE {ev!r}")
            hidden = [c for c in controls if c.get("shouldRenderHidden") is True]
            if not hidden:
                ERRORS.append(f"G5 {label}: team section needs shouldRenderHidden:true targets")
        if pat.get("id") == "tables_have_maxHeight":
            tables = [c for c in controls if c.get("type") == "table"]
            with_h = [c for c in tables if c.get("maxHeight")]
            if tables and not with_h:
                ERRORS.append(f"G6 {label}: every/comp tables need maxHeight (R10)")
            elif tables and len(with_h) < pat.get("min_tables_with_maxHeight", 1):
                ERRORS.append(f"G6 {label}: need ≥{pat.get('min_tables_with_maxHeight')} tables with maxHeight")
        if pat.get("id") == "blank_table_titles":
            for c in controls:
                if c.get("type") == "table" and (c.get("title") or "").strip():
                    # warn only — some apps title tables; gold prefers empty when header Custom exists
                    WARNS.append(f"G7 {label}: table {c.get('internalName')!r} has non-empty title "
                                 f"{c.get('title')!r} — gold prefers title '' under a header Custom")
        if pat.get("id") == "tab_onTabOpen":
            # any control nested under a tab type that has datasource must bind $onTabOpen
            tabs = [c for c in controls if c.get("type") == "tab"]
            for tab in tabs:
                nested = walk_controls(tab)
                for c in nested:
                    if c is tab:
                        continue
                    if (c.get("datasource") or {}).get("name"):
                        ev_names = {e.get("name") for e in (c.get("events") or [])}
                        if "$onTabOpen" not in ev_names:
                            ERRORS.append(
                                f"G8 {label}: tab child {c.get('internalName') or c.get('type')!r} "
                                f"missing $onTabOpen bind"
                            )
        if pat.get("id") == "export_pdf_wired":
            if "exportPagePDF" not in types:
                ERRORS.append(f"G9 {label}: missing exportPagePDF")
            if "button" not in types:
                ERRORS.append(f"G9 {label}: missing download button")
        if pat.get("id") == "supp_or_matrix_customs":
            ds_customs = [c for c in controls
                          if c.get("type") == "Custom" and (c.get("datasource") or {}).get("name")]
            need = pat.get("min_datasource_customs", 3)
            if len(ds_customs) < need:
                ERRORS.append(f"G10 {label}: need ≥{need} datasource-bound Customs "
                              f"(matrix / profile / supp); found {len(ds_customs)}")

    # layoutSize 25 row existence (supp cards) — soft
    twenty_fives = [c for c in controls if c.get("layoutSize") in (25, "25", 25.0)]
    if len(twenty_fives) < 4:
        WARNS.append(f"G11 {label}: gold has 4× layoutSize 25 supplemental cards; found {len(twenty_fives)}")


def check_views_sql(paths, manifest):
    forbid = manifest.get("forbidden_xsql_substrings") or []
    if not forbid or not paths:
        return
    for p in paths:
        if not os.path.isfile(p):
            continue
        text = open(p, encoding="utf-8", errors="ignore").read()
        for frag in forbid:
            if frag in text:
                ERRORS.append(f"G12 views: forbidden {frag!r} in {os.path.basename(p)} (comp Q18)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="page.json or bundle dir")
    ap.add_argument("--manifest", required=True, help="shape_manifest.json")
    ap.add_argument("--views", nargs="*", default=[], help="optional .sql files to scan")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    pages = load_page(args.target)
    for i, page in enumerate(pages):
        label = page.get("title") or page.get("pageDefinitionId") or f"page[{i}]"
        check_page(page, manifest, label)

    check_views_sql(args.views, manifest)

    for w in WARNS:
        print("WARN:", w)
    for e in ERRORS:
        print("ERROR:", e)
    print(f"RESULT: {'✓ PASS' if not ERRORS else '✗ FAIL'} "
          f"({len(ERRORS)} errors, {len(WARNS)} warnings)")
    return 0 if not ERRORS else 1


if __name__ == "__main__":
    sys.exit(main())
