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
  * ToNumber(...)                 ERROR         banned cast — bind directly, declare dataType in the query object
  * ToString(col)/ToChar(col) in a predicate   ERROR   per-row cast, defeats the index
  * rownum / RowNumber() / LIMIT  ERROR         no row limiters — aggregate to one row (MAX/SUM) or use IN
  * eff_participant_id            ERROR         use participant_id
  * Nvl outside Concat/FormatNumber            WARN    ships a bare $/% when the value is NULL
  * card/tile view with no aggregate           WARN    a zero-row view renders the literal `undefined`
  * hardcoded measure/component name LIKE      WARN    parameterize (:v_measure) or resolve the name
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


CLAUSE_RE = re.compile(r"\b(SELECT|WHERE|ON|HAVING|GROUP\s+BY|ORDER\s+BY|CASE)\b", re.I)
PREDICATE_CLAUSES = ("WHERE", "ON", "HAVING")
# view names whose control renders a single value set (card/tile/Custom/resolver) -> one-row contract
CARD_NAME_RE = re.compile(r"(card|tile|kpi|summary|measure|payout|header|_id)$", re.I)
AGG_RE = re.compile(r"\b(SUM|MAX|MIN|COUNT|AVG)\s*\(", re.I)


def in_predicate(body, pos):
    """True if offset `pos` sits in a WHERE / JOIN..ON / HAVING clause (vs the SELECT list)."""
    last = None
    for m in CLAUSE_RE.finditer(body, 0, pos):
        last = m.group(1).upper().split()[0]
    return last in PREDICATE_CLAUSES


def call_args(body, fn):
    """Yield the argument text of every `fn(...)` call, paren-balanced."""
    for m in re.finditer(r"\b" + fn + r"\s*\(", body, re.I):
        depth, i = 1, m.end()
        while i < len(body) and depth:
            if body[i] == "(":
                depth += 1
            elif body[i] == ")":
                depth -= 1
            i += 1
        yield body[m.end():i - 1]


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

    # --- binding contract: no casts, no row limiters, no eff_participant_id (2026-08-15 directive) ---
    if re.search(r"\bToNumber\s*\(", body, re.I):
        E("ToNumber() is banned — bind the param directly (col = :v_x) and declare its dataType in the "
          "query object's variables[]")
    for m in re.finditer(r"\b(ToString|ToChar)\s*\(", body, re.I):
        if in_predicate(body, m.start()):
            E(f"{m.group(1)}() in a WHERE/JOIN predicate — per-row cast on every column value, defeats the "
              f"index; compare the column to the param directly")
    if re.search(r"\brownum\b|\bRow_?Number\s*\(", body, re.I):
        E("rownum / RowNumber() is banned — guarantee a single row by aggregating "
          "(SELECT Nvl(MAX(id), 0) …), or pick one of many with a non-correlated IN (SELECT …)")
    if re.search(r"\bLIMIT\b", body, re.I):
        E("LIMIT is not valid xSQL — aggregate to a single row (MAX/SUM) instead")
    if re.search(r"\beff_participant_id\b", body, re.I):
        E("eff_participant_id — this tenant scopes facts on participant_id")
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

    # --- render-quality checks (render-defect rules R1-R4, R8) ---
    for args in call_args(body, "Nvl"):
        if re.match(r"\s*Concat\s*\(", args, re.I):
            W("Nvl() wraps a Concat() — the NULL is inside, so the page ships a bare '$'/'%' with no number; "
              "put Nvl innermost: Concat('$', FormatNumber(Nvl(x, 0), '#,##0'))")
    for args in call_args(body, "Concat"):
        if re.search(r"\b(SUM|MAX|MIN|AVG|Round|FormatNumber)\s*\(", args, re.I) and not re.search(r"\bNvl\s*\(", args, re.I):
            W("Concat() over an unguarded value — a NULL renders as a bare prefix/suffix; wrap the value in Nvl()")
    name = label.split()[-1] if label.startswith("view ") else ""
    if name and CARD_NAME_RE.search(name):
        if not AGG_RE.search(body):
            W(f"'{name}' looks like a card/tile/resolver view but has no aggregate — a zero-row result renders "
              f"the literal string 'undefined'; aggregate (SUM/MAX) with no GROUP BY so it always returns one row")
        elif re.search(r"\bGROUP\s+BY\b", body, re.I):
            W(f"'{name}' looks like a card/tile/resolver view but has a GROUP BY — it can return zero rows "
              f"(renders 'undefined') or many; a card view must return exactly one row")
    for col, lit in re.findall(r"\b(\w*name)\s*(?:=|LIKE)\s*'([^']+)'", body, re.I):
        if lit.strip("%").lower() not in ("all", ""):
            W(f"hardcoded name literal ({col} = '{lit}') — measure/component names are data: take them as a "
              f":param (e.g. :v_measure) or resolve them from the list view, or a tenant mismatch silently yields 0")


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
