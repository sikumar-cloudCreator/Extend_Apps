#!/usr/bin/env python3
"""
run_evals.py — regression + coverage evals for the Extend LLM (user point 8).

Deterministic checks run with NO API key (gate regressions, bundle shape, grounding, feedback roundtrip).
LLM checks (architect page coverage, query authoring) run only if ANTHROPIC_API_KEY is set.

    python evals/run_evals.py            # deterministic only unless a key is present
    python evals/run_evals.py --llm      # force-include LLM checks (needs key)
"""
import os, sys, json, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "app")
sys.path.insert(0, APP)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "gate"))  # vendored deterministic gate

import extend_build
import query_engine as qe
import page_designer as pdz
import app_assembler as aa
import schema_tools as st
import feedback_store as fb

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))


# ---- deterministic checks --------------------------------------------------------------------
def det_lint_regression():
    bad = qe.check("CREATE VIEW demo.x AS SELECT COALESCE(a,0) AS a FROM xactly.xc_credit", None)
    good = qe.check("CREATE VIEW demo.x AS SELECT Nvl(a,0) AS a FROM xactly.xc_credit", None)
    check("lint: COALESCE -> FAIL", bad["verdict"] == "FAIL", str(bad["errors"]))
    check("lint: Nvl -> PASS", good["verdict"] == "PASS", str(good["errors"]))


def det_page_gate():
    shell = {"pageDefinitionId": "pg_eval", "title": "Eval"}
    ok = [{"kind": "dropdown", "title": "Period", "ds": "incnt_stmt_monthly_period_list_till_curr_month",
           "schema": "demo", "valueField": "name_ft", "var": "v_period", "produces": "e_period"},
          {"kind": "table", "title": "Participants", "ds": "incnt_stmt_active_participant_list_admin_view",
           "schema": "demo", "columns": [{"field": "participant_name_display"}], "subscribes": [["e_period", ["refresh"]]]}]
    bad = [{"kind": "table", "title": "P", "ds": "incnt_stmt_active_participant_list_admin_view",
            "schema": "demo", "subscribes": [["e_missing", ["refresh"]]]}]
    check("page gate: valid -> PASS", pdz.assemble(ok, shell)["verdict"] == "PASS")
    r = pdz.assemble(bad, shell)
    cats = {e["category"] for e in r["errors"]}
    check("page gate: broken -> FAIL (wiring+param)", r["verdict"] == "FAIL" and {"wiring", "param"} <= cats, str(cats))


def det_bundle_shape():
    d = tempfile.mkdtemp()
    aa.write_bundle(d, "Eval App", "Analytics",
                    pages=[{"pageDefinitionId": "pid-1", "title": "P1", "page": {"pageDefinitionId": "pid-1"}}],
                    views=[{"name": "v1", "schema": "demo", "xsql": "SELECT 1 AS a"}],
                    tables=["xc_credit"], workflows=[])
    need = ["ADLC.json", "app/Application.json", "app/pid-1.json", "queries/demo/v1.json",
            "tables/schemas/xactly/xc_credit.json"]
    missing = [p for p in need if not os.path.exists(os.path.join(d, p))]
    check("bundle: real export layout", not missing, f"missing {missing}")
    adlc = json.load(open(os.path.join(d, "ADLC.json")))
    check("bundle: ADLC manifest keys", set(adlc) >= {"application", "queries", "pageDefinitions", "tables"})


def det_grounding():
    s = st.schema_lookup("xc_credit")
    check("schema: xc_credit PK", s.get("primary_key") == ["CREDIT_ID", "PERIOD_ID"], str(s.get("primary_key")))
    r = st.resolve_view(["measure_name"])
    check("reuse: resolves measure_name", r.get("found") and "measure_name" in r.get("columns", []), r.get("name"))


def det_feedback_roundtrip():
    tmp = tempfile.mktemp(suffix=".jsonl")
    old = fb.STORE
    try:
        fb.STORE = tmp
        fb.record("query", "give credits", "CREATE VIEW demo.x AS SELECT 1 AS a", accepted=True)
        fb.record("query", "bad one", "SELECT LIMIT", accepted=False, comment="no LIMIT")
        shot = fb.few_shot("query")
        stats = fb.stats()
        check("feedback: few_shot recalls accepted", "give credits" in shot and "bad one" not in shot)
        check("feedback: stats counts", stats["by_kind"]["query"]["accepted"] == 1 and
              stats["by_kind"]["query"]["corrected"] == 1, str(stats["by_kind"]))
    finally:
        fb.STORE = old
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---- golden fixtures (multiple app types, grounded in real catalog views) --------------------
def golden_cases():
    base = os.path.join(HERE, "golden")
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        frd, exp = os.path.join(d, "frd.md"), os.path.join(d, "expected.json")
        if os.path.isdir(d) and os.path.exists(frd) and os.path.exists(exp):
            yield name, frd, json.load(open(exp))


def det_golden_fixtures_valid():
    """No key: every golden's expected_reuse_views must exist in the catalog (keeps fixtures honest)."""
    names = {v["name"] for v in st.list_views()}
    cases = list(golden_cases())
    check("golden: >=3 fixtures present", len(cases) >= 3, f"found {[c[0] for c in cases]}")
    for case, _frd, exp in cases:
        missing = [v for v in exp.get("expected_reuse_views", []) if v not in names]
        check(f"golden[{case}]: reuse views exist in catalog", not missing, f"missing {missing}")


# ---- LLM checks (need key) -------------------------------------------------------------------
def llm_golden_coverage():
    """Run the architect on EVERY golden FRD; assert page count + that it reuses the expected views."""
    for case, frd, exp in golden_cases():
        spec = aa.architect(open(frd).read())
        pages = spec.get("pages", [])
        ds_names = {d["name"] for p in pages for d in p.get("datasources", [])}
        check(f"architect[{case}]: >= {exp.get('min_pages',1)} pages", len(pages) >= exp.get("min_pages", 1),
              f"got {len(pages)}")
        missing = [v for v in exp.get("expected_reuse_views", []) if v not in ds_names]
        check(f"architect[{case}]: reuses {exp.get('expected_reuse_views')}", not missing,
              f"missing {missing}; chose {sorted(ds_names)}")


def llm_query_pass():
    res = qe.generate_query("active participant list for a period",
                            tables=["xc_participant", "xc_period"], params=["v_period"], view_name="v_eval_participants")
    ok = res.get("action") == "reuse" or res.get("verdict") == "PASS"
    check("query: authors/reuses a PASS view", ok, str(res.get("errors")))


def main():
    include_llm = "--llm" in sys.argv or bool(os.environ.get("ANTHROPIC_API_KEY"))
    for fn in (det_lint_regression, det_page_gate, det_bundle_shape, det_grounding,
               det_feedback_roundtrip, det_golden_fixtures_valid):
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, f"EXCEPTION {e}")
    if include_llm:
        for fn in (llm_golden_coverage, llm_query_pass):
            try:
                fn()
            except Exception as e:
                check(fn.__name__, False, f"EXCEPTION {e}")
    else:
        print("(LLM checks skipped — no ANTHROPIC_API_KEY; pass --llm to force)\n")

    width = max(len(n) for n, _, _ in results)
    npass = sum(1 for _, v, _ in results if v == PASS)
    for n, v, d in results:
        mark = "✅" if v == PASS else "❌"
        print(f"{mark} {n.ljust(width)}  {v}" + (f"  — {d}" if v == FAIL and d else ""))
    print(f"\n{npass}/{len(results)} checks passed")
    sys.exit(0 if npass == len(results) else 1)


if __name__ == "__main__":
    main()
