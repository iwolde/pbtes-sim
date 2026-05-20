# Requirements

## v1.2 Requirements

### Configuration Separation
- [x] **CONF-01**: Explicitly separate and validate the equation system for the Parallel configuration.
- [x] **CONF-02**: Explicitly separate and validate the equation system for the Series configuration.

### Bug Fixing & Solver
- [ ] **BUG-01**: Execute the automated test suite and debug any identified anomalies.
- [ ] **BUG-02**: Ensure every mode yields correct results in a single steady-state time step.

### Physics Feasibility
- [ ] **PHYS-01**: Ensure thermodynamics and physics boundaries are correctly defined.
- [ ] **PHYS-02**: Ensure the entire system is engineeringly feasible based on the established components.

### Publication Requirements
- [ ] **PUB-01**: Full 365-day baseline simulation converges ≥ 95% of timesteps.
- [ ] **PUB-02**: Monthly energy balance error < 1%.
- [ ] **PUB-03**: All results stored as CSV in `results/` with metadata headers.
- [ ] **PUB-04**: LCOH within ±30% of literature values.
- [ ] **PUB-05**: All figures in SVG/PDF at 300 DPI.
- [ ] **PUB-06**: Topology comparison (Parallel vs Series, Direct vs Indirect).
- [ ] **PUB-07**: HTF comparison (NaK vs Air).

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONF-01 | Phase 8 | ✅ Complete |
| CONF-02 | Phase 8 | ✅ Complete |
| BUG-01 | Phase 9 / Phase B | Pending |
| BUG-02 | Phase 9 / Phase B | Pending |
| PHYS-01 | Phase 10 | Pending |
| PHYS-02 | Phase 10 | Pending |
| PUB-01 | Phase C | Pending |
| PUB-02 | Phase C | Pending |
| PUB-03 | Phase C | Pending |
| PUB-04 | Phase D | Pending |
| PUB-05 | Phase D | Pending |
| PUB-06 | Phase C | Pending |
| PUB-07 | Phase C | Pending |