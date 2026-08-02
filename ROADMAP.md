# 30-Day Sprint — Netso Energy RMG PPA Pipeline

Derived from Strategic Council Deliberation (2026-08-03). Three milestones, hard gates, no scope creep.

## M1: Hardened Term Sheet v2.0 (Target: Day 15)

Draft and sign PPA term sheets with anchor off-takers incorporating:

- **Two-Part Tariff:** Capacity charge (BDT/kW/month, covers 100% debt service + fixed O&M + equity IRR hurdle, payable regardless of generation) + energy charge (BDT 1.5-2.0/kWh, variable O&M only)
- **BPDB Escalator:** Index to BPDB Bulk Supply Tariff + 15% discount floor, cap 5% p.a.
- **UBO Guarantee:** Ultimate beneficial owner personal/corporate guarantee with lien on export LC proceeds
- **Escrow Waterfall:** Export proceeds (USD) flow through offshore escrow → debt service → Netso O&M → RMG OpEx
- **Deemed Generation Clause:** Off-taker pays as-if-generated during curtailment/shutdown
- **PRI Pass-Through:** Political risk insurance cost baked into capacity charge

**Success metric:** Signed term sheets with min 15 MW across 3+ distinct counterparties.

**Assignees:** Legal harness (SCRY — contract drafting), CFO harness (AURUM — investor relations for term sheet review)

---

## M2: IDCOL Programmatic Term Sheet (Target: Day 25)

Secure IDCOL mandate letter confirming:

- **Tenor:** 15 years (not 10 — matches asset life & PPA term, eliminates Year 10 refinancing cliff)
- **Leverage:** 80/20 debt/equity @ 6% fixed BDT
- **Master Facility:** Programmatic approval for 40 MW pipeline (not project-by-project)
- **DSRA:** 6-month debt service reserve account funded in USD equivalents at financial close
- **CAPEX Discipline:** Hard cap BDT 40k/kW certified by independent engineer
- **Amortization:** Sculpted to P90 generation profile, principal holiday Years 1-2

**Success metric:** Signed IDCOL mandate letter with all terms binding.

**Assignees:** Finance harness (SPARK — unit economics), CFO (AURUM — lender relations), Legal (BEACON — SREDA/IDCOL regulatory interface)

---

## M3: Master Procurement & USD CAPEX Lock (Target: Day 30)

Execute procurement strategy for Phase 1 (30-40 MW):

- **Master Supply Agreements (MSAs):** Tier-1 modules + inverters covering 50 MW block, fixed USD price CIF Chattogram
- **EPC Tender Pack:** Fixed-price, date-certain, LDs @ 0.5%/day (cap 15%), performance guarantees
- **Warehousing:** Chattogram/Dhaka FTZ strategy, pre-clearance via IDCOL/BEPZA channels
- **O&M Platform:** Centralized SCADA/remote monitoring mandatory, drone/AI inspection, no per-site teams

**Success metric:** Executed MSAs + EPC tender pack released + warehousing logistics plan approved.

**Assignees:** Operations harness (FORGE — installation/onsite, NEXUS — procurement), Finance (SPARK — CAPEX verification against GROUND_TRUTH_CONSTANTS.md)

---

## Standing Cadence

- **Friday executive cycle:** `python -m aos run --venture netso` — review → prioritize → delegate → summarize
- **Milestone builds:** `python -m aos orchestrate --autonomous --roadmap-file ROADMAP.md` (gates: spec, plan, review — founder decision required at each)

## Ground Rules

- All financial metrics verified against `GROUND_TRUTH_CONSTANTS.md` (true variable rate BDT 12.98, never blended 14.81 for savings)
- Every milestone output goes through approval gates before shipping
- Human lawyer review mandatory before any signature
