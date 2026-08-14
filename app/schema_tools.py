#!/usr/bin/env python3
"""
schema_tools.py — the grounding layer for the Extend LLM query engine.

Two real sources, no guessing:
  1. The Xactly data dictionary: ~/Documents/xc_tables/xc_<table>.csv (one row per column;
     name, type, PK ordinal, FK table/column). Ignore *_hist.csv.
  2. The tenant view catalog: gate/datasources.json (or $EXTEND_CATALOG_PATH) — existing views with
     name, schema, params, columns, xsql — the reuse-first source.

Stdlib only — importable and CLI-testable with no API key:
    python schema_tools.py xc_credit          # dump a table's columns/PK/FK
    python schema_tools.py --resolve credits amount period_id   # best reusable view for columns
"""
import os, csv, json, glob

XC_DIR = os.path.expanduser(os.environ.get("XC_TABLES_DIR", "~/Documents/xc_tables"))
CATALOG_PATH = os.environ.get("EXTEND_CATALOG_PATH") or \
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gate", "datasources.json")


# ---- source 1: the xc_* data dictionary ------------------------------------------------------
def _csv_path(table: str) -> str | None:
    t = table.strip().lower()
    if not t.startswith("xc_"):
        t = "xc_" + t
    p = os.path.join(XC_DIR, f"{t}.csv")
    return p if os.path.exists(p) else None


def schema_lookup(table: str) -> dict:
    """Real columns/types/PK/FK for one Xactly table. {found, table, columns[], primary_key[], foreign_keys[]}."""
    path = _csv_path(table)
    if not path:
        # suggest near-matches so the caller isn't stuck
        stems = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(XC_DIR, "xc_*.csv"))
                 if not p.endswith("_hist.csv")]
        hint = [s for s in stems if table.strip().lower().replace("xc_", "") in s]
        return {"found": False, "table": table, "note": f"no xc_ csv for {table!r}",
                "did_you_mean": sorted(hint)[:8]}
    cols, pk, fks = [], [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = (r.get("column_name") or "").strip()
            if not name:
                continue
            typ = (r.get("type_name") or "").strip()
            size, scale = (r.get("size") or "").strip(), (r.get("scale") or "").strip()
            nullable = (r.get("is_nullable") or r.get("nullable") or "").strip().upper() in ("YES", "1", "TRUE")
            prim = (r.get("primary_ordinal") or "0").strip()
            fk_t = (r.get("foreign_key_table_name") or "").strip()
            fk_c = (r.get("foreign_key_column_name") or "").strip()
            col = {"name": name, "type": typ, "size": size, "scale": scale, "nullable": nullable,
                   "pk": prim not in ("", "0"), "fk_table": fk_t or None, "fk_column": fk_c or None}
            cols.append(col)
            if col["pk"]:
                pk.append((int(prim), name))
            if fk_t:
                fks.append({"column": name, "references": f"{fk_t}.{fk_c}"})
    pk = [n for _, n in sorted(pk)]
    return {"found": True, "table": os.path.basename(path)[:-4], "schema": "xactly",
            "columns": cols, "primary_key": pk, "foreign_keys": fks}


def render_schema(table: str) -> str:
    """Compact text rendering of a table for an LLM prompt."""
    s = schema_lookup(table)
    if not s.get("found"):
        dym = s.get("did_you_mean") or []
        return f"[{table}] NOT FOUND." + (f" did you mean: {', '.join(dym)}" if dym else "")
    lines = [f"TABLE xactly.{s['table']}  (PK: {', '.join(s['primary_key']) or 'n/a'})"]
    for c in s["columns"]:
        tag = []
        if c["pk"]:
            tag.append("PK")
        if c["fk_table"]:
            tag.append(f"FK->{c['fk_table']}.{c['fk_column']}")
        if not c["nullable"]:
            tag.append("NOT NULL")
        sz = f"({c['size']}{','+c['scale'] if c['scale'] not in ('','0') else ''})" if c["size"] not in ("", "0") else ""
        lines.append(f"  {c['name']} {c['type']}{sz}{'  ['+', '.join(tag)+']' if tag else ''}")
    return "\n".join(lines)


# ---- source 2: the tenant view catalog (reuse-first) -----------------------------------------
def _load_catalog() -> list:
    try:
        return json.load(open(CATALOG_PATH))
    except Exception:
        return []


_CATALOG = _load_catalog()
_BYNAME = {c["name"].lower(): c for c in _CATALOG}


def list_views() -> list[dict]:
    """All existing tenant views: name, schema, params, columns (no xsql body)."""
    return [{"name": c["name"], "schema": c.get("schema"), "params": c.get("params", []),
             "columns": c.get("columns", [])} for c in _CATALOG]


def get_view(name: str) -> dict | None:
    return _BYNAME.get(name.strip().lower())


def resolve_view(needed_columns: list[str]) -> dict:
    """Best existing view covering needed_columns. {found, name, params, columns, matched, missing, covers_all}."""
    need = {c.lower() for c in needed_columns}
    best = None
    for c in _CATALOG:
        cols = {x.lower() for x in c.get("columns", [])}
        matched = need & cols
        if matched and (best is None or len(matched) > best[0] or
                        (len(matched) == best[0] and len(cols) < len(best[3]))):
            best = (len(matched), c, matched, cols)
    if not best:
        return {"found": False, "note": "no existing view covers those columns; author a new one"}
    _, c, matched, cols = best
    return {"found": True, "name": c["name"], "schema": c.get("schema"), "params": c.get("params", []),
            "columns": c.get("columns", []), "matched": sorted(matched),
            "missing": sorted(need - cols), "covers_all": need <= cols}


def render_reuse_candidates(needed_columns: list[str], k: int = 5) -> str:
    """Top-k reuse candidates as prompt text."""
    need = {c.lower() for c in needed_columns}
    scored = []
    for c in _CATALOG:
        cols = {x.lower() for x in c.get("columns", [])}
        m = need & cols
        if m:
            scored.append((len(m), c))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return "REUSE CANDIDATES: none cover the requested columns — author a new view."
    out = ["REUSE CANDIDATES (prefer these before authoring):"]
    for _, c in scored[:k]:
        out.append(f"  {c['name']}  params={c.get('params', [])}  columns={c.get('columns', [])}")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "--resolve":
        print(json.dumps(resolve_view(sys.argv[2:]), indent=2))
    elif len(sys.argv) >= 2:
        print(render_schema(sys.argv[1]))
    else:
        print(__doc__)
