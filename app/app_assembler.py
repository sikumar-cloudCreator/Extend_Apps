#!/usr/bin/env python3
"""
app_assembler.py — Stage 4: assemble a full, deployable Extend application from a finalized FRD.

FRD -> architect (build-spec) -> per page: author/reuse xSQL views + design page JSON (both gated)
     -> bundle into the real Extend export layout + coverage/validation report.

Deployable layout (mirrors a real Extend export, e.g. SellerDashboard_INTX):
    ADLC.json                              # manifest
    app/Application.json                   # nav (sections -> pageDefinitionId)
    app/<pageDefinitionId>.json            # each page (from page_designer)
    queries/<schema>/<view>.json           # each datasource view
    tables/schemas/xactly/<xc_table>.json  # referenced base tables (from the xc_ dictionary)

Hard rules honored:
  - point 2: `session.guard_build()` must pass (FRD finalized) before anything is generated.
  - user id rule: every page needs a user-provided pageDefinitionId (page_id_map) — none are generated.

Deterministic bundling (ADLC/Application/query/table files + coverage report) needs NO API key and is tested.
Only architect() and the per-page Opus steps need ANTHROPIC_API_KEY.
"""
import os, re, sys, json, hashlib, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schema_tools as st
import query_engine as qe
import page_designer as pdz

MODEL = "claude-opus-4-8"
ARCH_PROMPT = os.path.join(os.path.dirname(HERE), "prompts", "40_architect.md")
DEFAULT_SCHEMA = os.environ.get("EXTEND_DEFAULT_SCHEMA", "demo")


# ---- deterministic bundle files (no API key) -------------------------------------------------
def _ent_id(kind: str, name: str) -> str:
    return kind + hashlib.md5(f"{kind}:{name}".encode()).hexdigest()[:30]


def query_file(view: dict) -> dict:
    """queries/<schema>/<name>.json content for a datasource view (view has name/schema/xsql)."""
    return {"savedInEditor": True, "isValid": True, "name": view["name"],
            "schemaName": view.get("schema", DEFAULT_SCHEMA), "xsql": view.get("xsql", ""), "properties": {}}


def table_schema_file(table: str) -> dict:
    """tables/schemas/xactly/<t>.json — generated from the xc_ dictionary (Incent-bound base table)."""
    t = table if table.startswith("xc_") else f"xc_{table}"
    return {"id": _ent_id("ent", t), "schemaName": "xactly", "tableName": t, "columns": [],
            "overwrite": False, "unlogged": False, "archive": False, "local": False,
            "temporary": False, "preserveRows": False, "selectionSet": False,
            "using": f"Incent(TableName='Incent.{t.upper()}');", "audited": False, "effectiveDated": False}


def application_json(app_name: str, icon: str, nav_pages: list[dict]) -> dict:
    """app/Application.json — nav sections point at each page's pageDefinitionId."""
    sections = [{"name": p["title"], "icon": p.get("icon", icon), "pageDefinitionId": p["pageDefinitionId"],
                 "description": "", "sections": [], "accessRoles": None, "privileges": None} for p in nav_pages]
    return {"applicationId": _ent_id("app", app_name), "applicationName": app_name, "icon": icon,
            "sections": sections, "accessRoles": [], "tagIds": [], "applicationState": "DRAFT",
            "applicationI18nFiles": []}


def adlc_json(view_names: list[tuple], page_ids: list[str], tables: list[str], workflows: list[str]) -> dict:
    """ADLC.json manifest. view_names = [(schema, name)]; page_ids = [pageDefinitionId]."""
    return {"application": "app/Application.json",
            "queries": sorted(f"queries/{s}/{n}.json" for s, n in view_names),
            "workflows": sorted(f"workflows/{w}.json" for w in workflows),
            "pageDefinitions": sorted(f"app/{pid}.json" for pid in page_ids),
            "policySets": None,
            "tables": {"schemas": sorted(f"tables/schemas/xactly/{t if t.startswith('xc_') else 'xc_'+t}.json"
                                         for t in tables)}}


def write_bundle(out_dir: str, app_name: str, icon: str, pages: list[dict],
                 views: list[dict], tables: list[str], workflows: list[dict] | None = None) -> dict:
    """Write the full deployable folder tree. pages = [{pageDefinitionId, title, page(json), icon?}]."""
    workflows = workflows or []
    os.makedirs(os.path.join(out_dir, "app"), exist_ok=True)
    # pages
    for p in pages:
        with open(os.path.join(out_dir, "app", f"{p['pageDefinitionId']}.json"), "w") as f:
            json.dump(p["page"], f, indent=2)
    # views
    view_names = []
    for v in views:
        schema = v.get("schema", DEFAULT_SCHEMA)
        d = os.path.join(out_dir, "queries", schema); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{v['name']}.json"), "w") as f:
            json.dump(query_file(v), f, indent=2)
        view_names.append((schema, v["name"]))
    # base tables
    if tables:
        d = os.path.join(out_dir, "tables", "schemas", "xactly"); os.makedirs(d, exist_ok=True)
        for t in tables:
            tn = t if t.startswith("xc_") else f"xc_{t}"
            with open(os.path.join(d, f"{tn}.json"), "w") as f:
                json.dump(table_schema_file(t), f, indent=2)
    # workflows (bodies are pass-through if provided)
    if workflows:
        d = os.path.join(out_dir, "workflows"); os.makedirs(d, exist_ok=True)
        for w in workflows:
            with open(os.path.join(d, f"{w['name']}.json"), "w") as f:
                json.dump(w.get("body", {"name": w["name"]}), f, indent=2)
    # application + manifest
    with open(os.path.join(out_dir, "app", "Application.json"), "w") as f:
        json.dump(application_json(app_name, icon, pages), f, indent=2)
    with open(os.path.join(out_dir, "ADLC.json"), "w") as f:
        json.dump(adlc_json(view_names, [p["pageDefinitionId"] for p in pages],
                            tables, [w["name"] for w in workflows]), f, indent=2)
    return {"out_dir": out_dir, "pages": len(pages), "views": len(views), "tables": len(tables),
            "workflows": len(workflows)}


def coverage_report(build_spec: dict, page_results: list[dict]) -> dict:
    """FRD-coverage + gate summary."""
    spec_pages = {p["name"] for p in build_spec.get("pages", [])}
    built = {r["name"] for r in page_results}
    all_pass = all(r.get("verdict") == "PASS" for r in page_results)
    return {"app_name": build_spec.get("app_name"),
            "pages_in_spec": len(spec_pages), "pages_built": len(built),
            "missing_pages": sorted(spec_pages - built),
            "all_pages_pass_gate": all_pass,
            "pages": [{"name": r["name"], "verdict": r.get("verdict"),
                       "errors": len(r.get("errors", [])), "needs_human": r.get("verdict") != "PASS"}
                      for r in page_results]}


def required_page_ids(build_spec: dict, page_id_map: dict) -> list[str]:
    """Page names still missing a user-provided pageDefinitionId."""
    return [p["name"] for p in build_spec.get("pages", []) if not (page_id_map or {}).get(p["name"])]


# ---- architect (Opus) ------------------------------------------------------------------------
def architect(frd_markdown: str) -> dict:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("pip install anthropic to run the architect")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("set ANTHROPIC_API_KEY to run the architect")
    system = open(ARCH_PROMPT).read()
    grounding = "REUSABLE VIEW CATALOG:\n" + "\n".join(
        f"  {v['name']}  params={v['params']}  columns={v['columns']}" for v in st.list_views())
    r = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=6000, system=system,
        messages=[{"role": "user", "content": f"FRD:\n{frd_markdown}\n\n{grounding}"}])
    text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
    m = re.search(r"```json\s*(.*?)```", text, re.S)
    return json.loads((m.group(1) if m else text).strip())


# ---- full assembly (orchestrates Opus steps) -------------------------------------------------
def assemble_app(build_spec: dict, page_id_map: dict, out_dir: str, session=None) -> dict:
    """Author views + design pages per the build-spec, then write the deployable bundle. Needs a key
    for the per-page Opus steps. Enforces the FRD finalize gate and the user-provided-id rule."""
    if session is not None:
        session.guard_build()  # point 2: refuse until FRD finalized
    missing = required_page_ids(build_spec, page_id_map)
    if missing:
        return {"status": "needs_page_ids", "pages_needing_ids": missing,
                "message": "Create these pages in Extend and provide their pageDefinitionIds."}

    all_views, all_tables, pages_out, results = {}, set(), [], []
    for p in build_spec["pages"]:
        pid = page_id_map[p["name"]]
        ds_names = [d["name"] for d in p.get("datasources", [])]
        # author any 'new' views (reuse ones already exist in the catalog)
        for d in p.get("datasources", []):
            if d.get("action") == "new" and d["name"] not in all_views:
                res = qe.generate_query(p["spec"], needed_columns=d.get("columns"),
                                        params=d.get("params"), view_name=d["name"], schema=d.get("schema", DEFAULT_SCHEMA))
                if res.get("action") == "author" and res.get("verdict") == "PASS":
                    all_views[d["name"]] = {"name": d["name"], "schema": d.get("schema", DEFAULT_SCHEMA), "xsql": res["xsql"]}
            else:  # reuse: pull the real xsql from the catalog for the bundle
                v = st.get_view(d["name"])
                if v:
                    all_views[d["name"]] = {"name": v["name"], "schema": v.get("schema", DEFAULT_SCHEMA), "xsql": v.get("xsql", "")}
        design = pdz.design_page(p["spec"], ds_names, shell={"pageDefinitionId": pid, "title": p["title"]})
        results.append({"name": p["name"], "verdict": design.get("verdict"), "errors": design.get("errors", [])})
        if design.get("page"):
            pages_out.append({"pageDefinitionId": pid, "title": p["title"], "page": design["page"],
                              "icon": build_spec.get("icon", "Analytics")})

    written = write_bundle(out_dir, build_spec.get("app_name", "Extend App"),
                           build_spec.get("icon", "Analytics"), pages_out,
                           list(all_views.values()), sorted(all_tables),
                           build_spec.get("workflows", []))
    return {"status": "assembled", "written": written, "report": coverage_report(build_spec, results)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", help="deterministic test: path to a JSON {app_name, icon, pages, views, tables}")
    ap.add_argument("--out", default="./out_app")
    a = ap.parse_args()
    if a.bundle:
        spec = json.load(open(a.bundle))
        w = write_bundle(a.out, spec.get("app_name", "App"), spec.get("icon", "Analytics"),
                         spec["pages"], spec.get("views", []), spec.get("tables", []), spec.get("workflows", []))
        print(json.dumps(w, indent=2))
    else:
        print(__doc__)
