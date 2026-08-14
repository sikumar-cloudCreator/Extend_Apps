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


def det_binding_rules():
    """The 2026-08-15 binding directives + the render-defect rules must be hard lint errors."""
    cases = [
        ("ToNumber banned", "CREATE VIEW demo.x AS SELECT Nvl(SUM(c.amount),0) AS a FROM xactly.xc_credit c "
                            "WHERE c.participant_id = ToNumber(:v_master_participant_id)"),
        ("ToString(col) in predicate banned", "CREATE VIEW demo.x AS SELECT Nvl(SUM(c.amount),0) AS a "
                                              "FROM xactly.xc_credit c WHERE ToString(c.participant_id) = :v_x"),
        ("rownum banned", "CREATE VIEW demo.x AS SELECT Nvl(MAX(c.credit_id),0) AS a FROM xactly.xc_credit c "
                          "WHERE rownum = 1"),
        ("eff_participant_id banned", "CREATE VIEW demo.x AS SELECT Nvl(SUM(c.amount),0) AS a "
                                      "FROM xactly.xc_credit c WHERE c.eff_participant_id = :v_x"),
    ]
    for label, sql in cases:
        r = qe.check(sql, None)
        check(f"lint: {label} -> FAIL", r["verdict"] == "FAIL", str(r["errors"]))

    ok = ("CREATE VIEW demo.seller_kpi_card AS SELECT Concat('$', FormatNumber(Nvl(SUM(c.amount),0), '#,##0')) "
          "AS qtd_credits FROM xactly.xc_credit c WHERE c.participant_id = :v_master_participant_id")
    r = qe.check(ok, None)
    check("lint: direct bind + aggregate + Nvl -> PASS", r["verdict"] == "PASS" and not r["warnings"],
          f"errors={r['errors']} warns={r['warnings']}")

    # one-row contract + Nvl placement are warnings, not blockers
    warn_sql = ("CREATE VIEW demo.seller_total_tile AS SELECT Nvl(Concat('$', FormatNumber(c.amount, '#,##0')), '$0') "
                "AS v FROM xactly.xc_credit c WHERE c.participant_id = :v_x")
    w = qe.check(warn_sql, None)
    joined = " ".join(w["warnings"])
    check("lint: zero-row card view warns", "undefined" in joined, joined)
    check("lint: Nvl outside Concat warns", "Nvl innermost" in joined or "bare" in joined, joined)


def det_render_gate():
    """Render-quality defects observed on the shipped page must fail the page gate."""
    shell = {"pageDefinitionId": "pg_eval", "title": "Eval"}
    ds = "incnt_stmt_active_participant_list_admin_view"
    dup = [{"kind": "label", "title": "Deal Ledger Details"},
           {"kind": "table", "title": "Deal Ledger Details", "ds": ds, "schema": "demo",
            "columns": [{"field": "participant_name_display"}], "onload": ["refresh"]}]
    r = pdz.assemble(dup, shell)
    page = r["page"]
    tbl = next(c for c in page["pageSchema"]["controlSchema"]["schema"]["properties"].values()
               if c.get("type") == "table")
    check("render: duplicate heading dropped from the table title", tbl["title"] == "", tbl["title"])
    check("render: table height is bounded", tbl["maxHeight"] and tbl["pagination"]["itemsPerPage"] <= 25,
          f"maxHeight={tbl['maxHeight']} rows={tbl['pagination']['itemsPerPage']}")

    ph = [{"kind": "card", "title": "Pending", "html": "<div>Pending Payout<br/>Verification in progress</div>"}]
    r2 = pdz.assemble(ph, shell)
    check("render: placeholder copy -> FAIL", r2["verdict"] == "FAIL"
          and any("placeholder" in str(e) for e in r2["errors"]), str(r2["errors"]))


def det_query_object_typing():
    """Params are typed in the query object (that's what removes the need for a predicate cast)."""
    q = aa.query_file({"name": "v", "schema": "demo",
                       "xsql": "SELECT 1 AS a WHERE p = :v_master_participant_id AND n = :v_measure "
                               "AND d = :v_start_date"})
    types = {v["name"]: (v["dataType"], v["value"]) for v in q["variables"]}
    check("query object: numeric id typed Number, seeded 0",
          types["v_master_participant_id"] == ("Number", "0"), str(types))
    check("query object: filter typed String, seeded All", types["v_measure"] == ("String", "All"), str(types))
    check("query object: date param typed Date", types["v_start_date"][0] == "Date", str(types))


def det_knowledge_currency():
    """Overturned lessons must not be injected into any build prompt."""
    import knowledge_base as kb
    text = kb.render("query") + kb.render("page") + kb.render("architect")
    stale = [frag for frag in ("still use ToString(col)", "WHERE rownum = 1",
                               "IC self-view filters by the built-in current-user lookups")
             if frag in text]
    check("knowledge: overturned lessons retired", not stale, str(stale))
    fresh = ["ToNumber() is banned", "No rownum", "participant_id, never eff_participant_id",
             "exactly one row", "Title once"]
    missing = [f for f in fresh if f not in text]
    check("knowledge: new rules present", not missing, str(missing))


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
    rep = {"policySet": {"version": 16, "name": "Eval_Rep_Reporting", "visibleToTenant": True, "description": "self"},
           "policySetItems": [{"itemType": "ALLOW", "resourceName": "xactly.xc_credit", "resourceType": "TABLE",
                               "operation": "READ", "predicates": "participant_id = LookupCurrentUserMasterParticipantId()",
                               "conjunctionType": "AND", "isExclusive": False}]}
    views = [{"name": "v1", "schema": "demo", "xsql": "SELECT 1 AS a WHERE ( :v_measure = 'All' OR n = :v_measure )"}]
    aa.write_bundle(d, "Eval App", "Analytics",
                    pages=[{"pageDefinitionId": "pid-1", "title": "P1", "page": {"pageDefinitionId": "pid-1"}}],
                    views=views, tables=["xc_credit"], workflows=[],
                    policy_sets=[rep], access_roles=["Sales Rep", "Administrator"])
    # DEFAULT: queries ship as xSQL .sql
    need = ["ADLC.json", "app/Application.json", "app/pid-1.json", "queries/demo/v1.sql",
            "policy_sets/Eval_Rep_Reporting.json", "tables/schemas/xactly/xc_credit.json"]
    missing = [p for p in need if not os.path.exists(os.path.join(d, p))]
    check("bundle: real export layout (xsql default)", not missing, f"missing {missing}")
    sql = open(os.path.join(d, "queries/demo/v1.sql")).read()
    check("bundle: query is xSQL CREATE VIEW", sql.lstrip().upper().startswith("CREATE VIEW DEMO.V1"), sql[:40])
    adlc = json.load(open(os.path.join(d, "ADLC.json")))
    check("bundle: ADLC manifest keys", set(adlc) >= {"application", "queries", "pageDefinitions", "tables",
          "policySets", "agents"} and adlc["policySets"] and adlc["queries"][0].endswith(".sql"))
    # OPT-IN: json query-object format still available
    d2 = tempfile.mkdtemp()
    aa.write_bundle(d2, "Eval App", "Analytics",
                    pages=[{"pageDefinitionId": "pid-1", "title": "P1", "page": {"pageDefinitionId": "pid-1"}}],
                    views=views, tables=[], workflows=[], query_format="json")
    q = json.load(open(os.path.join(d2, "queries/demo/v1.json")))
    check("bundle: json format seeds vars", q.get("name") == "v1"
          and any(v["name"] == "v_measure" and v["value"] == "All" for v in q.get("variables", [])), str(q.get("variables")))
    app = json.load(open(os.path.join(d, "app/Application.json")))
    check("bundle: landingPage + role-gated nav", app.get("landingPageId") == "pid-1"
          and app["sections"][0]["accessRoles"] == ["Sales Rep", "Administrator"])
    page = json.load(open(os.path.join(d, "app/pid-1.json")))
    check("bundle: page envelope versionName", page.get("versionName") == "v1")


def det_grounding():
    s = st.schema_lookup("xc_credit")
    check("schema: xc_credit PK", s.get("primary_key") == ["CREDIT_ID", "PERIOD_ID"], str(s.get("primary_key")))
    r = st.resolve_view(["measure_name"])
    check("reuse: resolves measure_name", r.get("found") and "measure_name" in r.get("columns", []), r.get("name"))


def det_feedback_roundtrip():
    import db
    tmp = tempfile.mktemp(suffix=".db")
    old = db.DB_PATH
    try:
        db.DB_PATH = tmp
        fb.record("query", "give credits", "CREATE VIEW demo.x AS SELECT 1 AS a", accepted=True)
        fb.record("query", "bad one", "SELECT LIMIT", accepted=False, comment="no LIMIT")
        shot = fb.few_shot("query")
        stats = fb.stats()
        check("feedback: few_shot recalls accepted", "give credits" in shot and "bad one" not in shot)
        check("feedback: stats counts", stats["by_kind"]["query"]["accepted"] == 1 and
              stats["by_kind"]["query"]["corrected"] == 1, str(stats["by_kind"]))
    finally:
        db.DB_PATH = old
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
    # Customer-specific fixtures live outside the repo (gitignored) — the committed set is the
    # generic ones, so this floor is 2. Drop your own FRDs into evals/golden/<name>/ to widen it.
    check("golden: >=2 fixtures present", len(cases) >= 2, f"found {[c[0] for c in cases]}")
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
    for fn in (det_lint_regression, det_binding_rules, det_render_gate, det_query_object_typing,
               det_knowledge_currency, det_page_gate, det_bundle_shape, det_grounding,
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
