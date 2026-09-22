#!/usr/bin/env python3
"""
knowledge_base.py — the builder's accumulating knowledge (user point 5, "learn on each iteration").

Distilled RULES/LESSONS, stored in the shared SQLite DB (db.py) so the whole team's knowledge compounds.
Injected into every build (query/page/architect) as guardrails, complementing feedback_store's few-shot
EXAMPLES. Each iteration/correction can add a lesson; every future build of that scope inherits it.

Scopes: "query", "page", "architect", "frd", "all". Seeded on first use.
CLI:  python knowledge_base.py list [scope]   |   python knowledge_base.py add <scope> "<rule>" "<why>"
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

SCOPES = {"query", "page", "architect", "frd", "all"}

SEED = [
    ("page", "Bind $onPageLoad ['refresh'] on EVERY datasource-backed control (dropdown/vc/tile/table/chart/Custom).",
     "Otherwise the filter/VC chain never initializes and the page loads empty."),
    ("page", "A filter dropdown's valueField = the raw KEY column downstream views filter on (name, period_id, participant_id); displayField = the human label.",
     "Downstream views do WHERE key = :var; using a decorated label as the value returns no data."),
    ("page", "Dynamic / variable-column data => a `table` bound to the view, never a Custom card. N fixed-field richly-styled measure cards MAY be Custom at layoutSize 33.33.",
     "Custom (controlData HTML) renders only a fixed, known field set."),
    ("page", "A dropdown that sets its own variable binds its default channel with [assignCurrentVariable, refresh].",
     "Assign the current selection into the variable, then re-query."),
    ("page", "Every BIND channel must have a CREATE producer; a data control must subscribe every channel that sets a :param its view needs.",
     "Dangling channels and unsatisfied params break the page and fail the gate."),
    ("page", "PageLoader: showLoader on $onPageLoad; hideLoader on an EARLY channel that always fires on load (the period/init-filter channel, e.g. current_period_select) — NOT the deepest chain channel; never a refresh handler.",
     "Hiding on a deep channel (master_position_id, a table ready-signal) that may never complete leaves the loader spinning forever."),
    ("page", "Role/conditional sections use hidden:true by default and are revealed by a role variable.",
     "e.g. show team components only for Manager/Leader."),
    ("query", "Reuse an existing catalog view before authoring; bind only real columns/params from the schema + catalog.",
     "Avoids duplicate views and hallucinated columns."),
    ("query", "xc_participant & xc_position need effective-date overlap joins (xc_position also incent_st/end); banned: COALESCE/LEAST/GREATEST/IFNULL/LIMIT/Empty; no || in strict context.",
     "These are the xSQL lint rules; obey up front."),
    ("query", "Never use correlated subqueries or reference an OUTER alias inside a subquery JOIN...ON (Oracle ORA-00904 invalid identifier). Use single-level joins. For the position hierarchy use xc_position.parent_position_id (children) and a second self-join for grandchildren.",
     "Xactly/Oracle cannot resolve outer correlations in a subquery ON clause; also a 504 risk."),
    ("architect", "Use the same variable name for the same concept across all pages (v_period, v_master_participant_id, v_master_position_id, v_year_number).",
     "So filters wire cleanly app-wide."),
    ("all", "Never invent a pageDefinitionId — it comes from the user's created page and is passed through verbatim.",
     "A generated id orphans the page."),
    ("all", "Output convention: the design page is emitted as JSON; all datasource queries AND workflows are emitted as xSQL (.sql) files, not JSON envelopes.",
     "Matches the Extend authoring workflow (paste xSQL into the query editor); import only the page JSON."),

    # --- Xactly official BPs, 2026-09-16 (knowledge/xactly_extend_best_practices.md) ---
    ("all", "S1 App schema default is $framework (EXTEND_DEFAULT_SCHEMA). Fully qualify every object: $framework.* for app tables/queries, xactly.* for Incent facts. Unqualified Incent names fail after Oct 2026.",
     "Team standard 2026-09-16 — Builder schema drop-down and assembler default to $framework."),
    ("query", "Q18 Do NOT use ShowQuotaAttainment() for employee-facing attainment, payout, or MBO. Build from xactly.xc_quota_assignment + credits/commission with period_correctness R1–R5 (cookbook Pattern A).",
     "Official Xactly BP: known calculation discrepancies vs raw tables."),
    ("query", "Q10 Never JOIN xactly.xc_part_user_assignment to dedupe participants — it can bypass row-level security on xc_participant. Use DISTINCT on xc_participant; test via manager impersonation.",
     "Official BP — JOIN strips manager filters and returns all employees."),
    ("query", "Q8 Avoid deep query-in-query nesting (production perf #1). Allowed exception: one parameterless helper view that collapses a repeated domain rule (cookbook Rule 12).",
     "Official BP — nested queries cascade-break and hide cost."),
    ("query", "Q14 Boolean/flag filters use integer 1/0 or string 'Y'/'N'/'1' — never true/false keywords. Flag columns are often string(1).",
     "Official BP + runtime D2."),
    ("query", "Q13 Static table and column names in DDL/DML — no :v_table / :v_col interpolation (breaks app export).",
     "Official BP — exporter misclassifies dynamic DDL as physical tables."),
    ("query", "Q11 Conditional single-row insert: INSERT…SELECT…FROM Empty() WHERE…NOT IN (…). Empty() is for DML/workflow only — still banned in strict VC/whereClause.",
     "Official BP — ANSI WHERE NOT EXISTS does not work in xSQL."),
    ("page", "C2 Bind Custom Datasource directly — never push data into Custom via Variable Configurator events (render race).",
     "Official BP — VC event order vs component render is non-deterministic."),
    ("page", "C3 Never use hidden controls as layout spacers. Platform 2026: hidden no longer reserves space. Use empty text/padding; hidden only for real show/hide.",
     "Official BP — layouts that relied on hidden spacers broke after the 2026 update."),
    ("page", "C5 Grid loads ≤1000 rows initially then lazy-loads. Bulk actions and totals hit the underlying table/query, not rendered grid rows.",
     "Official BP."),
    ("page", "V1–V2 Page-scoped component variables only (no global set varname). Seed every query :param on $onPageLoad via VC before first refresh. Audit with show variables;.",
     "Official BP — globals collide across sessions; uninitialized params error on load."),
    ("architect", "W2–W5 Workflows: pass named page vars into XFlow (not session); incent synchronous … when chained; batch 200–500 with checkpoint log; schedules in UTC; no xFlow→xFlow calls.",
     "Official BP — async races, 20min timeout, no native cron."),
    ("architect", "I1 CAE PeriodName must match a real xactly.xc_period name — territory/model strings silently assign zero territories.",
     "Official BP."),

    # --- gold comp dashboard shape, 2026-09-16 (knowledge/gold_comp_dashboard_shape.md) ---
    ("page", "Comp dashboard: linear VC spine ending in data_ready; PageLoader hideLoader on data_ready; seed v_lock_status / v_credit_search / v_measure on $onPageLoad.",
     "Finalized seller gold 1af96141… — fan-out VCs race; unbound seeds error on first query."),
    ("page", "Comp dashboard: one measure MATRIX Custom (all measures × credits/quota/attainment/commission/released/pending), not N separate measure tiles.",
     "Gold scorecard shape — separate tiles diverged from the approved design."),
    ("page", "Comp dashboard: supplemental SPIFF/Bonus/PPP/Draw as four Customs at layoutSize 25; payout-by-quarter as its own table with blank title under a header Custom.",
     "Gold layout — period R4 one line per quarter; R9 title once."),
    ("page", "Comp dashboard: measure pills Custom + pick VCs CREATE measure_select; trend percent-only; credit tabs bind $onTabOpen and data_ready; team_show/team_hide with shouldRenderHidden true.",
     "Gold interaction + R11/R13/R14."),
    ("architect", "Deliver only via app_assembler.write_bundle + pack_bundle. For app_class comp_dashboard run gate/check_gold_shape.py against evals/golden/comp_dashboard/shape_manifest.json before pack.",
     "Hand-zip and ungated JSON are how ClaimRequest and early seller drafts failed import/PRD."),
    ("all", "After each generated app: add lessons for every live defect (knowledge_base add) and follow knowledge/training_loop.md. Promote scrubbed golds under evals/golden/<app_class>/.",
     "Training compounds only when defects become seeds + gates."),

    # --- period correctness, 2026-09-04 call (knowledge/period_correctness_rules.md) ---
    ("query", "R1 Quota = the version EFFECTIVE FOR THE SELECTED PERIOD, never 'the latest'. Filter effective-window overlap (qstart.start_date <= period.end_date AND qend.end_date >= period.start_date) AND pin qstart.start_date = MAX(qstart.start_date) over the same overlap.",
     "Two overlapping versions both land in the SUM and the quota doubles (a rep's Q1 quota rendered as the sum of both versions). The overlap test alone is usually enough; the MAX pin is what makes doubling structurally impossible."),
    ("query", "R2 Quotas load CUMULATIVE (QTD/YTD), grain-aware: PERIOD-grain SUM ordinals <= selected quarter (after R1 picks one version per quarter); YEAR-grain uses ordinal/4 proration and must NOT also sum across quarters. Never invent annual_quota/4 when the pivot already carries period amounts; never call a single PERIOD-grain quarter row 'QTD'.",
     "PERIOD grain mis-read as 'row at quarter' shipped QTD = this quarter only (2026-09-09). YEAR grain summed across quarters multiplies. annual/4 was a live BXO defect."),
    ("query", "R3 Historical credits are NOT recoverable once PPAs are processed (they load onto the original incentive date). Do not reconstruct: ship a :v_lock_status gate ('current' vs 'as_paid') plus a visible reporting-basis selector.",
     "Source the as-paid branch from the BATCH NAME, not created_date -- a reset/recalc rewrites created_date and silently reclassifies history. Target state is a processing-period DATE column on the order load."),
    ("query", "R4 Commission != payment. Commission is running YTD earnings (xc_commission); payment is the discrete per-period release (xc_payment). Show both; give releases one line per quarter (Released Q1 / Released Q2 / Pending Q3).",
     "Annual plans calculate YTD commission on YTD performance; the payment is that minus what was already released. A page showing only payment cannot be reconciled by a rep."),
    ("query", "R5 Commission attribution is two-part: rows carrying quota_name (Earned) UNION rows whose rule_name contains 'previous' and carry NO quota (True-up). Normalise both in one helper view to measure_name + commission_kind.",
     "Miss the true-up half and every YTD commission is overstated by the whole negation. Match '%revious%' -- case varies."),

    # --- composition & canvas intake, 2026-09-04 ---
    ("query", "A view over ~300 lines does not run. Hoist any rule that would repeat into a PARAMETERLESS helper view keyed by the columns consumers filter on; leaves bind :params and stay short.",
     "The v3 quota rule appeared 11 times written naively. Four helpers took the longest view from 140 to 95 lines, and correctness became one edit in one place. Keep helpers parameterless -- do not rely on bind propagation into a nested view."),
    ("page", "Chain the bootstrap VCs LINEARLY, one per link. Two VCs bound to the same upstream event have no ordering guarantee between them.",
     "seller_team_leaderboard binds :v_month_start_date; month_start_date and default_quarter both hung off current_period_id, so the leaderboard could fire with the month unresolved."),
    ("page", "Seed every :param that no dropdown sets on load with a static VC (useStaticValue:true, staticValue:'<const>', fired on $onPageLoad).",
     "Otherwise the first query runs with an unbound param. v3 seeds v_lock_status='current' and v_credit_search=''."),
    ("page", "Show/hide gates come in complementary PAIRS, both wired: team_show -> ['show'], team_hide -> ['hide'], target shouldRenderHidden:true. Default hidden, show on proof.",
     "Default-visible-and-hide-on-proof leaves the section exposed to the wrong audience whenever the gate view returns zero rows."),
    ("page", "Every data control INSIDE a tab must bind $onTabOpen -> refresh in addition to its filter subscriptions.",
     "A tab child is not rendered until the tab opens, so it misses every event broadcast before that."),
    ("page", "Working from an HTML canvas: build the VARIABLE INVENTORY before emitting any control -- every displayed value maps to a view column, a filter var, or static copy.",
     "The one thing that forces a second pass is discovering mid-emit that a control needs a variable nothing produces. See knowledge/canvas_to_extend_playbook.md."),
    ("page", "A variable a control OWNS but nothing consumes fails the render gate (a selector that changes nothing). Either delete the control or give it a guard that references it (validationXsql ':v_x=1').",
     "v3 inherited three dead variables from v2: v_session_id, v_year_number, v_team_hide."),

    # --- runtime data defects, 2026-09-05..09 (knowledge/runtime_data_defects.md) ---
    ("query", "D1 Enrichment joins must collapse to one row per business key before any SUM. Dedup xc_order_stage / xc_customer with GROUP BY + Max(...); verify enrichment COUNT(*) equals spine credit COUNT(*).",
     "Joining order_stage on (order_code, item_code) measured 3.4x fan-out and inflated every SUM(amount) in 13 consumers (2026-09-09)."),
    ("query", "D2 Flag columns (IS_RELEASED, IS_ACTIVE) are string(1): compare IN ('1','Y') / = '1', never = 1. Pending payout = complement of released so the two always total.",
     "Numeric compares matched nothing — released AND pending both shipped $0.00 (2026-09-09)."),
    ("query", "D4 Period predicates must be symmetric across credits / commission / payment. Use the same overlap or start-date-in-range shape; never a stricter 'period wholly inside window' test on one fact only.",
     "Commission required wholly-contained periods while credits used start-date overlap — every coarser-than-monthly commission row went to $0 (2026-09-09)."),
    ("query", "D5 A control that binds a datasource the bundle does not ship renders empty forever (simulate_events S8 ERROR). A shipped query with no consumer is drift (S9 WARN). Run import_ready + simulate before delivery.",
     "ClaimRequest 2026-09-05 passed page gates and still would not import; Seller v3.4 stranded three queries after a layout change."),

    # --- shipped-dashboard review, 2026-08-15 (knowledge/dashboard_render_defects.md) ---
    ("query", "Bind params directly: `col = :v_x`. ToNumber() is banned; ToString(col)/ToChar(col) in a predicate is banned. Type the param via the query object's variables[].dataType.",
     "Casting in the predicate defeats the index; the type belongs in the declaration, not the SQL. (user directive 2026-08-15)"),
    ("query", "No rownum / RowNumber() / LIMIT. Get one row by aggregating (SELECT Nvl(MAX(id),0) ...) or pick one of many with a non-correlated IN (SELECT ...).",
     "The aggregate also guarantees a row when nothing matches, which is what stops the downstream 404/undefined."),
    ("query", "Scope facts on participant_id, never eff_participant_id.",
     "eff_participant_id is not what these dashboards scope on. (user directive 2026-08-15)"),
    ("query", "A view behind a card/tile/Custom/resolver MUST always return exactly one row: aggregate with no GROUP BY, every output wrapped in Nvl().",
     "R1: a zero-row view renders the literal string 'undefined' on the page — four summary tiles shipped that way."),
    ("query", "Nvl goes innermost, inside the formatting: Concat('$', FormatNumber(Nvl(x,0), '#,##0')). Never Nvl(Concat(...)).",
     "R2: a NULL inside a Concat ships a bare '%' or '$' with no number — a shipped measure card rendered as just '%'."),
    ("query", "Never hardcode a measure/component/credit-type name in a predicate — parameterize it (:v_measure) or resolve it from the list view that renders the label.",
     "R3/R4: a literal that doesn't match the tenant silently returns 0, which looks like real data — a shipped breakdown table had every component column at 0 beside a correct nine-figure total."),
    ("query", "A breakdown column and its total must come from ONE rowset: SUM(CASE WHEN key = value THEN amount ELSE 0 END), not separately filtered sub-selects.",
     "R4: independently filtered parts can all be 0 while the total is right — nothing catches it."),
    ("query", "One card = one period grain. The headline % must be computed from the same credits/quota pair the card displays; don't mix a yearly attainment headline with QTD rows.",
     "R5: the Revenue card showed 43% above 5.3M credits / 3.06M quota (= 175%)."),
    ("query", "A trend view returns one row per period in the range, zero-filled: the period table is the spine, LEFT JOIN the facts. All plotted series share one unit.",
     "R14: the chart collapsed to 2 bars and put credit amounts (millions) on the same axis as attainment %."),
    ("query", "A deal/detail ledger excludes engine trigger/adjustment rows and GROUPs BY exactly the displayed columns.",
     "R6/R7: 'Trigger1_QGRP3_...' rows and duplicated accounts shipped in the ledger and portfolio tables."),
    ("page", "Title once: a section label OR the data control's title, never both.",
     "R9: the page rendered 'Deal Ledger Details' immediately above 'Table - Deal Ledger Details'."),
    ("page", "A table's height is data-driven: cap itemsPerPage (~25) and set maxHeight, and give it its own row.",
     "R10: 200-row unbounded tables rendered on top of the sections below them."),
    ("page", "A variable that a selector sets must be consumed — by the dependent views' :params, the controls' channels, AND the header/subtitle copy.",
     "R13: the Measure filter said 'Sales Profitability' while the chart below stayed captioned 'Measure: Revenue'."),
    ("page", "Role gating is wiring, not copy: derive v_role, mark the section's controls hidden:true, drive visibility from the role channel.",
     "R11: an IC saw the whole team section, subtitled 'Visible for Managers & Leaders · Role: IC'."),
    ("page", "Never ship placeholder copy (TODO / Coming soon / Verification in progress / undefined) in controlData, and never draw a meter/progress bar whose fill isn't bound.",
     "R15: 'Verification in progress' and an empty progress bar under a 96.77% attainment shipped to the customer."),
    ("page", "Every visual row's layoutSizes must sum to ~100 (allowed: 100, 66.66, 50, 33.33, 25, 16.66). Size by sibling count: 2→50, 3→33.33, 4→25, 6→16.66. Tables/charts/labels/search inputs are layoutSize 100 alone. Five filters → two rows (3+2), never five×16.66. Set layoutSize explicitly — do not leave dropdown/tile at default 25 when only two share a row.",
     "R16: half-empty KPI rows and an 83%-wide filter bar make the page look unaligned even when wiring is correct."),

    ("architect", "A production Extend app export ships more than pages+queries: ADLC.json (application, queries, workflows, pageDefinitions, policySets, tables, compositeComponents, applicationTags, agents), app/Application.json (landingPageId + per-section accessRoles[]), app/<pageDefinitionId>.json (with versionName), queries/<schema>/<name>.json query objects ({name,schemaName,xsql,variables[]}), policy_sets/ (row/role access), workflows/, tables/.",
     "Grounded on the EFM Goals&Guarantees + Certification reference exports; a bundle missing policy sets or Application nav imports but doesn't work. Note: a policy-set PREDICATE is the one place a current-user lookup legitimately appears (row-level security) — query scoping still uses the selected-rep chain."),

    # --- replacements for the RETIRED lessons below ---
    ("query", "Quota value = SUM(xactly.xc_quota_assignment.amount) (NOT xc_quota.quotavalue), joined to xc_period on xqa.period_id with the period-hierarchy OR: (p.name = :v_quarter OR p.parent_period_id IN (SELECT period_id FROM xactly.xc_period WHERE name = :v_quarter)). Resolve quota_id by name with a non-correlated IN. Cross-join the single-row credit and quota rowsets with ON 1 = 1 in view context.",
     "xc_quota.quotavalue is not the assigned quota; the assignment amount is, and it must be period-hierarchy scoped. (rownum removed 2026-08-15)"),
    ("query", "Dashboards must render on load: give every OPTIONAL filter an All sentinel branch — AND ( :v_x = 'All' OR col = :v_x ) — and seed the filter var default to 'All'. Required resolved ids need no guard and no cast: the Pattern B/C resolvers are aggregates that always return one row (0 when unresolved), so the view returns empty instead of erroring.",
     "Filters with no default and no All branch are the #1 cause of 'undefined/empty on load'. (ToString guard removed 2026-08-15)"),
    ("query", "Scope a person-filtered view ONLY through the selected-rep chain: rep dropdown (:v_participant) -> :v_master_participant_id -> :v_master_position_id. Never LookupCurrentUserMasterParticipantId()/MasterPositionId()/any LookupCurrentUser* — for ICs either.",
     "User-context lookups bind to the logged-in user, not the selected rep, which breaks the rep picker and every admin 'view any rep' flow."),
]


# Lessons that later directives OVERTURNED. Matched as substrings and deleted on every load, so a
# team DB that learned the old rule stops injecting it. Add the replacement to SEED in the same edit.
# Each entry matches the START of the overturned lesson (a prefix, not any mention), so a rule that
# merely *names* the banned construct in order to ban it — or a lesson about a different topic that
# cites it — is never swept up.
RETIRED = [
    ("A scalar resolver view", "no rownum — aggregate to one row (2026-08-15)"),
    ("Emit numeric equality filters on resolver-driven", "no predicate casts — bind directly + declare dataType (2026-08-15)"),
    ("IC self-view filters by the built-in current-user lookups", "user-context lookups are banned; resolve via the selected-rep chain"),
    ("R2 Quotas load CUMULATIVE (QTD/YTD): read the quota row AT the selected period",
     "grain-aware cumulation 2026-09-09 — PERIOD sums ordinals, YEAR prorates"),
    ("Attainment %, credited amount toward quota, and payout are ENGINE outputs",
     "official BP 2026-09-16 — do not use ShowQuotaAttainment for employee-facing comp; Pattern A from tables"),
    ("S1–S5 Customer-defined schema per app",
     "team standard 2026-09-16 — app schema default is $framework"),
]
# Rules replaced in place (same opening, corrected body): retire only the version that still carries
# the bad construct, identified by (prefix, offending substring).
SUPERSEDED = [
    ("Quota value = SUM", "rownum", "no rownum — use a non-correlated IN (2026-08-15)"),
    ("Dashboards must render on load", "ToString(col)", "no predicate casts (2026-08-15)"),
]


def _retire(c):
    """Delete overturned lessons. Returns [(rule, reason)] of what was removed."""
    removed = []
    for frag, reason in RETIRED:
        for r in c.execute("SELECT id, rule FROM lessons WHERE rule LIKE ?", (f"{frag}%",)).fetchall():
            c.execute("DELETE FROM lessons WHERE id = ?", (r["id"],))
            removed.append((r["rule"][:80], reason))
    for frag, offending, reason in SUPERSEDED:
        for r in c.execute("SELECT id, rule FROM lessons WHERE rule LIKE ?", (f"{frag}%",)).fetchall():
            if offending in r["rule"]:
                c.execute("DELETE FROM lessons WHERE id = ?", (r["id"],))
                removed.append((r["rule"][:80], reason))
    return removed


def _ensure_seeded():
    """Insert any SEED lesson the DB doesn't have yet. Runs every call (INSERT OR IGNORE on the
    UNIQUE(scope, rule) index) so a team DB created before a seed was added still picks it up —
    seeding only when the table was empty silently stranded new rules on existing databases."""
    c = db.connect()
    try:
        removed = _retire(c)
        c.executemany("INSERT OR IGNORE INTO lessons(ts,scope,rule,why,source) VALUES(?,?,?,?,?)",
                      [(time.time(), s, r, w, "seed") for s, r, w in SEED])
        c.commit()
        for rule, reason in removed:
            print(f"[knowledge_base] retired lesson ({reason}): {rule}…", file=sys.stderr)
    finally:
        c.close()


def add_lesson(scope: str, rule: str, why: str = "", source: str = "iteration") -> dict:
    """Add a distilled lesson learned this iteration. Deduplicates on (scope, rule)."""
    _ensure_seeded()
    scope = scope if scope in SCOPES else "all"
    c = db.connect()
    try:
        c.execute("INSERT OR IGNORE INTO lessons(ts,scope,rule,why,source) VALUES(?,?,?,?,?)",
                  (time.time(), scope, rule.strip(), why.strip(), source))
        c.commit()
    finally:
        c.close()
    return {"scope": scope, "rule": rule.strip(), "why": why.strip(), "source": source}


def all_lessons() -> list:
    _ensure_seeded()
    c = db.connect()
    try:
        return [dict(r) for r in c.execute("SELECT scope,rule,why,source,ts FROM lessons ORDER BY id")]
    finally:
        c.close()


def render(scope: str, max_chars: int = 9000) -> str:
    """Lessons for a scope (+ 'all'), formatted for prompt injection. '' if none.
    Truncates on whole lines — a half-written rule is worse than a missing one."""
    rows = [r for r in all_lessons() if r["scope"] in (scope, "all")]
    if not rows:
        return ""
    out, used = ["LEARNED RULES (accumulated across builds — apply them):"], 0
    for r in rows:
        line = f"- {r['rule']}" + (f"  ({r['why']})" if r.get("why") else "")
        if used + len(line) > max_chars:
            out.append(f"- … {len(rows) - (len(out) - 1)} more rules omitted (raise max_chars)")
            break
        out.append(line)
        used += len(line)
    return "\n".join(out)


if __name__ == "__main__":
    import json
    if len(sys.argv) >= 2 and sys.argv[1] == "add" and len(sys.argv) >= 4:
        print(json.dumps(add_lesson(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ""), indent=2))
    else:
        print(render(sys.argv[2] if len(sys.argv) > 2 else "page"))
