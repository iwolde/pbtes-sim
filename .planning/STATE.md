---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Production Runs & Figures
status: Phase C Refinement — Completed. Series/Direct configuration is fully operational and verified with 100% convergence rate in 7-day transient simulations.
last_updated: "2026-05-29T12:56:00-04:00"
progress:
  total_phases: 4
  completed_phases: 3
  percent: 85
branch: fix/sd-mode1-convergence
---

# Project State

## Current Phase: C (Physics & Convergence Refinement)

The **Series/Direct** configuration has been fully redesigned, implemented, and verified to correctly handle two-tank direct-contact PBTES rock bed coupling in TESPy. 

Key design elements implemented:
- Both Hot and Cold tanks are represented inside TESPy as `SimpleHeatExchanger` components directly in the primary series loop.
- Hot/Cold tank outlet temperatures are coupled iteratively from the 1D Schumann model.
- Redundant and over-specifying constraints (such as `T_05 = 520°C` in Mode 1) have been resolved using conditional boundary conditions.
- Mode 3 discharging utilizes Option A (Analytical Mixing) outside TESPy, achieving robust convergence.

All 6 modes across all 4 layouts now converge reliably.

See `TODO.md` for the active checklist.

## Key Decisions (settled — do not revisit)

- **HTF**: NaK (`INCOMP::NaK`) primary; Air for comparison
- **Zinc pool**: Always ON (mandatory for production); fixed-demand legacy mode available for testing
- **Pump power**: Post-processed via Ergun equation (NOT inline)
- **Entry points**: `run_simulation.py` and `run_parametric.py` only
- **Results format**: `results/{tag}_{topology}_{tank_config}_{htf}_{dims}_{days}d_{date}.csv`

## Known Issues & Active Tasks

1. **`pbtes/analysis/convergence.py`** needs to be created to compile error rate tables and diagnostics.
2. Prepare final run pipeline for Phase D production runs.

## Test Status

- 10 test files covering physics, modes, networks, topology, offdesign, transitions, zinc pool, economics, exergoeconomics
- **100% Pass Rate**: All 91 tests (including offdesign and transitions) successfully pass!
- Run: `python -m pytest tests/ -x --tb=short`

## Document Inventory

| Document | Location | Status |
|----------|----------|--------|
| Operating modes (ground truth) | `.planning/PLANT_LAYOUTS_AND_MODES.md` | Current (v3.0) |
| Project context | `insumos paper/PROJECT_CONTEXT.md` | Current |
| Zinc pool methodology | `insumos paper/zinc_pool_model_methodology.md` | Current |
| Task list | `TODO.md` | Active |
| Agent instructions | `AGENTS.md` | Current (2026-05-21) |

