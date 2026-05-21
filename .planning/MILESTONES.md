# Milestones

## v1.2 Publication Pipeline (In Progress — Phase C)

**Phases:** A (Foundation), B (Bug Fixes), C (Convergence), D (Publication)

**Phase A — Foundation & Agent Methodology** (Complete)
- Codebase cleanup, AGENTS.md rewrite, planning documents established
- Documentation coherence audit and fixes (2026-05-21)

**Phase B — Bug Fixes & Script Consolidation** (Complete)
- Unified `run_simulation.py` and `run_parametric.py` entry points
- Critical bug fixes, mode1_kA.txt removed
- Post-processing pipeline (pump power via Ergun equation)

**Phase C — Physics & Convergence** (In Progress)
- Fix Mode 1 offdesign convergence for NaK
- Fix Mode 6 design ("too many parameters")
- Converge all 6 modes for all 4 topologies
- Create `pbtes/analysis/convergence.py`

**Phase D — Results & Publication** (Not Started)
- Full-year simulations for all configurations
- Parametric sweeps (aperture, TES volume, topology)
- HTF comparison (NaK vs Air)
- 14+ publication figures
- LCOH and exergoeconomic analysis
- Paper draft

## v1.1 Robust Physics and Testing Framework (Shipped: 2026-04-29)

- Comprehensive pytest suites (physics, modes, networks, topology, transitions)
- Parallel/Series equation system validation
- Mode transition integration testing
- Thermodynamic consistency verification (1st and 2nd law energy balances)
- CoolProp constraint limits against NaK boundaries

## v1.0 PBTES Pipeline MVP (Shipped: 2026-04-23)

- Refactored 6 duplicated TESPy network modes into config-driven method
- PTC field, PBTES, zinc pool, and economic models integrated
- Automated parametric sweep infrastructure
- LCOH calculation and publication-quality graph generation
- HTF comparison framework (NaK/Air)
