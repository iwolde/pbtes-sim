---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Publication Pipeline
status: Phase B complete — Ready for Phase C (Physics & Convergence)
last_updated: "2026-05-21T12:00:00-04:00"
progress:
  total_phases: 4
  completed_phases: 2
  percent: 50
branch: main
---

# Project State

## Current Phase: C (Physics & Convergence Tuning)

Phase A (foundation) and Phase B (bug fixes + script consolidation) are complete.
The current focus is **fixing TESPy solver convergence** for Mode 1 offdesign
and Mode 6 design initialization, and converging all modes for all 4
topologies. See `TODO.md` for the full task list.

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

