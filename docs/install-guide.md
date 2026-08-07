# Extend LLM — Install Guide

Follow this **after** your admin has granted API access (see the admin checklist). You'll have either an
Anthropic API key (`sk-ant-...`) or cloud credentials (Bedrock/Vertex/Azure). This guide gets the tool
running on your machine.

**Prerequisites:** Python **3.11+**, `git`, and one of the credential types above.

---

## 1. Get the code

Ask the person sharing it for either a **private Git URL** or a **zip**.

```bash
# Git (preferred — easy updates later):
git clone <private-repo-url> extend-llm
cd extend-llm

# OR unzip the folder they sent, then: cd extend-llm
```

> If you received a zip, make sure it does **not** contain their `.venv/`, `.env/`, or `.git/` —
> the venv is machine-specific and `.env` holds *their* secrets, which you must not reuse.

## 2. Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Add YOUR credentials

Create a file named `.env` in the project root. **Use your company's credentials, never someone else's.**

**If you got an Anthropic API key (Path A):**
```bash
ANTHROPIC_API_KEY=sk-ant-...        # your company's key from the admin
```

**If you're on cloud (Path B) — pick your provider, no Anthropic key needed:**
```bash
# AWS Bedrock:
EXTEND_LLM_PROVIDER=bedrock
AWS_REGION=us-east-1                 # plus your normal AWS credentials configured

# GCP Vertex:
EXTEND_LLM_PROVIDER=vertex
ANTHROPIC_VERTEX_PROJECT_ID=<project-id>
CLOUD_ML_REGION=<region>            # plus GCP application-default credentials

# Azure Foundry:
EXTEND_LLM_PROVIDER=foundry
ANTHROPIC_FOUNDRY_API_KEY=<key>
ANTHROPIC_FOUNDRY_RESOURCE=<resource>
```

> `.env` is gitignored — keep it that way. Never commit or share it.

## 4. Point it at your data (important — not bundled fully)

The tool grounds its answers on Xactly schema + a view catalog. Two paths depending on your tenant:

- **`XC_TABLES_DIR`** — folder of Xactly `xc_*.csv` data-dictionary files (one CSV per table). Set this to
  wherever you keep them:
  ```bash
  # add to .env, or export before running:
  XC_TABLES_DIR=/path/to/xc_tables
  ```
- **`EXTEND_CATALOG_PATH`** — the repo ships `gate/datasources.json`, which is **one specific tenant's** set
  of reusable views.
  - **Same Xactly tenant** as the person who shared it → leave it as-is.
  - **Different tenant** → point this at *your* tenant's view catalog, or the reuse suggestions will
    reference views that don't exist for you:
    ```bash
    EXTEND_CATALOG_PATH=/path/to/your/datasources.json
    ```

## 5. Verify (no API spend)

```bash
python evals/run_evals.py            # deterministic checks — should report all passing, no key used
python app/schema_tools.py xc_credit # confirms schema grounding can read your xc_tables
```

## 6. Verify the model connection (small API spend)

```bash
python evals/run_evals.py --llm      # makes real Claude calls — confirms your key/creds work
```

If this fails with an **auth error**, your credentials aren't right yet — recheck step 3 (and that your admin
actually enabled **API access**, not just a chat seat).

## 7. Run it

**Command line (fastest way to try it):**
```bash
python app/query_engine.py "credits by measure for a participant and period" \
  --tables xc_credit xc_credit_type xc_participant xc_period \
  --params v_master_participant_id v_period
```

**Slack bot (the team surface — optional):** you also need Slack tokens.
1. Create a Slack app from `app/slack_manifest.yaml`, enable **Socket Mode**, generate an App-Level token
   with `connections:write`.
2. Add to `.env`:
   ```bash
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   ```
3. Start it and invite the bot to a channel:
   ```bash
   python app/slack_app.py
   ```
4. In Slack, type `/extend` — you'll get buttons: **Ask a Question**, **Write a Query**, **Upload FRD**,
   **Generate FRD**.

> The bot runs only while this process is alive. For **just yourself**, running it locally is fine. To keep it
> up for a team, host it on an always-on machine under a process manager (systemd / Docker `restart: always`) —
> Socket Mode needs no public URL.

---

## Quick troubleshooting
| Symptom | Likely cause | Fix |
|---|---|---|
| `auth` / `401` / permission error on `--llm` | No real API access (chat seat only), or wrong key | Recheck step 3; confirm admin enabled API/Developer Platform |
| `provider needs an SDK extra` | Cloud provider missing its SDK extra | `pip install "anthropic[bedrock]"` (or `[vertex]`) |
| Schema lookups empty | `XC_TABLES_DIR` not set / wrong path | Point it at your `xc_*.csv` folder |
| Reuse suggests views you don't have | `datasources.json` is another tenant's | Set `EXTEND_CATALOG_PATH` to your tenant's catalog |
| Bot starts but never responds in Slack | Socket Mode off, or bot not invited to channel | Enable Socket Mode; `/invite` the bot |

## What NOT to do
- Don't reuse anyone else's `.env` or API key — use your own company's credentials.
- Don't commit `.env` or keys to Git.
- Don't automate the claude.ai chat app as a substitute for API access — it won't work and violates the terms.
