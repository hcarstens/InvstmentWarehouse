## Phase 1 — Weeks 1–4: Discovery, schema & data model views ✓

**Dashboard at run:** Entity graph explorer, security master table, schema/migration status.

Backend:
- [x] **Workflow catalog** — owner, inputs, outputs, SLA (onboarding through reporting)
- [x] **Entity graph v0** — Person, Household, Trust, LLC, Account, Custodian edges
- [x] **Security master v0** — CUSIP/ISIN/ticker, asset class, tax character, wash-sale groups
- [x] **Lot ledger schema** — cost basis, holding period, wash-sale chains
- [x] Alembic migrations against **SQLite** (local file under `data/`; Postgres later)

Dashboard panels (each phase item maps to a visible panel):
- [x] **Entity graph view** — household → accounts → custodians (interactive or tabular)
- [x] **Security master browser** — search/filter instruments and tax attributes
- [x] **Schema status** — applied migrations, table row counts, last migration time

---

## Phase 2 — Weeks 5–12: Vertical slice & positions dashboard (current)