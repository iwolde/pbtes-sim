# Requirements

## Phase C: Physics & Convergence

### Convergence Targets
- [x] **CONV-01**: Mode 1 offdesign converges for Solar Salt HTF (fix Solar Salt property range issue).
- [x] **CONV-02**: Mode 6 design passes (fix "too many parameters" error).
- [x] **CONV-03**: PI: 4-mode scheme converges (Modes 2-6).
- [ ] **CONV-04**: SI: not in scope — deferred.
- [ ] **CONV-05**: PD: not in scope — deferred.
- [x] **CONV-06**: SD: Modes 1-4 converge.
- [x] **CONV-07**: Full 365-day baseline simulation converges >= 95% of timesteps.
- [x] **CONV-08**: Create `pbtes/analysis/convergence.py` for error rate tables and anomaly detection.

### Energy Balance
- [x] **EBAL-01**: Monthly energy balance error < 1%.
- [x] **EBAL-02**: Energy conservation verified across mode transitions.

### Results Output
- [ ] **RES-01**: Topology comparison (PI vs SD) — 2 full-year runs.
- [ ] **RES-02**: HTF comparison (Solar Salt vs Air) — 2 full-year runs.

## Phase D: Publication Output

### Economic Analysis
- [ ] **ECON-01**: LCOH within +/-30% of literature values.
- [ ] **ECON-02**: Exergoeconomic analysis completed.
- [ ] **ECON-03**: Sensitivity tornado chart for LCOH.

### Figures & Tables
- [ ] **FIG-01**: System schematic (PI and SD layouts).
- [ ] **FIG-02**: Annual DNI and ambient temperature profile.
- [ ] **FIG-03**: TES temperature colormap (full year).
- [ ] **FIG-04**: Summer day profile (powers, temps, modes).
- [ ] **FIG-05**: Winter day profile.
- [ ] **FIG-06**: Monthly energy breakdown (stacked bar).
- [ ] **FIG-07**: Zinc pool temperature year-long profile.
- [ ] **FIG-08**: PI vs SD solar fraction comparison.
- [ ] **FIG-09**: Solar Salt vs Air HTF comparison.
- [ ] **FIG-10**: Solar fraction vs solar multiple.
- [ ] **FIG-11**: LCOH vs TES volume.
- [ ] **FIG-12**: Sensitivity tornado chart.
- [ ] **FIG-13**: All figures in SVG/PDF at 300 DPI.

### Documentation
- [ ] **DOC-01**: Paper draft sections 1-8.
- [ ] **DOC-02**: Synthesis tables from parametric sweeps.