# Roadmap

## Phases
- [x] **Phase 8: Parallel & Series Equation Validation** - System equations strictly separated and validated for both configurations (completed 2026-04-30)
- [ ] **Phase 9: Steady-State Mode Bug Fixing** - All operation modes yield correct, bug-free results in a single time step
- [ ] **Phase 10: Physics & Engineering Feasibility** - System operates within realistic thermodynamic bounds and engineering constraints

## Phase Details

### Phase 8: Parallel & Series Equation Validation
**Goal**: System equations are strictly separated and validated for both Parallel and Series configurations.
**Depends on**: None
**Requirements**: CONF-01, CONF-02
**Success Criteria** (what must be TRUE):
  1. The solver successfully runs the Parallel configuration without cross-contamination of Series equations.
  2. The solver successfully runs the Series configuration without cross-contamination of Parallel equations.
  3. Equation outputs for both topologies match theoretical thermodynamic expectations.
**Plans**: 1 plans
- [x] 08-01-PLAN.md — Strictly separate and validate both Parallel and Series configuration equations

### Phase 9: Steady-State Mode Bug Fixing
**Goal**: All operation modes yield correct, bug-free results in a single steady-state time step.
**Depends on**: Phase 8
**Requirements**: BUG-01, BUG-02
**Success Criteria** (what must be TRUE):
  1. The automated test suite executes completely with zero failures for steady-state scenarios.
  2. Running any single operation mode (1-6) for a single time step produces correct thermodynamic states.
  3. Identified convergence anomalies in previous tests are patched and no longer fail.
**Plans**: 2 plans
- [ ] 09-01-PLAN.md — Test Execution and Bug Fixing
- [ ] 09-02-PLAN.md — Assertion Hardening and Final Verification

### Phase 10: Physics & Engineering Feasibility
**Goal**: System simulation operates within realistic thermodynamic bounds and engineering constraints across the full quasi-steady state run.
**Depends on**: Phase 9
**Requirements**: PHYS-01, PHYS-02
**Success Criteria** (what must be TRUE):
  1. Full quasi-steady state simulations complete without violating Molten Salt temperature boundaries.
  2. Component states (heat exchangers, pumps, flow rates) remain within standard engineering operational limits throughout the simulation.
  3. Full system energy balances strictly hold for the entire transient simulation period.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 8. Parallel & Series Equation Validation | 1/1 | Complete   | 2026-05-04 |
| 9. Steady-State Mode Bug Fixing | 0/0 | Not started | - |
| 10. Physics & Engineering Feasibility | 0/0 | Not started | - |
