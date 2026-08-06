#!/usr/bin/env python3
"""
slack_app.py — the Extend LLM Slack surface (one app, two modes; user point 7 + D2).

Modes, chosen from the `/extend` menu buttons and tracked per thread:
  • QUERY  — "write me an xSQL for ..." -> query_engine -> posts the lint-passing view (or REUSE).
  • BUILD  — Upload FRD or Generate FRD (-> Word doc) -> finalize -> architect -> collect page ids
             -> assemble_app -> posts the coverage report and uploads the deployable app bundle (zip).

Every build path calls the FRD finalize gate before generating anything (point 2) and requires
user-provided pageDefinitionIds (never generated). The engines (query/frd/page/app) are the same
deterministic-gated modules built in steps 1-4.

Run (Socket Mode) in Cursor:
    pip install -r ../requirements.txt
    export SLACK_BOT_TOKEN=xoxb-...  SLACK_APP_TOKEN=xapp-...  ANTHROPIC_API_KEY=sk-...
    python app/slack_app.py
"""
import os, re, sys, shutil, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import query_engine as qe
import frd_flows as ff
import app_assembler as aa
import page_designer as pdz
import feedback_store as fb
import knowledge_base as kb

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# per-thread state: key -> {"mode": str, "frd": FRDSession, "build_spec": dict, "page_ids": dict}
SESSIONS: dict[str, dict] = {}


def _key(body_or_event) -> str:
    ch = body_or_event.get("channel") or body_or_event.get("channel_id") or ""
    ts = body_or_event.get("thread_ts") or body_or_event.get("ts") or body_or_event.get("message_ts") or ""
    return f"{ch}:{ts}"


def _sess(key: str) -> dict:
    return SESSIONS.setdefault(key, {"mode": None, "frd": ff.FRDSession(), "build_spec": None, "page_ids": {}})


MENU_BLOCKS = [
    {"type": "section", "text": {"type": "mrkdwn",
        "text": "*Extend LLM.* What do you want to do?"}},
    {"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "Write a Query"}, "action_id": "mode_query"},
        {"type": "button", "text": {"type": "plain_text", "text": "Upload FRD"}, "action_id": "mode_upload"},
        {"type": "button", "text": {"type": "plain_text", "text": "Generate FRD"}, "action_id": "mode_generate"},
    ]},
]


# ---- entry -----------------------------------------------------------------------------------
@app.command("/extend")
def cmd_extend(ack, respond):
    ack()
    respond(blocks=MENU_BLOCKS, text="Extend LLM menu")


@app.event("app_mention")
def on_mention(event, say):
    say(blocks=MENU_BLOCKS, text="Extend LLM menu", thread_ts=event.get("ts"))


# ---- mode buttons ----------------------------------------------------------------------------
@app.action("mode_query")
def a_query(ack, body, say):
    ack(); _sess(_key(body["container"]))["mode"] = "query"
    say("*Query mode.* Send your request, e.g. `credits by measure for a participant and period`. "
        "Optionally add `tables: xc_credit, xc_period` and `params: v_period` to ground it.",
        thread_ts=body["container"].get("thread_ts") or body["container"].get("message_ts"))


@app.action("mode_upload")
def a_upload(ack, body, say):
    ack(); s = _sess(_key(body["container"])); s["mode"] = "upload"; s["frd"].choose(ff.Mode.UPLOAD)
    say("*Upload FRD mode.* Attach your FRD (.docx / .md) in this thread.",
        thread_ts=body["container"].get("thread_ts") or body["container"].get("message_ts"))


@app.action("mode_generate")
def a_generate(ack, body, say):
    ack(); s = _sess(_key(body["container"])); s["mode"] = "generate"; s["frd"].choose(ff.Mode.GENERATE)
    say("*Generate FRD mode.* Describe the dashboard requirements in plain English. "
        "I'll write the FRD and post a Word doc for review.",
        thread_ts=body["container"].get("thread_ts") or body["container"].get("message_ts"))


# ---- query mode ------------------------------------------------------------------------------
def _parse_query_hints(text: str):
    # capture each hint value up to the next hint keyword or end-of-line
    tables = re.findall(r"tables?:\s*(.+?)(?=\s+params?:|\s+tables?:|\n|$)", text, re.I)
    params = re.findall(r"params?:\s*(.+?)(?=\s+params?:|\s+tables?:|\n|$)", text, re.I)
    split = lambda s: [x.strip() for x in re.split(r"[,\s]+", s) if x.strip() and ":" not in x]
    t = split(tables[0]) if tables else []
    p = split(params[0]) if params else []
    request = re.sub(r"(tables?|params?):\s*.+?(?=\s+params?:|\s+tables?:|\n|$)", "", text, flags=re.I).strip()
    return request, t, p


def run_query(text: str) -> dict:
    request, tables, params = _parse_query_hints(text)
    res = qe.generate_query(request, tables=tables, params=params or None)
    if res.get("action") == "reuse":
        out = f"REUSE {res['view']}"
        return {"display": f":recycle: *Reuse* existing view `{res['view']}` (params: {res.get('params')}).",
                "request": request, "output": out}
    verdict = res.get("verdict")
    body = res.get("xsql", "").strip()
    head = ":white_check_mark: PASS" if verdict == "PASS" else f":x: {verdict} (attempts {res.get('attempts')})"
    errs = "\n".join(f"- {e}" for e in res.get("errors", []))
    return {"display": f"{head}\n```{body}```" + (f"\n*gate errors:*\n{errs}" if errs else ""),
            "request": request, "output": body}


ACCEPT_BLOCK = [{"type": "actions", "elements": [
    {"type": "button", "text": {"type": "plain_text", "text": "👍 Accept"}, "action_id": "accept_output", "style": "primary"},
    {"type": "button", "text": {"type": "plain_text", "text": "✍️ Correct"}, "action_id": "correct_output"}]}]


@app.action("accept_output")
def a_accept(ack, body, say):
    ack(); s = _sess(_key(body["container"])); last = s.get("last")
    if last:
        fb.record(last["kind"], last["request"], last["output"], accepted=True, verdict="user_accept")
        say(":pushpin: Saved as an accepted example — I'll reuse this style.",
            thread_ts=body["container"].get("thread_ts") or body["container"].get("message_ts"))


@app.action("correct_output")
def a_correct(ack, body, say):
    ack(); _sess(_key(body["container"]))["mode"] = "correcting"
    say("Send the correction/comment and I'll log it (it graduates into the guardrails when it recurs).",
        thread_ts=body["container"].get("thread_ts") or body["container"].get("message_ts"))


# ---- FRD build mode --------------------------------------------------------------------------
def start_generate(s: dict, requirements: str, say, client, channel, thread):
    out = os.path.join(tempfile.mkdtemp(), "FRD.docx")
    try:
        r = s["frd"].draft_from_requirements(requirements, out)
    except Exception as e:
        say(f":warning: {e}", thread_ts=thread); return
    client.files_upload_v2(channel=channel, thread_ts=thread, file=r["docx_path"],
                           title="Generated FRD", initial_comment="Draft FRD — review, then Finalize & Build.")
    say(blocks=[{"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "Finalize & Build"}, "action_id": "finalize_build", "style": "primary"},
        {"type": "button", "text": {"type": "plain_text", "text": "Revise"}, "action_id": "revise_frd"}]}],
        text="Finalize?", thread_ts=thread)


@app.action("revise_frd")
def a_revise(ack, body, say):
    ack(); say("Send your revision comment and I'll regenerate the FRD.",
               thread_ts=body["container"].get("thread_ts") or body["container"].get("message_ts"))
    _sess(_key(body["container"]))["mode"] = "revise"


@app.action("finalize_build")
def a_finalize(ack, body, say):
    ack(); s = _sess(_key(body["container"]))
    thread = body["container"].get("thread_ts") or body["container"].get("message_ts")
    try:
        s["frd"].finalize()
    except ff.BuildBlocked as e:
        say(f":warning: {e}", thread_ts=thread); return
    fb.record("frd", s["frd"].requirements or "(uploaded)", s["frd"].frd_markdown, accepted=True, verdict="finalized")
    say(":hourglass: FRD finalized. Planning the app…", thread_ts=thread)
    try:
        s["build_spec"] = aa.architect(s["frd"].frd_markdown)
    except Exception as e:
        say(f":warning: architect failed: {e}", thread_ts=thread); return
    missing = aa.required_page_ids(s["build_spec"], s["page_ids"])
    s["mode"] = "collect_ids"
    say("Create these pages in Extend and reply with one `name = pageDefinitionId` per line:\n"
        + "\n".join(f"• `{n}`" for n in missing), thread_ts=thread)


def collect_ids_and_build(s: dict, text: str, say, client, channel, thread):
    for line in text.splitlines():
        m = re.match(r"\s*([\w-]+)\s*=\s*([\w-]+)\s*$", line)
        if m:
            s["page_ids"][m.group(1)] = m.group(2)
    missing = aa.required_page_ids(s["build_spec"], s["page_ids"])
    if missing:
        say("Still need ids for: " + ", ".join(f"`{n}`" for n in missing), thread_ts=thread); return
    say(":hammer_and_wrench: Building the app…", thread_ts=thread)
    out_dir = tempfile.mkdtemp()
    res = aa.assemble_app(s["build_spec"], s["page_ids"], os.path.join(out_dir, "app_bundle"), session=s["frd"])
    rep = res.get("report", {})
    zip_path = shutil.make_archive(os.path.join(out_dir, "app_bundle"), "zip", os.path.join(out_dir, "app_bundle"))
    client.files_upload_v2(channel=channel, thread_ts=thread, file=zip_path, title="Extend app bundle",
                           initial_comment=(f"*{rep.get('app_name')}* — {rep.get('pages_built')}/{rep.get('pages_in_spec')} pages, "
                                            f"all pass gate: {rep.get('all_pages_pass_gate')}."))
    s["mode"] = None


# ---- message router --------------------------------------------------------------------------
@app.event("message")
def on_message(event, say, client):
    if event.get("bot_id") or event.get("subtype") in ("bot_message",):
        return
    key = _key(event); s = _sess(key)
    text = (event.get("text") or "").strip()
    thread = event.get("thread_ts") or event.get("ts")
    channel = event.get("channel")
    mode = s.get("mode")

    if mode == "query" and text:
        r = run_query(text)
        s["last"] = {"kind": "query", "request": r["request"], "output": r["output"]}
        say(r["display"], thread_ts=thread)
        say(blocks=ACCEPT_BLOCK, text="Accept or correct?", thread_ts=thread)
    elif mode == "correcting" and text:
        last = s.get("last", {})
        scope = last.get("kind", "query")
        fb.record(scope, last.get("request", ""), last.get("output", ""), accepted=False, comment=text)
        kb.add_lesson(scope, text, why="from user correction", source="slack_correction")  # compound knowledge
        say(":brain: Logged and *learned* it — this rule now applies to every future build.", thread_ts=thread)
        s["mode"] = "query"
    elif mode == "generate" and text:
        start_generate(s, text, say, client, channel, thread)
    elif mode == "revise" and text:
        out = s["frd"].docx_path or os.path.join(tempfile.mkdtemp(), "FRD.docx")
        s["frd"].revise(text, out)
        client.files_upload_v2(channel=channel, thread_ts=thread, file=out, title="Revised FRD")
        s["mode"] = "generate"
    elif mode == "upload":
        files = event.get("files") or []
        if not files:
            return
        tmp = os.path.join(tempfile.mkdtemp(), files[0]["name"])
        _download(client, files[0], tmp)
        s["frd"].load_upload(tmp)
        say(blocks=[{"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Finalize & Build"}, "action_id": "finalize_build", "style": "primary"}]}],
            text="FRD loaded — Finalize & Build?", thread_ts=thread)
    elif mode == "collect_ids" and text:
        collect_ids_and_build(s, text, say, client, channel, thread)


def _download(client, file_obj, dest):
    import urllib.request
    req = urllib.request.Request(file_obj["url_private_download"],
                                 headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"})
    with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
        f.write(r.read())


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
