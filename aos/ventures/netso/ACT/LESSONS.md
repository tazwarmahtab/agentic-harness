# Netso Energy — Lessons Learned

> Patterns learned, mistakes to avoid.
> Last updated: 2026-08-07

## Operational Lessons

### Financial Accuracy
- **Rule:** Never use blended rate BDT 14.81 for savings calculations
- **Correct:** True variable rate BDT 12.98/kWh
- **Why:** Blended rate includes fixed demand charge; variable rate is the true cost comparison
- **Source:** GROUND_TRUTH_CONSTANTS.md (canonical)

### PPA Pricing
- **Rule:** PPA rate is BDT 10.00/kWh with 3% triennial escalation
- **First escalation:** January 2029
- **Why:** Locked in contract; deviating damages trust

### Approval Gates
- **Rule:** Proposal value > BDT 5,000,000 requires Founder approval
- **Rule:** DSCR < 2.25x requires Founder + CFO approval
- **Rule:** DSCR < 2.0x is immediate alert
- **Why:** Financial risk management; no exceptions

### Data Integrity
- **Rule:** All financial numbers must match GROUND_TRUTH_CONSTANTS.md
- **Generator:** core_economics.py (never edit constants manually)
- **Why:** Single source of truth prevents drift

## Technical Lessons

### AOS Runtime
- **Lesson:** Dry-run mode is essential for testing without LLM costs
- **Lesson:** Seed data must be realistic to catch edge cases early
- **Lesson:** File-based adapters are faster to build than API integrations

## Process Lessons

### Meeting Prep
- **Lesson:** Always prepare intro materials before customer meetings
- **Lesson:** Reach out to local contacts (e.g., Md. Mahfuzul Kabir) before cold outreach

### Investor Relations
- **Lesson:** Follow up within 1 week of initial pitch
- **Lesson:** Keep $500K SAFE terms clear: $3M cap, standard SAFE docs
