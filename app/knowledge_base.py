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
