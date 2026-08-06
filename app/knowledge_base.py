#!/usr/bin/env python3
"""
knowledge_base.py — the builder's accumulating knowledge (user point 5, "learn on each iteration").

Two complementary learning surfaces:
  • feedback_store.py — accepted input→output EXAMPLES (few-shot; style/imitation).
  • knowledge_base.py — distilled RULES/LESSONS (curated guardrails; injected into every build).

Each build iteration can add a lesson (from a correction or a discovered gap); every future build of the
same scope gets that lesson prepended to its prompt, so knowledge compounds instead of being re-learned.

Store: knowledge/lessons.jsonl (override EXTEND_KNOWLEDGE_PATH). Seeded on first use with what the project
has already learned. Scopes: "query", "page", "architect", "frd", "all".
Stdlib only — no API key.

CLI:
    python knowledge_base.py list [scope]
    python knowledge_base.py add <scope> "<rule>" "<why>"
"""
import os, json, time

STORE = os.path.expanduser(os.environ.get(
    "EXTEND_KNOWLEDGE_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge", "lessons.jsonl")))

SCOPES = {"query", "page", "architect", "frd", "all"}

SEED = [
    # page-design lessons (hard-won this project)
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
    # query lessons
    ("query", "Reuse an existing catalog view before authoring; bind only real columns/params from the schema + catalog.",
     "Avoids duplicate views and hallucinated columns."),
    ("query", "xc_participant & xc_position need effective-date overlap joins (xc_position also incent_st/end); banned: COALESCE/LEAST/GREATEST/IFNULL/LIMIT/Empty; no || in strict context.",
     "These are the xSQL lint rules; obey up front."),
    # architect lessons
    ("architect", "Use the same variable name for the same concept across all pages (v_period, v_master_participant_id, v_master_position_id, v_year_number).",
     "So filters wire cleanly app-wide."),
    # global
    ("all", "Never invent a pageDefinitionId — it comes from the user's created page and is passed through verbatim.",
     "A generated id orphans the page."),
]


def _ensure_seeded():
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    if not os.path.exists(STORE) or os.path.getsize(STORE) == 0:
        with open(STORE, "w", encoding="utf-8") as f:
            for scope, rule, why in SEED:
                f.write(json.dumps({"ts": time.time(), "scope": scope, "rule": rule,
                                    "why": why, "source": "seed"}, ensure_ascii=False) + "\n")


def add_lesson(scope: str, rule: str, why: str = "", source: str = "iteration") -> dict:
    """Add a distilled lesson learned this iteration. Deduplicates on (scope, rule)."""
    _ensure_seeded()
    scope = scope if scope in SCOPES else "all"
    for r in all_lessons():
        if r["scope"] == scope and r["rule"].strip() == rule.strip():
            return r  # already known
    rec = {"ts": time.time(), "scope": scope, "rule": rule.strip(), "why": why.strip(), "source": source}
    with open(STORE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def all_lessons() -> list:
    _ensure_seeded()
    out = []
    with open(STORE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


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
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "add" and len(sys.argv) >= 4:
        print(json.dumps(add_lesson(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ""), indent=2))
    else:
        scope = sys.argv[2] if len(sys.argv) > 2 else "page"
        print(render(scope))
