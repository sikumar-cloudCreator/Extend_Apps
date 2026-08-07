# Claude API Access — Request for Admin

**What I'm setting up:** an internal tool (an Extend / Xactly requirements + xSQL assistant) that calls
Claude **programmatically via the Anthropic API**. It runs as code, not in the chat app.

**Why the Enterprise seat isn't enough:** our Claude **Enterprise** license covers the claude.ai *chat*
product (human seats in the browser/desktop app). This tool needs **API / Developer Platform access** —
a separate capability. A chat seat cannot authenticate an API call.

Please provision **one** of the two paths below and return the noted values.

---

## Path A — Anthropic API (Developer Platform)  ← simplest

1. Confirm the company has an org at **console.anthropic.com** with **API access** enabled
   (this may already be part of our Enterprise agreement; if not, it needs to be added to the account).
2. Create a **dedicated Workspace** for this tool (so its usage and spend are isolated from everything else).
3. In that workspace, create an **API key**.
4. Set a **monthly spend limit** on the workspace (suggest starting at a modest cap, e.g. $50–100, adjustable).
5. Return to me:
   - [ ] The **API key** (`sk-ant-...`) — via a secrets manager / password vault, **not** email or chat
   - [ ] Confirmation the workspace spend limit is set

## Path B — Claude via our cloud (AWS Bedrock / GCP Vertex / Azure)  ← if we already use these

If the company accesses Claude through a cloud provider instead of the Anthropic API directly:

1. Confirm which provider: **AWS Bedrock**, **GCP Vertex AI**, or **Azure Foundry**.
2. Enable model access to **Claude Opus 4.8** in that provider's console/region.
3. Provision credentials scoped to invoking that model (IAM role/key for Bedrock, ADC/service account for
   Vertex, resource + key for Azure) — **no Anthropic API key needed** on this path.
4. Return to me:
   - [ ] Provider name + **region**
   - [ ] The scoped **credentials** (via vault, not email/chat)
   - [ ] For Vertex: the **project ID**; for Azure: the **resource name**

---

## What I do NOT need
- No new claude.ai chat/Enterprise seats.
- No access to anyone else's data, keys, or workspaces.
- No admin/owner role for myself — just the key/credentials above.

## Security notes (for the admin's peace of mind)
- The key/credentials live only in a server-side secrets file with restricted permissions — never in source
  control, never shared in plaintext.
- A **dedicated workspace + spend cap** means this tool's usage is fully visible and bounded, and its key can
  be rotated or revoked independently without affecting anything else.
- Usage is auditable per-workspace in the provider's console.

## Quick reference — which do we have?
| We have… | Path | Return |
|---|---|---|
| Anthropic API org (console.anthropic.com) | A | `sk-ant-...` key + spend cap |
| Claude on AWS Bedrock | B | region + IAM creds |
| Claude on GCP Vertex | B | project ID + region + service-account creds |
| Claude on Azure Foundry | B | resource + region + api key |
| Only claude.ai Enterprise chat seats | — | **API access must be added to the account first** |
