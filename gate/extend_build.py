"""
Extend page builder + validator — REAL model (channel events, PageLoader, Custom HTML cards,
tiles, VC id-chain). Derived from deployed apps: Natera, Goaland, EPOC, PayPal Seller Dashboard.

Control spec (input to build_page) — one dict per control:
  { "kind": "label|pageloader|dropdown|vc|tile|card|table|chart",
    "id": <uuid?>, "title": str, "ds": <view name?>,
    "valueField","displayField","column",           # dropdown/vc/tile
    "var": "v_x", "produces": "e_channel",           # broadcaster (dropdown/vc)
    "bound": [["v_x","col"],...], "html": "<div>{{v_x}}</div>",   # card
    "subscribes": [["e_channel",["refresh"]], ...],  # BIND channels + handlers
    "onload": ["refresh"]|None,                      # $onPageLoad handlers
    "layoutSize": 25|100|None,
    "chart": {"x":"month","ys":[{"key":"attain","label":"Attainment %","fill":"#66B6DE","type":"bar"}]},
    "columns": [{"field","headerName"},...],         # table (optional)
    "schema": "demo" }
"""
import os, uuid

# Tenant schema is not universal — default is configurable; "demo" only as a last resort.
DEFAULT_SCHEMA = os.environ.get("EXTEND_DEFAULT_SCHEMA", "demo")
VALID_KINDS = {"label","pageloader","dropdown","vc","tile","card","table","chart",
               "input","button","export"}
S3 = {"useComponentShadow": False, "useGreyBackground": False, "useInnerGreyBackground": False}
S3s = {"useComponentShadow": True, "useGreyBackground": False, "useInnerGreyBackground": False}
PAG = {"currentPage": 1, "totalItems": None, "itemsPerPage": 200}
NULLDS = {"name": None, "schema": None, "fields": None, "type": None, "isReadOnly": False,
          "columns": None, "seriesColors": {}, "customLabels": {}}


def _ev(name, sel, cid, handlers):
    e = {"name": name, "eventSelection": sel, "id": cid, "handlers": list(handlers),
         "handlerArgs": [{} for _ in handlers], "preHandlers": [], "preHandlerArgs": []}
    if name != "$onPageLoad":
        e["broadcastArgs"] = {"validationXsql": ""}
    return e

def _dsv(name, schema, series=False):
    # Ground truth (SellerDashboard_INTX real page): every datasource carries seriesColors:{},
    # on tables too — not just series controls. `series` kept for call-site compatibility.
    return {"name": name, "type": "view", "isReadOnly": True, "schema": schema, "seriesColors": {}}

def _ckey(cid):
    """controlKey as seen on real presentational controls: 'control_' + first 8 of the controlId."""
    return f"control_{str(cid)[:8]}"

def _grid_column(col):
    """Normalize a minimal {field, headerName?} spec into the full real table-column shape."""
    field = col["field"]
    return {"field": field, "name": col.get("name", field),
            "headerName": col.get("headerName", field), "dataType": col.get("dataType", "string"),
            "editable": False, "isPrimaryKey": False, "formattingStyle": "default", "sortable": False,
            "readOnly": False, "pinned": False, "currencyFormat": "en-US", "groupBy": False}

def _events(spec, cid, default_onload):
    ev = []
    onload = spec.get("onload", default_onload)
    if onload:
        ev.append(_ev("$onPageLoad", "BIND_EVENT", cid, onload))
    for sub in spec.get("subscribes", []):
        ch, handlers = (sub if isinstance(sub, (list, tuple)) else (sub, ["refresh"]))
        ev.append(_ev(ch, "BIND_EVENT", cid, handlers))
    if spec.get("produces"):
        ev.append(_ev(spec["produces"], "CREATE_EVENT", cid, []))
    return ev


def build_page(controls: list, shell: dict) -> dict:
    props, n = {}, 0
    for spec in controls:
        kind = spec.get("kind")
        if kind not in VALID_KINDS:
            raise ValueError(f"invalid kind {kind!r}; use {sorted(VALID_KINDS)}")
        n += 1
        key = f"control_{n}"
        cid = spec.get("id") or str(uuid.uuid4())
        schema = spec.get("schema") or DEFAULT_SCHEMA
        ds = spec.get("ds")
        title = spec.get("title", "")
        ls = spec.get("layoutSize")

        if kind == "label":
            props[key] = {"type": "label", "controlId": cid, "privileges": None, "styles": S3,
                          "events": [], "controlData": title, "layoutSize": ls or 100,
                          "intl": False, "helpIconPosition": "alignLeft",
                          "helpIconTooltipPosiiton": "right", "helpIconValue": None,
                          "shouldRenderHidden": False, "controlKey": _ckey(cid),
                          "internalName": spec.get("internalName", title)}
        elif kind == "pageloader":
            props[key] = {"type": "PageLoader", "controlId": cid, "privileges": None, "styles": S3,
                          "layoutSize": None, "title": title or "Page Loader",
                          "loaderSize": "FULL", "loaderOpacity": "75",
                          "events": _events(spec, cid, None)}
        elif kind == "dropdown":
            props[key] = {"type": "dropdown", "controlId": cid, "privileges": None, "styles": S3s,
                          "events": _events(spec, cid, ["refresh"]), "datasource": _dsv(ds, schema, True),
                          "pagination": PAG, "columns": [], "whereClauseVariable": None,
                          "variables": [{"name": spec["var"]}], "isMultiSelect": False, "shouldHideLabel": False,
                          "displayField": spec.get("displayField", spec.get("valueField")),
                          "valueField": {"dataType": "string", "name": spec["valueField"]},
                          "labelText": title, "layoutSize": ls or 25, "shouldRenderHidden": False,
                          "controlKey": _ckey(cid)}
        elif kind == "vc":
            # VCs must initialize on load (real pages bind $onPageLoad on every variableConfigurator).
            props[key] = {"type": "variableConfigurator", "controlId": cid, "privileges": None, "styles": S3,
                          "events": _events(spec, cid, ["refresh"]), "datasource": _dsv(ds, schema, True),
                          "pagination": PAG, "columns": [], "whereClauseVariable": None,
                          "variables": [{"name": spec["var"]}],
                          "valueField": {"dataType": "string", "name": spec["valueField"]},
                          "usingMultiSelectVariableFormat": False, "title": title,
                          "staticValue": spec.get("staticValue", ""), "useStaticValue": spec.get("useStaticValue", False),
                          "staticDataType": spec.get("staticDataType", "STRING"),
                          "internalName": spec.get("internalName", title)}
        elif kind == "tile":
            props[key] = {"type": "tile", "controlId": cid, "privileges": None, "styles": S3s,
                          "events": _events(spec, cid, ["refresh"]), "datasource": _dsv(ds, schema, True),
                          "pagination": PAG, "columns": [], "whereClauseVariable": None,
                          "titleText": title, "subtitleText": "", "icon": spec.get("icon", "Align Justify"),
                          "data": "", "column": spec["column"], "layoutSize": ls or 25,
                          "helpIconValue": None, "helpIconPosition": "alignLeft", "helpIconTooltipPosiiton": "right",
                          "shouldRenderHidden": False, "internalName": title}
        elif kind == "card":
            props[key] = {"type": "Custom", "controlId": cid, "privileges": None, "styles": S3s,
                          "internalName": spec.get("internalName", title or "Custom"),
                          "events": _events(spec, cid, ["refresh"] if ds else None),
                          "datasource": _dsv(ds, schema, True) if ds else NULLDS,
                          "pagination": PAG, "columns": [], "whereClauseVariable": None,
                          "variables": [{"name": v, "boundToField": f} for v, f in spec.get("bound", [])],
                          "controlData": spec["html"], "layoutSize": ls, "intl": False,
                          "helpIconPosition": "alignLeft", "helpIconTooltipPosiiton": "right",
                          "helpIconValue": None, "shouldRenderHidden": False}
        elif kind == "table":
            props[key] = {"type": "table", "controlId": cid, "privileges": None, "styles": S3,
                          "internalName": spec.get("internalName", title or "Grid Component"),
                          "events": _events(spec, cid, ["refresh"]), "datasource": _dsv(ds, schema),
                          "pagination": PAG, "columns": [_grid_column(c) for c in spec.get("columns", [])],
                          "whereClauseVariable": None,
                          "variables": [], "table": "grid", "title": spec.get("internalName", title or ""),
                          "maxHeight": None, "shouldRenderHidden": False, "staticAllCoumns": not spec.get("columns")}
            if ls is not None:  # real tables omit layoutSize (full width) unless explicitly sized
                props[key]["layoutSize"] = ls
        elif kind == "chart":
            ch = spec.get("chart", {})
            props[key] = {"type": "composedChart", "controlId": cid, "privileges": None, "styles": S3,
                          "internalName": spec.get("internalName", title or "Chart"),
                          "events": _events(spec, cid, ["refresh"]), "datasource": _dsv(ds, schema),
                          "pagination": PAG, "columns": [], "whereClauseVariable": None,
                          "title": "", "subtitle": "", "xAxis": {"title": {"text": ""}, "type": ""},
                          "yAxis": {"title": {"text": ""}}, "ref": {},
                          "xAxisField": ch.get("x"),
                          "yAxisFields": [{"id": i + 2, "dataKey": y["key"], "customLabel": y.get("label", y["key"]),
                                           "fill": y.get("fill", "#66B6DE"), "selectedChart": y.get("type", "bar")}
                                          for i, y in enumerate(ch.get("ys", []))],
                          "layoutSize": ls or 100, "titleAlignment": "left", "subtitleAlignment": "left",
                          "helpIconValue": None, "helpIconPosition": "alignLeft", "helpIconTooltipPosition": "right",
                          "shouldRenderHidden": False}
        elif kind == "input":  # B1: search / free-text input; CREATEs a channel on Enter
            props[key] = {"type": "input", "controlId": cid, "privileges": None, "styles": S3,
                          "internalName": spec.get("internalName", title or "Input"),
                          "events": _events(spec, cid, None),
                          "variables": [{"name": spec["var"]}] if spec.get("var") else [],
                          "labelText": spec.get("labelText", ""), "labelValue": spec.get("placeholder", title or ""),
                          "isMultiLine": spec.get("isMultiLine", False), "isDisabled": False,
                          "layoutSize": ls or 100, "useEnterBroadcast": spec.get("useEnterBroadcast", True),
                          "shouldRenderHidden": False, "allowClear": spec.get("allowClear", True)}
        elif kind == "button":  # B1: action button; CREATEs a channel when clicked
            props[key] = {"type": "button", "controlId": cid, "privileges": None, "styles": S3,
                          "internalName": spec.get("internalName", title or "Button"),
                          "events": _events(spec, cid, None), "controlData": title or spec.get("label", "Button"),
                          "layoutSize": ls or 16.66, "buttonColorType": spec.get("buttonColorType", "link"),
                          "icon": spec.get("icon", ""), "iconPosition": spec.get("iconPosition", "left"),
                          "shouldRenderHidden": False}
        elif kind == "export":  # B1/B2: export-page-to-PDF; BINDs a channel with exportAsPDF
            props[key] = {"type": "exportPagePDF", "controlId": cid, "privileges": None, "styles": S3,
                          "internalName": spec.get("internalName", ""), "layoutSize": ls,
                          "title": title or "Export As PDF", "variables": [],
                          "events": _events(spec, cid, None)}

        # B3: conditional visibility — any control may be marked hidden (shouldRenderHidden).
        if spec.get("hidden") and isinstance(props.get(key), dict) and "shouldRenderHidden" in props[key]:
            props[key]["shouldRenderHidden"] = True

    page = {"pageDefinitionId": shell["pageDefinitionId"],
            "pageSchema": {"properties": {}, "controlSchema": {"schema": {"type": "object", "properties": props}}},
            "title": shell["title"], "versionName": shell.get("versionName", "v1")}
    # Real known-good pages omit description entirely; only include it when explicitly supplied.
    if shell.get("description") is not None:
        page["description"] = shell["description"]
    return page


def _bound_columns(c):
    """Every view column a control references, so we can check them against the catalog."""
    t, out = c.get("type"), []
    vf = c.get("valueField")
    if isinstance(vf, dict) and vf.get("name"):
        out.append(vf["name"])
    df = c.get("displayField")
    if isinstance(df, str):
        out.append(df)
    elif isinstance(df, dict) and df.get("name"):
        out.append(df["name"])
    if c.get("column"):                       # tile
        out.append(c["column"])
    for v in c.get("variables", []):          # Custom boundToField
        if v.get("boundToField"):
            out.append(v["boundToField"])
    if t == "table":
        out += [col.get("field") for col in c.get("columns", []) if col.get("field")]
    if t == "composedChart":
        if c.get("xAxisField"):
            out.append(c["xAxisField"])
        out += [y.get("dataKey") for y in c.get("yAxisFields", []) if y.get("dataKey")]
    return [x for x in out if x]


def validate_page(page: dict, shell: dict | None = None, catalog: list | None = None) -> dict:
    errors, warnings = [], []
    def err(control, category, problem, fix):
        errors.append({"control": control, "category": category, "problem": problem, "fix": fix})
    try:
        props = page["pageSchema"]["controlSchema"]["schema"]["properties"]
    except Exception:
        return {"verdict": "FAIL", "errors": [{"control": "<root>", "category": "structure",
                "problem": "missing pageSchema.controlSchema.schema.properties", "fix": "use the Extend envelope"}], "warnings": []}
    if shell:
        for k in ("pageDefinitionId", "title"):
            if page.get(k) != shell.get(k):
                err("<root>", "structure", f"{k} != shell", f"set {k} to {shell.get(k)!r}")
    if "variables" in page:
        warnings.append({"control": "<root>", "note": "page-level variables[] present — real pages declare variables per control, not at page level"})

    valid_types = {"label","PageLoader","dropdown","variableConfigurator","tile","Custom","table","composedChart",
                   "button","input","exportPagePDF","slideout","modal","tabContainer","Timer","xSQLRunner",
                   "xSQLButton","workflowButton","xsqlWorkflowTrigger"}
    produced, subscribed, ids = set(), {}, []
    for key, c in props.items():
        for e in c.get("events", []):
            if e.get("name") == "$onPageLoad":
                continue
            if e.get("eventSelection") == "CREATE_EVENT":
                produced.add(e.get("name"))
            elif e.get("eventSelection") == "BIND_EVENT":
                subscribed.setdefault(e.get("name"), []).append(key)
    for key, c in props.items():
        t = c.get("type")
        if t not in valid_types:
            err(key, "type", f"type {t!r} not a known Extend type", "use a real Extend control type")
        WRAP = {"extendType","region","role","consumesParam","computes"}
        bad = WRAP & set(c.keys())
        if bad or ("id" in c and "controlId" not in c):
            err(key, "wrap", f"has pipeline-metadata key(s) {sorted(bad or {'id'})}", "transform to real control shape")
        cid = c.get("controlId")
        ids.append(cid)
        if t == "dropdown" and "valueField" not in c:
            err(key, "wiring", "dropdown has no valueField", "add valueField (else can't hold a selection)")
        if t == "Custom" and c.get("datasource", {}).get("name") and not c.get("variables"):
            warnings.append({"control": key, "note": "Custom has a datasource but no boundTofield variables"})
        # Every datasource-backed control (driver or data) must initialize on load — real pages bind
        # $onPageLoad on every dropdown / variableConfigurator / tile / table / Custom / chart.
        if (c.get("datasource") or {}).get("name"):
            has_onload = any(e.get("name") == "$onPageLoad" and e.get("eventSelection") == "BIND_EVENT"
                             for e in c.get("events", []))
            if not has_onload:
                err(key, "wiring", f"{t} has a datasource but does not bind $onPageLoad — it will not "
                    "initialize on page load (chain/data stays empty until a filter changes)",
                    "add a $onPageLoad BIND_EVENT with handler 'refresh'")
    # every subscribed channel must have a producer
    for ch, subs in subscribed.items():
        if ch not in produced:
            err(subs[0], "wiring", f"channel '{ch}' is subscribed (BIND) but no control CREATEs it",
                f"add a control that CREATE_EVENTs '{ch}', or fix the channel name")
    if len(set(ids)) != len(ids):
        err("<root>", "structure", "duplicate controlId(s)", "make every controlId unique")

    # ---- catalog-aware depth checks: bound columns exist + :params are satisfied ----
    if catalog:
        byview = {d["name"]: {"columns": {col.lower() for col in d.get("columns", [])},
                              "params": list(d.get("params", []))} for d in catalog}
        # variables the page actually sets (drivers/filters declare them per control)
        declared_vars = set()
        for c in props.values():
            for v in c.get("variables", []):
                if v.get("name"):
                    declared_vars.add(v["name"])
        used_views = set()
        for key, c in props.items():
            ds = c.get("datasource") or {}
            name = ds.get("name")
            if not name:
                continue
            used_views.add(name)
            view = byview.get(name)
            if view is None:
                warnings.append({"control": key, "note": f"datasource '{name}' is not in the catalog — "
                                 "can't verify its columns/params (make sure the view exists in the tenant)"})
                continue
            for col in _bound_columns(c):
                if col.lower() not in view["columns"]:
                    err(key, "binding", f"column '{col}' is not in view '{name}'",
                        f"bind a real column of {name}: {sorted(view['columns'])[:12]}")
        # every :param a used view needs must be set by some control on the page
        for name in used_views:
            view = byview.get(name)
            if not view:
                continue
            for p in view["params"]:
                if p not in declared_vars:
                    err("<root>", "param", f"view '{name}' needs :{p} but no control declares that variable",
                        f"add a dropdown/variableConfigurator whose variables[] sets '{p}' (and broadcasts a channel the data control binds)")

    return {"verdict": "PASS" if not errors else "FAIL", "errors": errors, "warnings": warnings}
