#!/usr/bin/env python3
"""
page_designer.py — Stage 3: design one Extend dashboard page from a finalized FRD page-spec.

page-spec (text) + datasource names + created-page shell
  -> grounding: each view's real columns + params (+ optional table schema)
  -> Opus 4.8 emits a control list (kinds/wiring), honoring the Custom dynamic-column rule
  -> build_extend_page (deterministic, exact envelope)   [from extend-mcp]
  -> validate_extend_page (structure + wiring + catalog-aware binding/param gate)
  -> self-correct loop -> PASS page JSON.

`assemble(controls, shell)` (build + validate) is deterministic and testable with NO API key.
Only `design_page()` calls Opus (needs ANTHROPIC_API_KEY). Build must be unblocked by the FRD gate first.

CLI (deterministic assemble of a hand control list):
    python page_designer.py --assemble controls.json --title "My Page" --id pg_1
"""
import os, re, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schema_tools as st

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "gate"))  # vendored deterministic gate
import extend_build            # build_page(controls, shell), validate_page(page, shell, catalog)
import xsql_author            # (kept import parity; not required here)

MODEL = "claude-opus-4-8"
PROMPT_PATH = os.path.join(os.path.dirname(HERE), "prompts", "30_page_designer.md")
CATALOG = st._CATALOG
MAX_ATTEMPTS = 3


# ---- grounding -------------------------------------------------------------------------------
def build_grounding(datasources: list[str], tables: list[str] | None = None) -> str:
    blocks = []
    for name in datasources or []:
        v = st.get_view(name)
        if v:
            blocks.append(f"VIEW {v['name']}  (schema {v.get('schema')})\n"
                          f"  columns: {v.get('columns', [])}\n  params: {v.get('params', [])}")
        else:
            r = st.resolve_view([name])  # maybe they passed a column; surface a candidate
            blocks.append(f"VIEW {name}: NOT in catalog." +
                          (f" closest: {r['name']} cols={r['columns']}" if r.get("found") else " author it first."))
    for t in tables or []:
        blocks.append(st.render_schema(t))
    return "\n\n".join(blocks) or "(no datasources named — the page may be static labels only)"


# ---- deterministic assemble + gate (no API key) ----------------------------------------------
def assemble(controls: list[dict], shell: dict) -> dict:
    """Build the page JSON and gate it (structure/wiring + render quality).
    Returns {page, verdict, errors, warnings}."""
    page = extend_build.build_page(controls, shell)
    gate = extend_build.validate_page(page, shell, catalog=CATALOG)
    errors, warnings = list(gate["errors"]), list(gate["warnings"])

    # render-quality gate: the defects that pass a structural check and still look broken on screen
    # (duplicate headings, unbounded tables, placeholder copy) — see knowledge/dashboard_render_defects.md
    import tempfile, check_page_render as cpr
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(page, f)
        tmp = f.name
    try:
        cpr.check_page(tmp, errors, warnings)
    finally:
        os.unlink(tmp)

    verdict = "FAIL" if errors else gate["verdict"]
    return {"page": page, "verdict": verdict, "errors": errors, "warnings": warnings}


# ---- LLM design loop -------------------------------------------------------------------------
_JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.S | re.I)


def _extract_controls(text: str):
    m = _JSON_BLOCK.search(text)
    raw = m.group(1) if m else text
    try:
        data = json.loads(raw.strip())
        return data if isinstance(data, list) else data.get("controls")
    except Exception:
        return None


def _call_opus(system, messages):
    import llm  # provider-agnostic
    return llm.complete(system, messages, max_tokens=4000)


PAGE_ID_PROMPT = ("Please provide the Extend **pageDefinitionId** (create the page in Extend first and paste "
                  "its id). The designer will not generate one — the id must match the real page.")


class MissingPageId(ValueError):
    """Raised when no user-provided pageDefinitionId is available."""


def _load_examples(kind: str) -> str:
    try:
        import feedback_store
        return feedback_store.few_shot(kind)
    except Exception:
        return ""


def _load_knowledge(scope: str) -> str:
    try:
        import knowledge_base
        return knowledge_base.render(scope)
    except Exception:
        return ""


def design_page(page_spec: str, datasources: list[str], shell: dict | None = None,
                tables: list[str] | None = None, dry: bool = False, examples=None) -> dict:
    """Design + gate one page. shell = {pageDefinitionId, title, versionName?}. The pageDefinitionId is
    REQUIRED and must come from the user (the Extend created-page shell) — never generated."""
    shell = dict(shell or {})
    if not shell.get("pageDefinitionId"):
        # Do not fabricate an id. Ask the user for it.
        raise MissingPageId(PAGE_ID_PROMPT)
    shell.setdefault("title", "Untitled Page")

    system = open(PROMPT_PATH).read()
    if examples is None:
        examples = _load_examples("page")
    user = (f"PAGE SPEC:\n{page_spec}\n\nGROUNDING:\n{build_grounding(datasources, tables)}\n\n"
            f"Page title: {shell['title']}. Emit the control list.")
    if examples:
        user = f"{examples}\n\n{user}"
    knowledge = _load_knowledge("page")
    if knowledge:
        user = f"{knowledge}\n\n{user}"
    if dry:
        return {"dry": True, "user_message": user, "shell": shell}

    messages = [{"role": "user", "content": user}]
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        text = _call_opus(system, messages)
        controls = _extract_controls(text)
        if not controls:
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": "Return exactly one ```json array of control objects."}]
            continue
        try:
            res = assemble(controls, shell)
        except Exception as e:
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"build failed: {e}. Fix the control list and resend."}]
            continue
        last = {"controls": controls, "page": res["page"], "verdict": res["verdict"],
                "errors": res["errors"], "warnings": res["warnings"], "attempts": attempt}
        if res["verdict"] == "PASS":
            return last
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "The gate FAILED:\n" +
                      "\n".join(f"- [{e['category']}] {e['problem']} -> {e['fix']}" for e in res["errors"]) +
                      "\nReturn a corrected ```json control list."}]
    return last or {"verdict": "FAIL", "errors": [{"problem": "no controls produced"}], "attempts": MAX_ATTEMPTS}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--assemble", help="path to a JSON control list (deterministic build+gate, no key)")
    ap.add_argument("--title", default="My Page")
    ap.add_argument("--id", default=None)
    a = ap.parse_args()
    if a.assemble:
        if not a.id:
            sys.exit("--id is required: provide the Extend pageDefinitionId (the designer never generates one).")
        controls = json.load(open(a.assemble))
        shell = {"pageDefinitionId": a.id, "title": a.title}
        res = assemble(controls, shell)
        print("VERDICT:", res["verdict"])
        for e in res["errors"]:
            print("  ERR", e)
        for w in res["warnings"]:
            print("  WARN", w.get("note"))
        print(json.dumps(res["page"], indent=2)[:1500])
    else:
        print(__doc__)
