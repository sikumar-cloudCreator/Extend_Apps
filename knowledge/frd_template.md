# FRD Template for Extend (derived from EFM FRD — the canonical format)

Source of truth: `~/Downloads/FRD EFM V1.docx` (Republic Services Goals & Guarantees) and
`~/Downloads/EFM_Goals_Guarantees_extend/FRD.md`. The **Generate-FRD** path must produce a Word doc
that follows this structure. This is also what an **uploaded** FRD is parsed against.

## Document outline
1. **INTRODUCTION** — purpose, background, scope of the Extend build.
2. **PROJECT SUCCESS FACTORS** — what "done/good" means for this engagement.
3. **OVERVIEW** — the solution at a glance: what dashboards/pages are being built and why.
4. **APPLICATION LAYOUT** — the app-level shell: navigation, page list, roles/access, global filters.
5. **PAGES** — one subsection per page (see per-page template below).
6. **DOCUMENT ACCEPTANCE** — sign-off block (name/role/date).

## Per-page template (repeat for every page)
Each page in **PAGES** carries:
- **`<PAGE NAME>`** (e.g. GOAL ENTRY PAGE, GOAL REVIEW PAGE, ADMIN: LOAD TO INCENT, GUARANTEE ENTRY,
  GUARANTEE PREVIEW & UPLOAD, ADMIN: EMAIL TEMPLATE)
  - **User Stories** — "As a <role>, I want <goal> so that <value>."
  - **Assumptions** — data availability, roles, pre-conditions, out-of-scope notes.
  - **Page Layout** — the components on the page and their arrangement (tiles / charts / tables /
    dropdowns / variableConfigurators / buttons), described so a designer can place them.
  - **Filters at the top of the page** — the driver controls (period, participant, position, year, …)
    and what each filters.
  - **Fields and their source** — a table mapping each displayed field → its **datasource view** and
    **column** (this is what grounds xSQL + bindings). Include the `:param`s each view needs.
  - **Page-specific sections as needed** — Approval Paths, Calculations, Sample Email Verbiage, etc.

## Extend-specific additions (make the FRD build-ready)
Beyond the EFM prose, every page section should also state — because the whole app runs on this (user point 6):
- **Datasources** — the views the page uses (reused existing view name, or "new" + required columns/params).
- **Variables & Events** — the page variables (`v_*`) and the **broadcast/subscribe channels**: which control
  CREATEs each channel and which controls BIND it (the filter→data wiring).
- **Dynamic vs fixed data** — flag any variable/dynamic-column area (→ must be a `table` bound to a view;
  **not** a `Custom` HTML card, which only supports a fixed set of fields — user point 3).

## Notes
- Font/branding in the EFM doc: Century Gothic, numbered headings, TOC, acceptance table. The generated
  `.docx` should be clean and professional; exact branding can be tuned later.
- Keep the "Fields and their source" tables precise — they are the contract the query engine and page
  designer build against.
