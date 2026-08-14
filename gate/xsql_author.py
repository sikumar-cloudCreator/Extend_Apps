#!/usr/bin/env python3
"""
xsql_author.py — grounded xSQL authoring + the deterministic lint GATE, for the Extend MCP.

Two capabilities, both real (no stubs):

  lint_xsql(sql, strict=False)  -> {verdict, errors, warnings}
      Runs the canonical lint_extend_xsql.py rules IN-PROCESS over one or more CREATE VIEW
      bodies (or a raw body). This is the gate that turns a guessed view into a verified one.

  write_xsql(spec)              -> {xsql, verdict, errors, warnings, source, grounding, needs_human}
      Composes REAL xSQL from the proven Xactly patterns (extend_kb) when spec.pattern matches a
      known template, substituting the spec's params/filters. For an unrecognised pattern it does
      NOT hallucinate — it returns a grounded scaffold (schema slice + closest exemplars + the hard
      rules) with needs_human=True. EITHER WAY the returned xSQL is run through the lint gate first.

The proven templates below are lifted from extend_kb/xsql_schema_and_patterns.md (the same exemplars
the human authors use), so a match emits query text that already obeys the rules.
"""
import os, re, json, importlib.util

# ---- the real tenant view catalog (reuse an existing view before authoring a new one) --------
_CATALOG_PATH = os.environ.get("EXTEND_CATALOG_PATH") or \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasources.json")
try:
    _CATALOG = json.load(open(_CATALOG_PATH))
except Exception:
    _CATALOG = []
_BYNAME = {c["name"].lower(): c for c in _CATALOG}


def _find_reusable(spec):
    """Return an existing catalog view that satisfies the request, or None.
    Match order: exact view_name, then a view whose columns cover every requested column."""
    nm = (spec.get("view_name") or "").lower()
    if nm in _BYNAME:
        return _BYNAME[nm]
    need = {c.lower() for c in (spec.get("columns") or [])}
    if not need:
        return None
    best = None
    for c in _CATALOG:
        cols = {x.lower() for x in c.get("columns", [])}
        if need <= cols and (best is None or len(cols) < len(best[1])):
            best = (c, cols)  # smallest covering view = tightest fit
    return best[0] if best else None

# ---- import the canonical lint rules in-process (single source of truth) --------------------
_LINT_PATHS = [
    os.path.expanduser("~/.claude/skills/extend-check/lint_extend_xsql.py"),
    os.path.expanduser("~/Documents/Code_and_Data/lint_extend_xsql.py"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "lint_extend_xsql.py"),
]


def _load_lint():
    for p in _LINT_PATHS:
        if os.path.exists(p):
            spec = importlib.util.spec_from_file_location("lint_extend_xsql", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, p
    return None, None


_LINT, _LINT_SRC = _load_lint()


def lint_xsql(sql: str, strict: bool = False, declared_params=None) -> dict:
    """Gate xSQL through the canonical rules. strict=True for VC/whereClause/validationXsql context.
    declared_params: if given, every :param must be in it (else ERROR)."""
    if _LINT is None:
        return {"verdict": "UNKNOWN", "errors": ["lint_extend_xsql.py not found on this machine"],
                "warnings": [], "lint_source": None}
    errors, warns = [], []
    dialect = "strict" if strict else "view"
    declared = set(declared_params) if declared_params is not None else None
    n = 0
    for name, body in _LINT.split_views(sql):
        n += 1
        _LINT.lint_body(f"view {name}", body, dialect, declared, errors, warns)
    return {"verdict": "FAIL" if errors else "PASS", "errors": errors, "warnings": warns,
            "statements": n, "dialect": dialect, "lint_source": _LINT_SRC}


# ---- proven pattern templates (from extend_kb) ----------------------------------------------
# Each template returns a CREATE-VIEW-less body; write_xsql wraps it. {param} slots are filled from
# spec["params_map"] with sensible Xactly defaults.
def _p(spec, key, default):
    return (spec.get("params_map") or {}).get(key, default)


def _tmpl_master_participant_id(spec):
    return f"""select pa.name,
       master_pa.participant_id as master_participant_id
from xactly.xc_participant pa
inner join xactly.xc_period p
  on pa.effective_start_date < p.end_date
  and pa.effective_end_date > p.start_date
join xactly.xc_participant master_pa
  on pa.employee_id = master_pa.employee_id
  and master_pa.is_master = 1
where p.name = :{_p(spec,'period','v_period')}
  and pa.name = :{_p(spec,'participant','v_participant')}"""


def _tmpl_master_position_id(spec):
    return f"""select distinct
    part.name as participant_name,
    pos.name as position_name,
    pos.master_position_id
from xactly.xc_participant master_part
join xactly.xc_period curr on 1 = 1
join xactly.xc_participant part
  on part.employee_id          = master_part.employee_id
  and part.effective_start_date < curr.end_date
  and part.effective_end_date   > curr.start_date
left join xactly.xc_pos_part_assignment ppa
  on ppa.participant_id = master_part.participant_id
join xactly.xc_position pos
  on pos.position_id            = ppa.position_id
  and pos.effective_start_date  < curr.end_date
  and pos.effective_end_date    > curr.start_date
  and pos.incent_st_date        < curr.end_date
  and pos.incent_end_date       > curr.start_date
where master_part.participant_id = :{_p(spec,'master_participant_id','v_master_participant_id')}
  and master_part.is_master      = 1
  and curr.name                  = :{_p(spec,'period','v_period')}"""


def _tmpl_credits_by_measure(spec):
    cur = spec.get("currency")
    cur_filter = f"\n    AND cr.amount_display_symbol = '{cur}'" if cur else ""
    return f"""SELECT
    ct.name AS measure_name,
    Nvl(FormatNumber(SUM(cr.amount), '#,##0.00'), '0.00') AS credits
FROM xactly.xc_participant master_part
JOIN xactly.xc_period curr ON 1 = 1
JOIN xactly.xc_credit cr
    ON cr.participant_id = master_part.participant_id
    AND cr.period_id     = curr.period_id{cur_filter}
JOIN xactly.xc_credit_type ct ON ct.credit_type_id = cr.credit_type_id
WHERE master_part.participant_id = :{_p(spec,'master_participant_id','v_master_participant_id')}
  AND master_part.is_master      = 1
  AND curr.name                  = :{_p(spec,'period','v_period')}
GROUP BY ct.name"""


def _tmpl_period_list(spec):
    return f"""select p.name as period_name
from xactly.xc_period p
where p.name LIKE Concat('%-', :{_p(spec,'year_number','v_year_number')})
order by p.start_date"""


def _tmpl_headcount(spec):
    return f"""select count(*) as headcount
from ShowIncentHierarchy(EffectiveAsOf = :{_p(spec,'as_of','v_qtr_start_date')}, ParentId = :{_p(spec,'master_position_id','v_master_position_id')}) hier
where hier.position_is_active = 'true'"""


TEMPLATES = {
    "master_participant_id": _tmpl_master_participant_id,
    "master_position_id":    _tmpl_master_position_id,
    "credits_by_measure":    _tmpl_credits_by_measure,
    "period_list":           _tmpl_period_list,
    "headcount":             _tmpl_headcount,
}

# ---- grounding for unrecognised patterns ----------------------------------------------------
HARD_RULES = [
    "BANNED functions: LEAST, GREATEST, COALESCE, IFNULL — cap/floor with CASE, null-coalesce with Nvl().",
    "No || in strict contexts — use Concat(a,b) (nest for 3+).",
    "No LIMIT / rownum / RowNumber() — reduce to one row by aggregating (Nvl(MAX(id),0)) or a non-correlated IN.",
    "No ToNumber(); no ToString(col)/ToChar(col) in a predicate. Compare col = :v_param directly and declare the "
    "param's dataType in the query object's variables[].",
    "Scope facts on participant_id — never eff_participant_id.",
    "A card/tile/resolver view must ALWAYS return exactly one row (aggregate, no GROUP BY, every output Nvl'd): "
    "a zero-row view renders the literal string 'undefined'.",
    "Nvl goes innermost: Concat('$', FormatNumber(Nvl(x,0), '#,##0')) — never Nvl(Concat(...)).",
    "No Empty(), no SELECT *, no trailing ;, no correlated subqueries.",
    "No ORDER BY inside a UNION member; UNION members must type-match (FormatNumber -> string, so static members must be '0.00').",
    "Don't reference a computed alias from a derived table in another computed expr — repeat the aggregate inline.",
    "JOIN ShowXxx(...) re-runs per row (504) — make the table func the sole FROM and filter with a non-correlated IN.",
]
EFF_DATE_TABLES = {
    "xc_participant": "effective_start_date < p.end_date AND effective_end_date > p.start_date",
    "xc_position": "BOTH ranges must overlap: effective_start_date/end_date AND incent_st_date/incent_end_date",
    "xc_pos_hierarchy_type": "effective_start_date < p.end_date AND effective_end_date > p.start_date",
    "xc_pos_part_assignment": "NO effective-date columns — do not add period overlap here",
}


def _scaffold(spec):
    cols = spec.get("columns") or []
    sel = ",\n    ".join(f"/* {c} */ Cast(Null As Varchar) AS {c}" for c in cols) or "/* project real columns */"
    tables = spec.get("tables") or []
    eff = {t: EFF_DATE_TABLES[t] for t in tables if t in EFF_DATE_TABLES}
    body = f"""-- SCAFFOLD (needs authoring): pattern '{spec.get('pattern')}' not in the template library.
-- Fill the SELECT with REAL columns/aggregates and correct joins per the grounding below.
SELECT
    {sel}
FROM xactly.{tables[0] if tables else '<base_table>'} /* + joins */
WHERE 1 = 1  /* + :param filters */"""
    return body, {
        "closest_templates": list(TEMPLATES.keys()),
        "effective_date_join_hints": eff,
        "hard_rules": HARD_RULES,
        "note": "This is a grounded starting point, NOT a finished view — the SELECT is placeholder and will "
                "not pass review until real columns/joins replace it.",
    }


def write_xsql(spec: dict) -> dict:
    """
    spec: {
      view_name: str, schema?: 'demo', pattern: one of TEMPLATES or 'custom',
      params_map?: {role: varname}   e.g. {"period":"v_period"},
      currency?: 'EUR', columns?: [str], tables?: [xc_* names]   # columns/tables used for scaffold
    }
    Returns real xSQL for a known pattern (lint-gated) or a grounded scaffold for 'custom'/unknown.
    """
    name = spec.get("view_name") or "v_new_view"
    schema = spec.get("schema") or os.environ.get("EXTEND_DEFAULT_SCHEMA", "demo")
    pattern = spec.get("pattern") or "custom"

    # 0) Reuse an existing real view before authoring anything new (unless caller forces fresh).
    if not spec.get("force_new"):
        hit = _find_reusable(spec)
        if hit and hit.get("xsql"):
            full = f"CREATE VIEW {hit['schema']}.{hit['name']} AS\n{hit['xsql'].rstrip(';')}"
            gate = lint_xsql(full, strict=False)
            return {"view_name": hit["name"], "schema": hit["schema"], "source": "reuse:catalog",
                    "xsql": full, "verdict": gate["verdict"], "errors": gate["errors"],
                    "warnings": gate["warnings"], "needs_human": False, "reused": True,
                    "params": hit.get("params", []), "columns": hit.get("columns", []),
                    "grounding": {"note": f"Reused existing tenant view '{hit['name']}' — do not create a duplicate."},
                    "available_patterns": list(TEMPLATES.keys())}

    if pattern in TEMPLATES:
        body = TEMPLATES[pattern](spec)
        grounding, needs_human, source = None, False, f"template:{pattern}"
    else:
        body, grounding = _scaffold(spec)
        needs_human, source = True, "scaffold"

    full = f"CREATE VIEW {schema}.{name} AS\n{body}"
    gate = lint_xsql(full, strict=False)
    return {
        "view_name": name, "schema": schema, "source": source,
        "xsql": full,
        "verdict": gate["verdict"], "errors": gate["errors"], "warnings": gate["warnings"],
        "needs_human": needs_human or gate["verdict"] != "PASS",
        "grounding": grounding,
        "available_patterns": list(TEMPLATES.keys()),
    }


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) > 1 and sys.argv[1] == "--lint":
        print(json.dumps(lint_xsql(open(sys.argv[2]).read()), indent=2))
    else:
        demo = {"view_name": "v_credits_by_measure", "pattern": "credits_by_measure", "currency": "EUR"}
        print(json.dumps(write_xsql(demo), indent=2))
