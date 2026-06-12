---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Production Runs & Exergoeconomics
status: Phase D In Progress — Parametric sweep plan documented in `.planning/PARAMETRIC_SWEEP_PLAN.md`. 4-mode PI scheme verified. Baseline runs and 55-run sweep grid ready to execute.
last_updated: "2026-06-12T00:00:00-04:00"
progress:
  total_phases: 4
  completed_phases: 3
  percent: 80
branch: feature/4mode-pi
---

# Project State

## Current Phase: C → D Transition (Physics & Convergence → Production Runs)

Phase C is functionally complete. The **4-mode PI scheme** has been implemented,
tested, and verified with a full-year simulation (A=1500 m², 8760 timesteps,
100% convergence, SF=54.5%). PI now performs on par with SD (SF=55.4%).

Key Phase C deliverables:
- **PI Mode 1 temperature constraint removed**: conn_05.T=520°C lock broken via
  DNI-aware conn_02.T anchor for offdesign. PTC outlet now reaches 560°C (was 520°C).
- **4-mode PI scheme**: Mode 1 deprecated for PI; Mode 5 (high-T series charge)
  and Mode 6 (dedicated PTC→TES) handle all TES charging. Mode selection thresholds
  updated: Mode 5 uses `TES_bot < T_ptc_est − 20°C`, Mode 6 uses `SoC < 0.80`.
- **Bugs fixed**: stale component references in `create_network`, `design_path`
  not recalculated on Mode 4 fallback, Mode 5 coupling switch checking wrong HX
  attribute, Mode 4 fallback using `use_init_path=True` on incomplete cache.
  See `.planning/MODE_SIMPLIFICATION_PROPOSAL.md` for full details.

Remaining minor issues (low priority, Phase D):
- `T_ptc_out` column always reads 520°C (_collect_step_signals uses PTC component,
  not conn_02.T anchor)
- `aux_tes_energy_kJ` naming bug (stores Joules, labeled kJ)
- `soc_mode3_minimum` hardcoded at 0.02 vs config value 0.10
- `convergence.py` diagnostic module not yet created
- PI_A1000 yearly and PD yearly runs not yet completed.

See `TODO.md` for the active checklist.

## Key Decisions (settled — do not revisit)

- **HTF**: Solar Salt (`INCOMP::NaK` in CoolProp) primary; Air for comparison
- **Zinc pool**: Always ON (mandatory for production); fixed-demand legacy mode available for testing
- **Pump power**: Post-processed via Ergun equation (NOT inline)
- **Entry points**: `run_simulation.py` and `run_parametric.py` only
- **Results format**: `results/{tag}_{topology}_{tank_config}_{htf}_{dims}_{days}d_{date}.csv`

## Known Issues & Active Tasks

1. **`pbtes/analysis/convergence.py`** needs to be created to compile error rate tables and diagnostics.
2. Prepare final run pipeline for Phase D production runs.

## Test Status

- 10 test files: physics, modes, networks, topology, offdesign, transitions, zinc pool, economics, exergoeconomics, ptc_inhouse
- **100% Pass Rate**: 100 passed, 1 xpassed, 0 failed (101 total)
- Run: `python -m pytest tests/ -x --tb=short`

## Document Inventory

| Document | Location | Status |
|----------|----------|--------|
| Operating modes (ground truth) | `.planning/PLANT_LAYOUTS_AND_MODES.md` | Current (v3.2) |
| Mode Simplification (4-mode PI) | `.planning/MODE_SIMPLIFICATION_PROPOSAL.md` | Implemented & Verified (2026-06-10) |
| 4-mode PI yearly assessment | `results/pi_4mode_yearly_*.csv` | Complete (2026-06-10) |
| Project context | `insumos paper/PROJECT_CONTEXT.md` | Current |
| Physics & coupling methodology | `insumos paper/PHYSICS_METHODOLOGY.md` | Current |
| Zinc pool methodology | `insumos paper/zinc_pool_model_methodology.md` | Current |
| Zinc pool transient methodology | `insumos paper/zinc_pool_transient_methodology.md` | Created |
| Article LaTeX Methodology | `insumos paper/article_methodology.txt` | Created |
| Task list | `TODO.md` | Active |
| Agent instructions | `AGENTS.md` | Current |



