# Extend LLM — Requirements vs. Design (gap analysis)

Checking the 8 user requirements (2026-08-06) against `ARCHITECTURE.md`. Legend:
✅ covered · 🟡 partial (needs change) · ➕ new (not in design yet) · ⚠️ conflict / needs a decision.

| # | Requirement | Status | Design impact |
|---|---|---|---|
| 1 | **Two-path entry:** every session starts with a choice — **Upload FRD** (→ go build JSON) or **Generate FRD** (user gives plain-English requirements → LLM writes the FRD → returns a **downloadable Word doc**). | 🟡➕ | Upload path existed; the **Generate-FRD → .docx** path is new. Add an **FRD-Author** sub-agent + a `docx` export step. Entry UI = two buttons. |
| 2 | **Approval gate:** after FRD is uploaded/generated, prompt the user to start the build. **No code/JSON generation until the user finalizes the FRD.** | 🟡 | Make it a hard checkpoint in orchestration: pipeline **halts** at "FRD finalized?" — architect/xSQL/page steps are blocked until an explicit go. |
| 3 | **Custom-component constraint:** Extend HTML lives in a `Custom` control's `controlData`, but `Custom` only works for a **fixed/defined set of fields** — **dynamic columns won't render** through it. | ➕ | New hard guardrail: **variable/dynamic-column data → use a `table` bound to a view** (columns come from the view), **never** a `Custom` HTML card. `Custom` only for fixed, known fields. This corrects a wrong assumption in the current prompt. |
| 4 | **Goal = graphical, plug-and-play dashboards.** | ✅ | Reframe the target artifact as **dashboard pages** (tiles + charts + tables), reusable/parameterized so a user can drop them in. Already the direction; make it explicit. |
| 5 | **LLM learns from user comments and "trains itself."** | 🟡⚠️ | Honest version: no live weight-training in a Cursor/Slack app. Realistic loop = capture user corrections/approvals into a **feedback store** (accepted examples + correction pairs) reused as few-shot context and promoted into guardrails → measurable improvement. A true **fine-tune dataset** can be a later, separate track. **Decision needed** (see below). |
| 6 | **Everything = JSON + events (broadcast/subscribe) + parameters** defined on the page/dashboard. | ✅ | Already the core model in the orchestrator prompt (CREATE_EVENT/BIND_EVENT channels + `:param`↔variable). Reinforce as the single source of truth. |
| 7 | **Slack bot:** answers questions from queries the LLM builds; and **if asked, creates a query from the user's input.** | 🟡⚠️ | The bot is described more as a **query-generation + Q&A assistant** than the full-app builder UI. Likely **two surfaces** on one engine: (a) query bot, (b) app/dashboard builder. **Decision needed** on whether these are one Slack app or two. |
| 8 | **Analyze design first; build queries first.** | ✅ | This document = the analysis. Revised build order below puts **xSQL query generation first** (it's the foundation of pages *and* the bot's core skill). |

## Revised build order (queries first)
1. **Query engine (xSQL generation + validation)** — grounded on `xc_tables/*.csv` (schema) + the tenant view
   catalog (reuse-first) + the `lint_xsql` gate. This is the atom everything else stands on **and** the Slack
   bot's core capability (point 7).
2. **FRD flows** — the two-path entry (upload / generate→.docx) + the finalize-before-build gate (points 1, 2).
3. **Page/dashboard designer** — tiles/charts/tables with the channel-event + `:param` model, honoring the
   `Custom` dynamic-column constraint (points 3, 4, 6).
4. **App assembler** — nav + pages + views + workflows, all gated.
5. **Slack surface(s)** — query bot + build trigger (point 7).
6. **Feedback/learning loop + evals** — capture comments → improve (points 5, 8).

## Decisions needed before building
- **D1 (point 5):** "learn/train by itself" = (a) feedback-store + few-shot self-improvement (no fine-tuning, works now), or
  (b) also build a fine-tuning dataset pipeline for a real custom model later? *Recommend (a) now, (b) as a separate track.*
- **D2 (point 7):** Slack = one app with two modes (query bot **+** dashboard builder), or start with **just the query bot**?
- **D3 (point 1):** FRD Word doc — generate from an HTML template via `textutil`/`python-docx`? Any required FRD template/section list to follow?

## Decisions resolved (2026-08-06)
- **D1 → Feedback store + few-shot** (no live fine-tuning). Capture corrections/approvals; reuse as few-shot + promote to guardrails.
- **D2 → One Slack app, both modes** (query Q&A/creation **and** FRD→dashboard build) from the start.
- **D3 → EFM FRD is the template.** Follow `~/Downloads/FRD EFM V1.docx` structure — captured in `knowledge/frd_template.md`.
- **Build order stands: queries first** (xSQL generation + validation), then FRD flows, then page/dashboard designer, then assembler, then Slack surface, then feedback loop.
