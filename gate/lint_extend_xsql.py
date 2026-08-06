#!/usr/bin/env python3
"""
lint_extend_xsql.py  —  Linter for Xactly Extend xSQL (datasource views + page-embedded xSQL).

Encodes the strict-context rules and known perf traps so agent-generated queries are safe
before they hit ADS. Two dialects (per reference_xactly_schema / reference_xactly_xsql_queries):
  - view      (default)  : demo-schema views tolerate LIMIT / Empty() / mid-UNION ORDER BY -> WARN
  - --strict            : variableConfigurator / whereClause / validationXsql context -> those are ERROR

Usage:
    python3 lint_extend_xsql.py views.sql [--strict]
    python3 lint_extend_xsql.py --page page.json          # lint xSQL embedded in the page (strict) + collect vars
    python3 lint_extend_xsql.py views.sql --page page.json # + cross-check every :param is a declared page variable

Checks:
  * LIMIT                         strict:ERROR  view:WARN   (use `AND rownum = 1`)
  * Empty()                       strict:ERROR  view:ok
  * ORDER BY inside a UNION member strict:ERROR view:WARN   (only allowed at very end of full UNION)
  * JOIN <ShowXxx(...)>           WARN          table function re-evaluated per row -> 504; make it sole FROM + IN
  * ; (semicolon)                 WARN          xSQL statements usually omit terminators
  * SELECT *                      WARN          list columns explicitly in datasource views
  * unbalanced parentheses        ERROR
  * :param not a declared page var ERROR        (only when --page supplied)

Exit code 0 iff no ERRORs.
"""
import sys, re, json, os, argparse

TABLE_FUNCS = r"(?:ShowQuotaAttainment|ShowCredit|ShowOrders|Show\w+)"


def get_props(doc):
    return (doc.get("pageSchema", {}) or {}).get("controlSchema", {}).get("schema", {}).get("properties", {})


def iter_controls(props):
    if not isinstance(props, dict):
        return
    for key, ctrl in props.items():
        if not isinstance(ctrl, dict):
            continue
        yield ctrl
        for sk in ("pageSchema", "footerSchema"):
            sub = ctrl.get(sk)
            if isinstance(sub, dict):
                yield from iter_controls((sub.get("controlSchema", {}) or {}).get("schema", {}).get("properties", {}))


def collect_page(doc):
    """Return (declared_vars:set, embedded:[(label, xsql)])."""
    declared, embedded = set(), []
    for ctrl in iter_controls(get_props(doc)):
        for v in ctrl.get("variables", []) or []:
            if isinstance(v, dict) and v.get("name"):
                declared.add(v["name"])
        cid = ctrl.get("controlId", "?")
        for k in ("xSQL", "workflowXsql"):
            if isinstance(ctrl.get(k), str) and ctrl[k].strip():
                embedded.append((f"{cid}.{k}", ctrl[k]))
        for v in ctrl.get("variables", []) or []:
            if isinstance(v, dict) and isinstance(v.get("updateXsql"), str) and v["updateXsql"].strip():
                embedded.append((f"{cid}.updateXsql", v["updateXsql"]))
        for ev in ctrl.get("events", []) or []:
            vx = (ev.get("broadcastArgs") or {}).get("validationXsql")
            if isinstance(vx, str) and vx.strip():
                embedded.append((f"{cid}.event[{ev.get('name')}].validationXsql", vx))
    return declared, embedded


def clean_body(body):
    """Strip SQL comments and one trailing statement terminator so we lint just the xSQL body."""
    body = re.sub(r"/\*.*?\*/", " ", body, flags=re.S)   # block comments
    body = re.sub(r"--[^\n]*", "", body)                  # line comments
    return body.strip().rstrip(";").strip()


def strip_literals(s):
    """Blank out single-quoted string literals (handles '' escapes) so their contents aren't scanned."""
    return re.sub(r"'(?:[^']|'')*'", "''", s)


def split_views(sql):
    """Yield (view_name, clean_body) for each CREATE VIEW ... AS <body>; else ('(raw)', clean sql)."""
    found = False
    for m in re.finditer(r"CREATE\s+VIEW\s+(?:\w+\.)?(\w+)\s+AS\s+(.*?)(?=(?:CREATE\s+VIEW\b)|\Z)",
                         sql, re.I | re.S):
        found = True
        yield m.group(1), clean_body(m.group(2))
    if not found:
        yield "(raw)", clean_body(sql)


def mid_union_order_by(body):
    """True if an ORDER BY occurs before a later UNION (i.e., inside a member, not final)."""
    if not re.search(r"\bUNION\b", body, re.I):
        return False
    idx_ob = [m.start() for m in re.finditer(r"\bORDER\s+BY\b", body, re.I)]
    idx_un = [m.start() for m in re.finditer(r"\bUNION\b", body, re.I)]
    return any(ob < max(idx_un) for ob in idx_ob)


def lint_body(label, body, dialect, declared, errors, warns):
    def E(m): errors.append(f"{label}: {m}")
    def W(m): warns.append(f"{label}: {m}")
    strict = dialect == "strict"

    for fn in re.findall(r"\b(LEAST|GREATEST|COALESCE|IFNULL)\s*\(", body, re.I):
        alt = "a CASE expression" if fn.upper() in ("LEAST", "GREATEST") else "Nvl(...)"
        E(f"{fn.upper()}() is not a valid xSQL function — use {alt}")
    if "||" in strip_literals(body):
        (E if strict else W)("|| string-concat operator — prefer Concat(a, b) (nest for 3+ parts); disallowed in strict VC/whereClause/validationXsql context")
    if re.search(r"\bLIMIT\b", body, re.I):
        (E if strict else W)("LIMIT used — not allowed in strict xSQL; use `AND rownum = 1`")
    if re.search(r"\bEmpty\s*\(", body, re.I) and strict:
        E("Empty() used — invalid in strict variableConfigurator/whereClause xSQL")
    if mid_union_order_by(body):
        (E if strict else W)("ORDER BY inside a UNION member — only allowed at the very end of the full UNION")
    if re.search(r"\bJOIN\s+" + TABLE_FUNCS + r"\s*\(", body, re.I):
        W("table function in a JOIN re-evaluates once per probe row (504 risk) — make it the sole FROM rowset and filter with a non-correlated IN")
    if ";" in body.strip().rstrip(";"):
        W("semicolon inside statement — xSQL statements normally omit terminators")
    if re.search(r"SELECT\s+\*", body, re.I):
        W("SELECT * — list columns explicitly in datasource views")
    if body.count("(") != body.count(")"):
        E(f"unbalanced parentheses ( {body.count('(')} '(' vs {body.count(')')} ')' )")
    if declared is not None:
        for p in sorted(set(re.findall(r":(\w+)", strip_literals(body)))):
            if p not in declared:
                E(f"param :{p} is not a declared page variable")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sql", nargs="?", help="views .sql file")
    ap.add_argument("--page", help="page .json (declared vars + embedded xSQL)")
    ap.add_argument("--strict", action="store_true", help="treat the .sql file as strict-context xSQL")
    args = ap.parse_args()

    errors, warns = [], []
    declared = None

    if args.page:
        if not os.path.exists(args.page):
            print(f"ERROR: --page {args.page} not found"); sys.exit(1)
        doc = json.load(open(args.page, encoding="utf-8"))
        declared, embedded = collect_page(doc)
        print(f"Declared page variables: {len(declared)}")
        for label, xsql in embedded:                     # page-embedded xSQL is always strict context
            lint_body(label, xsql, "strict", declared, errors, warns)

    if args.sql:
        if not os.path.exists(args.sql):
            print(f"ERROR: {args.sql} not found"); sys.exit(1)
        sql = open(args.sql, encoding="utf-8", errors="ignore").read()
        dialect = "strict" if args.strict else "view"
        n = 0
        for name, body in split_views(sql):
            n += 1
            lint_body(f"view {name}", body, dialect, declared, errors, warns)
        print(f"Statements linted from {args.sql}: {n}  (dialect: {dialect})")

    if not args.sql and not args.page:
        ap.print_help(); sys.exit(2)

    if errors:
        print(f"\n✗ {len(errors)} ERROR(S):")
        for e in errors: print("  ERROR:", e)
    if warns:
        print(f"\n⚠ {len(warns)} WARNING(S):")
        for w in warns: print("  WARN :", w)
    if not errors and not warns:
        print("\n✓ PASS — no errors, no warnings.")
    elif not errors:
        print(f"\n✓ PASS (with {len(warns)} warning(s) to review).")
    else:
        print(f"\n✗ FAIL — {len(errors)} error(s).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
