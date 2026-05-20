---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Publication Pipeline
status: Phase B complete — Ready for Phase C (Physics Convergence)
last_updated: "2026-05-20T11:22:00-04:00"
progress:
  total_phases: 4
  completed_phases: 2
  percent: 50
branch: fix/phase-b-bugs
---

# Project State

## Current Phase: C (Physics & Convergence Tuning)

Phase A (foundation) and Phase B (bug fixes + script consolidation) are complete.
The next agent must focus on **fixing TESPy solver convergence** for Mode 1 offdesign
and Mode 6 design initialization. Do NOT change the script structure or results format.

## Key Decisions (settled — do not revisit)

- **HTF**: NaK (`INCOMP::NaK`) primary; Air for comparison
- **Zinc pool**: Always ON (mandatory)
- **Pump power**: Post-processed via Ergun equation (NOT inline)
- **Entry points**: `run_simulation.py` and `run_parametric.py` only
- **Results format**: `results/{tag}_{topology}_{tank_config}_{htf}_{dims}_{days}d_{date}.csv`

## Known Issues for Next Agent

1. **Mode 6 design fails**: "You have provided too many parameters: 13 required, 14 supplied"
   → Fix: remove one over-specified parameter from Mode 6 network setup in `system.py`

2. **Mode 1 offdesign diverges**: NaK fluid properties go out of range for TESPy
   → Fix: improve initial guesses / clamp in `solver.py` `attempt_to_solve()`

## Test Status (branch: fix/phase-b-bugs)

- 83/83 tests pass (excluding `test_offdesign.py::test_mode1_offdesign` — physics issue)
- Run: `python -m pytest tests/ --ignore=tests/test_offdesign.py -x --tb=short`

## Recent Updates

- Phase B committed: `6a5ca7e` — mode1_kA.txt removed, run_simulation.py + run_parametric.py created (2026-05-20)
- Phase A committed: `e6d494f` — AGENTS.md rewrite, cleanup, dict key fixes (2026-05-19)
- Modularization committed: `39254b3` — pbtes/ package created (prior)

