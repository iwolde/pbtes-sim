# Paper Outline — PBTES for Solar Galvanizing

**Target journals:** Journal of Energy Storage, Energy, Solar Energy (Q1)

## Proposed Structure

### 1. Introduction
- Industrial process heat decarbonization challenge
- Packed bed TES for medium-temperature applications (400-600°C)
- Gap: PBTES integrated with galvanizing process — no published system-level simulation

### 2. System Description
- PTC solar field → PBTES → zinc galvanizing bath
- Parallel vs Series HTF integration
- Direct vs Indirect TES tank configuration  
- 6 operating modes (charge, discharge, simultaneous, bypass, aux)

### 3. Mathematical Models
- 3.1 PTC efficiency model (IAM, thermal losses)
- 3.2 Packed bed TES — 1D Schumann equation (validated in prior article)
- 3.3 Zinc pool — lumped capacitance (dynamic galvanizing demand)
- 3.4 TESPy network coupling (quasi-steady approach)
- 3.5 Mode selection logic (SoC + irradiance + temperature thresholds)
- 3.6 Pump power — Ergun equation (post-processed)

### 4. Case Study
- 4.1 Location and weather data (TMY — TBD)
- 4.2 Galvanizing plant specifications (hypothetical reference)
- 4.3 Design point selection and baseline parameters

### 5. Results
- 5.1 Baseline annual simulation
- 5.2 Monthly energy breakdown
- 5.3 Dynamic zinc pool behavior
- 5.4 Topology comparison (Parallel vs Series)
- 5.5 Tank configuration comparison (Direct vs Indirect)
- 5.6 HTF comparison (NaK vs Air)
- 5.7 Parametric analysis (solar multiple, TES volume)

### 6. Economic Analysis
- 6.1 LCOH methodology
- 6.2 Sensitivity to key parameters
- 6.3 Comparison with conventional heating

### 7. Discussion

### 8. Conclusions

## Key Figures (minimum 13)
1. System schematic (Parallel + Series)
2. Annual DNI & ambient temperature
3. TES temperature colormap (full year)
4. Summer day profile (powers, temps, modes)
5. Winter day profile
6. Monthly energy breakdown (stacked bar)
7. Zinc pool temperature (year)
8. Parallel vs Series solar fraction
9. Direct vs Indirect comparison
10. NaK vs Air comparison
11. Solar fraction vs solar multiple
12. LCOH vs TES volume
13. Sensitivity tornado

## Key Decisions
- HTF: NaK (primary), Air (comparison)
- Zinc pool: always ON (dynamic demand)
- Plant: hypothetical reference design
- PBTES model: pre-validated from prior article
- Pump power: post-processed from quasi-steady results
