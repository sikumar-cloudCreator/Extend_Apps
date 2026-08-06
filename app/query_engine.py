#!/usr/bin/env python3
"""
query_engine.py — the Extend LLM query engine (queries-first foundation).

request (plain English + optional tables/columns/params)
  -> gather grounding: schema_lookup(tables) + reuse candidates (both sources)
  -> Opus 4.8 authors xSQL (or picks REUSE)
  -> lint_xsql GATE -> self-correct loop
  -> return a PASS-ing view (or REUSE) with the params it needs.

The deterministic parts (grounding + lint) run with NO API key and are unit-testable.
Only the authoring step calls Anthropic (needs ANTHROPIC_API_KEY). Model: claude-opus-4-8.

CLI:
    python query_engine.py "credits by measure for a participant and period" \
        --tables xc_credit xc_credit_type xc_participant xc_period \
        --columns measure_name credits --params v_master_participant_id v_period
    python query_engine.py --dry ... # grounding + prompt only, no API call
"""
import os, re, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schema_tools as st

# The deterministic gate is vendored in ../gate (single source of truth for this repo).
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "gate"))
try:
    import xsql_author  # provides lint_xsql(sql, strict, declared_params)
    lint_xsql = xsql_author.lint_xsql
except Exception as e:  # pragma: no cover
    def lint_xsql(sql, strict=False, declared_params=None):
        return {"verdict": "UNKNOWN", "errors": [f"lint unavailable: {e}"], "warnings": []}

MODEL = "claude-opus-4-8"
PROMPT_PATH = os.path.join(os.path.dirname(HERE), "prompts", "10_query_writer.md")
MAX_ATTEMPTS = 3


# ---- grounding -------------------------------------------------------------------------------
def build_grounding(tables: list[str], needed_columns: list[str]) -> str:
    blocks = []
    for t in tables or []:
        blocks.append(st.render_schema(t))
    blocks.append(st.render_reuse_candidates(needed_columns or []))
    return "\n\n".join(blocks)


def build_user_message(request: str, tables, needed_columns, params, schema, view_name) -> str:
    hints = []
    if params:
        hints.append(f"Use these :params (declare them as page variables): {', '.join(':' + p for p in params)}")
    if view_name:
        hints.append(f"If authoring, name the view {schema}.{view_name}.")
    if needed_columns:
        hints.append(f"Requested output columns: {', '.join(needed_columns)}")
    return (f"REQUEST:\n{request}\n\n"
            f"GROUNDING:\n{build_grounding(tables, needed_columns)}\n\n"
            + ("\n".join(hints) if hints else ""))


# ---- gate ------------------------------------------------------------------------------------
_SQL_BLOCK = re.compile(r"```sql\s*(.*?)```", re.S | re.I)


def extract_sql(text: str) -> str | None:
    m = _SQL_BLOCK.search(text)
    if m:
        return m.group(1).strip()
    if re.search(r"\bCREATE\s+VIEW\b", text, re.I):  # unfenced fallback
        return text.strip()
    return None


def check(sql: str, declared_params: list[str] | None) -> dict:
    return lint_xsql(sql, strict=False, declared_params=declared_params)


# ---- LLM authoring (needs ANTHROPIC_API_KEY) -------------------------------------------------
def _call_opus(system: str, messages: list[dict]) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("pip install anthropic (in the extend-llm env) to run authoring")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("set ANTHROPIC_API_KEY to run authoring (grounding/lint work without it)")
    client = anthropic.Anthropic()
    resp = client.messages.create(model=MODEL, max_tokens=1500, system=system, messages=messages)
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _load_examples(kind: str) -> str:
    try:
        import feedback_store
        return feedback_store.few_shot(kind)
    except Exception:
        return ""


def generate_query(request: str, tables=None, needed_columns=None, params=None,
                   schema="demo", view_name=None, dry=False, examples=None) -> dict:
    """Author (or reuse) a lint-passing xSQL view for the request. Few-shot examples from the feedback
    store (point 5 learning loop) are auto-injected unless `examples` is passed ('' to disable)."""
    system = open(PROMPT_PATH).read()
    if examples is None:
        examples = _load_examples("query")
    user = build_user_message(request, tables, needed_columns, params, schema, view_name)
    if examples:
        user = f"{examples}\n\n{user}"
    if dry:
        return {"dry": True, "system_prompt_path": PROMPT_PATH, "user_message": user}

    messages = [{"role": "user", "content": user}]
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        text = _call_opus(system, messages)
        # REUSE path
        mreuse = re.match(r"\s*REUSE\s+([A-Za-z0-9_]+)", text)
        if mreuse:
            v = st.get_view(mreuse.group(1))
            return {"action": "reuse", "view": mreuse.group(1), "found": bool(v),
                    "params": (v or {}).get("params", []), "attempts": attempt, "raw": text.strip()}
        sql = extract_sql(text)
        if not sql:
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": "Return exactly one ```sql CREATE VIEW block per the output contract."}]
            continue
        gate = check(sql, params)
        last = {"action": "author", "xsql": sql, "verdict": gate["verdict"],
                "errors": gate["errors"], "warnings": gate["warnings"],
                "params": params or sorted(set(re.findall(r":(\w+)", sql))), "attempts": attempt}
        if gate["verdict"] == "PASS":
            return last
        # self-correct: hand the gate errors back
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "The lint gate FAILED with:\n" +
                      "\n".join(f"- {e}" for e in gate["errors"]) +
                      "\nFix and return one corrected ```sql block."}]
    return last or {"action": "author", "verdict": "FAIL", "errors": ["no SQL produced"], "attempts": MAX_ATTEMPTS}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    ap.add_argument("--tables", nargs="*", default=[])
    ap.add_argument("--columns", nargs="*", default=[])
    ap.add_argument("--params", nargs="*", default=[])
    ap.add_argument("--schema", default="demo")
    ap.add_argument("--name", default=None)
    ap.add_argument("--dry", action="store_true", help="grounding + prompt only, no API call")
    a = ap.parse_args()
    out = generate_query(a.request, a.tables, a.columns, a.params, a.schema, a.name, dry=a.dry)
    print(json.dumps(out, indent=2))
