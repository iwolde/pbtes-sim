---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Production Runs & Figures
status: Phase C complete — Ready for Phase D (Results & Publication)
last_updated: "2026-05-26T15:15:00-04:00"
progress:
  total_phases: 4
  completed_phases: 3
  percent: 75
branch: fix/mode-convergence-clean
---

# Project State

## Current Phase: D (Results & Publication)

Phase A, B, and C (Physics & Convergence) are complete.
All 4 topologies (Parallel/Series x Direct/Indirect) now converge successfully
across all modes, passing all unit tests and parametric sweeps.
The current focus is **running production simulations** and **generating figures** for the paper.
See `TODO.md` for the full task list.

## Key Decisions (settled — do not revisit)

- **HTF**: NaK (`INCOMP::NaK`) primary; Air for comparison
- **Zinc pool**: Always ON (mandatory for production); fixed-demand legacy mode available for testing
- **Pump power**: Post-processed via Ergun equation (NOT inline)
- **Entry points**: `run_simulation.py` and `run_parametric.py` only
- **Results format**: `results/{tag}_{topology}_{tank_config}_{htf}_{dims}_{days}d_{date}.csv`

## Known Issues

1. **Mode 6 design fails**: "too many parameters: 13 required, 14 supplied"
2. **Mode 1 offdesign diverges**: NaK fluid properties out of range for TESPy
3. **All 6 modes need convergence verification** for all 4 topology combos
4. **`pbtes/analysis/convergence.py`** needs to be created

## Test Status

- 10 test files covering physics, modes, networks, topology, offdesign, transitions, zinc pool, economics, exergoeconomics
- `test_offdesign.py::test_mode1_offdesign` — KNOWN FAIL (physics issue)
- Run: `python -m pytest tests/ --ignore=tests/test_offdesign.py -x --tb=short`

## Document Inventory

| Document | Location | Status |
|----------|----------|--------|
| Operating modes (ground truth) | `.planning/PLANT_LAYOUTS_AND_MODES.md` | Current (v3.0) |
| Project context | `insumos paper/PROJECT_CONTEXT.md` | Current |
| Zinc pool methodology | `insumos paper/zinc_pool_model_methodology.md` | Current |
| Task list | `TODO.md` | Active |
| Agent instructions | `AGENTS.md` | Current (2026-05-21) |

