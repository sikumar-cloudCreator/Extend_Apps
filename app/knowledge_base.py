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
]


def _ensure_seeded():
    c = db.connect()
    try:
        if c.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 0:
            c.executemany("INSERT OR IGNORE INTO lessons(ts,scope,rule,why,source) VALUES(?,?,?,?,?)",
                          [(time.time(), s, r, w, "seed") for s, r, w in SEED])
            c.commit()
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


def render(scope: str, max_chars: int = 3000) -> str:
    """Lessons for a scope (+ 'all'), formatted for prompt injection. '' if none."""
    rows = [r for r in all_lessons() if r["scope"] in (scope, "all")]
    if not rows:
        return ""
    lines = ["LEARNED RULES (accumulated across builds — apply them):"]
    for r in rows:
        lines.append(f"- {r['rule']}" + (f"  ({r['why']})" if r.get("why") else ""))
    return "\n".join(lines)[:max_chars]


if __name__ == "__main__":
    import json
    if len(sys.argv) >= 2 and sys.argv[1] == "add" and len(sys.argv) >= 4:
        print(json.dumps(add_lesson(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ""), indent=2))
    else:
        print(render(sys.argv[2] if len(sys.argv) > 2 else "page"))
