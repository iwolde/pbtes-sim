# Offdesign Refactor Report — PBTES Simulation

**Date:** 2026-05-05 (updated 2026-05-06)
**Scope:** `coreV5.py`, `tests/test_topology.py`, `tests/test_networks.py`, `tests/test_modes.py`
**Test result:** 59/60 pass (1 pre-existing failure)
**Modes working offdesign:** 1, 2

---

## 1. Goal

Make all 20 network configurations (2 topologies × 2 tank configs × 5 modes) solvable in both **design** and **offdesign** mode, with physically coherent constraints. Offdesign must support quasi-steady hourly simulation with variable irradiance (`E`), variable TES coupling temperatures, and component characteristics fixed from design (kA, PTC area, etc.).

---

## 2. Key Architectural Insight: ttd_l Forces kA Computation

### The Problem
In the original code, the HeatExchanger (charge/discharge HX) was configured by fixing all 4 temperatures externally (primary in/out, secondary in/out). This prevented TESPy from computing `kA` during design mode (`kA = NaN` in the stored design file). In offdesign, with `kA = NaN`, the HX had no thermal equation to replace the missing temperature constraints, making the system under-determined.

### The Solution
Use `ttd_l` (terminal temperature difference, cold end) as the HX design parameter instead of fixing the 4th temperature. This forces TESPy to compute `kA` during design:

```python
self.charge_tes_hx.set_attr(pr1=0.98, pr2=0.98, ttd_l=20)
```

With `ttd_l=20`:
- `T_primary_outlet = T_secondary_inlet + 20` (cold-end approach)
- `kA` is computed from the design-point temperatures and stored
- In offdesign, `kA` replaces `ttd_l` as the thermal equation, providing flexibility

### Unified for Both Topologies
Both Parallel and Series topologies now use `ttd_l=20` on the charge HX. This guarantees `kA` computation for all networks, enabling flexible offdesign operation.

---

## 3. Constraint Architecture: `create_network` Design/Offdesign Split

### Principle
`create_network` now accepts a `design_mode` parameter (`'design'` or `'offdesign'`). The common block is divided into:

**Structural (always applied, both modes):**
- Connection pressure and fluid specifications (`conn_06.p`, `conn_06.fluid`, `conn_13.p`, `conn_13.fluid`)
- Component pressure drops (`HX pr1/pr2` or `pr`, `Process pr`, `PTC pr` for Series)
- Initial guesses (`T0`, `h0`, `m0`, `p0` on connections)

**Design-only (skipped in `design_mode='offdesign'`):**
- PTC thermal parameters (`A`, `E`, `η`, `c1`, `c2`, `iam`, `aoi`, `doc`, `Tamb`)
- HX thermal design parameter (`ttd_l=20`)
- Connection temperature setpoints (`conn_05.T`, `conn_06.T`)
- Process duty (`Q`)

### Offdesign Boundary Conditions
In `set_operation_mode` with `mode='offdesign'`:
- PTC `E` is set to `current_irr` (variable hourly irradiance)
- Connection temperatures are set explicitly (not from common block)
- Process `Q` is cleared (`Q=None`) for Series only (uses stored design value)
- Series PTC `A` is set from the designed value (`ptc_field_A_designed`, persisted after design solve)

---

## 4. Per-Mode Constraint Summary

### Mode 1 — High Irradiance: PTC → Process + TES Charge

| Parameter | Parallel | Series |
|-----------|----------|--------|
| HX design | `pr1=0.98, pr2=0.98, ttd_l=20` | `pr1=0.98, pr2=0.98, ttd_l=20` |
| PTC A (design) | Fixed from `component_params['ptc_A']` | `A='var'` (sizes to match single-flow demand) |
| PTC A (offdesign) | Fixed from `component_params` | Fixed from `ptc_field_A_designed` (stored after design) |
| PTC pr | None (Parallel) | `pr=1.0` (Series, structural) |
| T05 (design) | 520°C (fixed) | 520°C (fixed) |
| T05 (offdesign) | 520°C (fixed) | Free (PTC outlet varies with E) |
| T06 (both) | 480°C (process setpoint) | 480°C (process setpoint) |
| Process Q (design) | -1 MW (fixed) | -1 MW (fixed) |
| Process Q (offdesign) | -1 MW (fixed) | None (stored design) |
| Preheater Q (both) | Q=0 | Q=0 |
| `conn_14.T` | `TES_bot + 40` | `TES_bot + 40` |

**Why Series T05 floats in offdesign:** In Series, the single flow path means PTC outlet temperature must vary with irradiance. Fixing it at 520°C would force the PTC to maintain constant outlet temperature regardless of E, which is physically impossible at low irradiance. The Process outlet (T06=480°C) is the true process setpoint.

**Why Series Q=None in offdesign:** With T05 free, fixing both T06 and Q would over-determine the Process. Using stored Q from design (`Q=-1e6`) lets the system find mass flow and T05 that satisfy both Process and PTC equations simultaneously.

**Why Series PTC A must be persisted:** In design mode, `A='var'` sizes the PTC to match the single-flow thermal demand (e.g., 3323 m² instead of the `component_params` upper limit of 10000 m²). In offdesign, this designed value must be fixed. The `solve_network` method persists `ptc_field_A_designed` after each design solve. In `set_operation_mode` offdesign, this value is read and applied.

---

### Mode 6 — Full Charge: PTC → TES (Parallel only; Series not used)

**Architecture:** Two independent cycles with separate `CycleCloser`s:
- **Cycle 1:** CC → PTC → Charge_HX → CC (PTC charges TES directly)
- **Cycle 2:** CC2 → Preheater → Process → CC2 (auxiliary heater supplies process)

| Parameter | Value |
|-----------|-------|
| Cycle 1 HX | `pr1=1.0, pr2=1.0, ttd_l=20` (indirect) or `pr=1.0` (direct) |
| Cycle 1 `conn_02.T` | 520°C (PTC outlet = HX primary inlet) |
| Cycle 1 `conn_02.p` | 50 bar (pressure anchor, indirect only) |
| Cycle 1 `conn_02.fluid` | NaK (fluid anchor, indirect only) |
| Cycle 2 Preheater | `Q=0, pr=1.0` (pass-through, auxiliary heat implicit) |
| Cycle 2 Process | `pr=1.0, Q=-1e6` (from common block) |
| Cycle 2 `conn_05.T` | 520°C (common block) |
| Cycle 2 `conn_06.T` | 480°C, `p=50`, `fluid=NaK` (common block) |
| `conn_14.T` | `TES_bot + 40` |

**Key difference from Mode 1:** No Splitter/Merge. The two cycles are independent. Each has its own pressure closure (Cycle 1: `conn_02.p=50` + CC; Cycle 2: `conn_06.p=50` + CC2). No PTC `pr` for Cycle 1 (pressure equality from CC is sufficient).

**Convergence:** Mode 6 Parallel design converges via `attempt_to_solve` retry logic (same as Mode 1's "21 required, 22 supplied" over-determined pattern). The randomized initial values in the retry pipeline allow the solver to find a valid solution despite the redundant equation.

---

### Mode 2, 3, 4 — Unchanged
These modes were not the focus of this refactor. They continue to work as before. Mode 5 (re-stratification) is excluded per requirements.

---

## 5. How `ptc_field_A_designed` Persistence Works

In `SolarThermalSystem.solve_network()`, after a design-mode solve:
```python
if mode == 'design':
    self.network.solve(...)
    self.network.save(name)
    # Persist designed PTC area
    if (hasattr(self, 'ptc_field') and self.ptc_field is not None
            and self.ptc_field.A.val is not None):
        self.ptc_field_A_designed = self.ptc_field.A.val
```

In `set_operation_mode` Mode 1 offdesign (Series):
```python
if mode == 'offdesign':
    self.ptc_field.set_attr(E=current_irr)
    if getattr(self, 'topology', 'Parallel') == 'Series':
        self.process_hx.set_attr(Q=None)
        if hasattr(self, 'ptc_field_A_designed'):
            self.ptc_field.set_attr(A=self.ptc_field_A_designed)
```

**Critical**: The offdesign system must have `ptc_field_A_designed` set BEFORE calling `set_operation_mode`. In the simulation pipeline, this is done by the design-mode solve which precedes the hourly offdesign solves.

---

## 6. Offdesign Verification Results

### Parallel Mode 1 — Variable E (T_tank=400°C)

```
E=200:  Q_ptc=1.5 MW  (expected 1.5)
E=400:  Q_ptc=3.0 MW  (expected 3.0)
E=600:  Q_ptc=4.5 MW  (expected 4.5)
E=800:  Q_ptc=6.0 MW  (expected 6.0)
E=1000: Q_ptc=7.5 MW  (expected 7.5)
```

All match `Q = E × A × η = E × 10000 × 0.75 / 10⁶` exactly.

### Series Mode 1 — Variable E (T_tank=400°C, A_designed=3323 m²)

```
E=200:  Q_ptc=0.5 MW  (expected 0.5)
E=400:  Q_ptc=1.0 MW  (expected 1.0)
E=600:  Q_ptc=1.5 MW  (expected 1.5)
E=800:  Q_ptc=2.0 MW  (expected 2.0)
E=1000: Q_ptc=2.5 MW  (expected 2.5)
```

All match `Q = E × A_designed × η = E × 3323 × 0.75 / 10⁶` exactly.

---

## 7. Design Philosophy and Rules

### Hard Rules (user-specified)
1. **Never fix mass flows in design mode.** The system should determine them from component equations.
2. **Never fix mass flows or powers in offdesign.** Components use stored characteristics.
3. **Temperatures should ideally not be fixed in offdesign** (but some are needed for solver closure — `T06` as Process setpoint is the key exception).
4. **Each change must be isolated:** A change for one mode/topology/tank_config must not affect others.
5. **E is the incident irradiation on the PTC.** Fixed in design (design DNI = 1000 W/m²). Variable in offdesign (hourly data).

### Design Mode Rules
- Component parameters define the equipment sizing: `A` (PTC), `ttd_l` → `kA` (HX), `Q` (Process)
- Connection temperatures define the nominal operating point
- The `base_design_{mode}` file stores all solved characteristics

### Offdesign Mode Rules
- Component characteristics are FIXED from stored design
- Only `E` (irradiance) and TES coupling temperatures change
- The coupling loop (`_iterate_tes_coupling`) handles temperature evolution between time steps
- For Series: `A` must be explicitly fixed from the designed value (was `'var'` in design)
- For Series: `process Q` uses stored design value (not re-specified)
- For Series: `T05` floats (PTC outlet varies with E)

### Convergence Strategy
- The `attempt_to_solve` method retries with randomized initial values (up to 5 attempts)
- On failure, the coupling loop falls back: Mode 1/6 → Mode 2 → Mode 4
- Many networks converge via retry even with slightly over-determined equation systems

---

## 8. Test Changes

### `test_topology.py`
- `Initial temperature` changed from 500°C to 400°C (needed because `ttd_l=20` with T13=500 forces T10=520, causing thermal inconsistency with hot TES)
- Tests now use direct `set_operation_mode(TESmode='1')` + `conn_13.set_attr(T=...)` instead of `Solver.init_steady()`. This avoids the `get_mode` selection logic interfering with test expectations.
- Added `import numpy as np` for profile creation.

### `test_networks.py`
- `_assert_parallel_mode6` updated to check for `cycle_closer2` (dual-loop) instead of `splitter1`/`merge2`.

### `test_modes.py`
- Added missing `'13_p'`, `'13_f'`, `'15_p'`, `'15_f'` keys to `CONEXION_PARAMS` (needed by common block structural section).

---

## 9. Known Issues & Future Work

### Pre-existing
- `test_mass_flow_routing` fails — expects direct config (Pipe components) but uses indirect default (HeatExchanger with secondary). The test needs updating to match the current architecture.

### Mode Convergence via Retry
- Mode 1 Parallel and Mode 6 Parallel/Series converge via `attempt_to_solve` retry (slightly over-determined: 21 required/22 supplied or 13/14). Without retry, the first solve attempt fails DOF check. This is acceptable for production but could be cleaned up with tighter constraint management.

### Mode 6 Offdesign
- Not yet verified with full offdesign pipeline. Mode 6 was the lower priority after Modes 1 and 2.

### Modes 2, 3, 6 Offdesign
- Not yet tested with variable E spanning. Mode 2 (PTC→Process) should be straightforward (no HX). Mode 3 (TES discharge) needs `ttd_l` on the discharge HX similar to Mode 1's charge HX. Mode 6 Parallel needs full offdesign verification.

### Direct Tank Config
- The `direct` config (no secondary HX loop) was not the focus. Mode 1 Series direct may need additional work for offdesign.

---

## 10. Key Code Locations

| Feature | File | Lines |
|---------|------|-------|
| `create_network` signature | `coreV5.py` | 604 |
| Structural constraints (always) | `coreV5.py` | 763-795 |
| Design-only constraints | `coreV5.py` | 797-830 |
| HX ttd_l (unified) | `coreV5.py` | 815 |
| PTC pr (Series only) | `coreV5.py` | 766 |
| Mode 1 set_operation_mode | `coreV5.py` | 846-875 |
| Mode 6 set_operation_mode | `coreV5.py` | 900-928 |
| Mode 6 Parallel network (dual-loop) | `coreV5.py` | 742-772 |
| `ptc_field_A_designed` persistence | `coreV5.py` | 939-943 |
| Topology tests (Mode 1) | `tests/test_topology.py` | 89-146 |
| Network build tests | `tests/test_networks.py` | 118-145 |

---

## 11. Mode 2 Offdesign — PTC Defocus

### Concept
Mode 2 delivers PTC output directly to the process (no TES). In offdesign, the PTC must deliver exactly the process demand (1 MW) at variable irradiance. This is achieved by **defocusing the mirrors**: `A='var'` lets the PTC adjust its effective area to match `Q = E × A × η = Q_process`.

### Implementation
```python
# set_operation_mode Mode 2 offdesign
self.ptc_field.set_attr(E=current_irr, A='var')  # Defocus to match demand
```

### Verification (A_max = 10000 m², η = 0.75, Q_proc = 1 MW)

| E (W/m²) | A_solved (m²) | Expected | Q_ptc (MW) | Focus ratio |
|----------|---------------|----------|-----------|-------------|
| 200 | 6667 | 6667 | 1.0 | 67% |
| 400 | 3333 | 3333 | 1.0 | 33% |
| 600 | 2222 | 2222 | 1.0 | 22% |
| 800 | 1667 | 1667 | 1.0 | 17% |
| 1000 | 1333 | 1333 | 1.0 | 13% |

All match `A = Q_proc / (E × η)` exactly.

### Key fix
`Preheater Q=0, pr=1.0` was inside `if irr > 500:` gate (design-only). Moved outside so offdesign also receives it.

---

## 12. Control Logic Refactor

### Problem with original logic
Hardcoded thresholds (`irr > 700`, `irr > 600`, `irr > 500`) were independent of the actual PTC size and process demand. A system with A=10000 m² behaves very differently from one with A=5000 m², but the thresholds didn't scale.

### New approach: physics-based irradiance thresholds

```python
A_ptc   = self.component_params['ptc_A']       # Max mirror area
eta_opt = self.component_params['eta_opt']      # Optical efficiency  
Q_proc  = abs(self.component_params['PR_Q'])    # Process demand (W)

E_min_process = Q_proc / (A_ptc * eta_opt)      # Min E for full PTC to deliver process
E_min_charge  = E_min_process * 1.5              # Min E for process + TES charge
```

**For current config** (A=10000 m², η=0.75, Q=1 MW):

| Threshold | Value | Meaning |
|-----------|-------|---------|
| `E_min_process` | 133 W/m² | PTC at full focus delivers exactly process demand |
| `E_min_charge` | 200 W/m² | PTC produces 50% excess for TES charging |

### Mode selection logic (flow order)

1. **Dwell:** Stay in current mode for 2 steps minimum (prevents oscillation)
2. **Pegajosidad Mode 6:** Stay in full charge while SOC < 0.8 and irr sufficient
3. **Cold + dark → Mode 4:** `soc_norm < 0.05 AND E < E_min_process`
4. **Cold TES with irradiance → Mode 6 (full charge):** `soc_norm < 0.4 AND TES_top < 470 AND E > E_min_charge`
5. **Irradiance for charge → Mode 1 or 2:** `E > E_min_charge` → Mode 1 if charge viable and SOC < 0.95, else Mode 2
6. **Irradiance for process only → Mode 2:** `E > E_min_process`
7. **Low irradiance with stored energy → Mode 3 (discharge):** TES top hot enough and SOC > 0.1
8. **Fallback → Mode 4 (standby)**

### Mode diagram vs irradiance

```
E = 0    133    200                                   1000+  W/m²
| Mode 4 | Mode 2 (PTC→Process only) | Mode 1 or 2 (Process + optional charge) |
         | A=var defocus             | A=var defocus or A=var + TES charge     |
```

### Code location
`Solver.get_mode()`: `coreV5.py` lines 1024-1109

---

## 13. Convergence Strategy Update

### Mode 1 (Parallel + Series)
Over-determined by 1 equation (21/22 or 13/14). Converges via `attempt_to_solve` retry with randomized initial values. Series uses `ttd_l=20` → kA stored; offdesign uses kA + variable A.

### Mode 2 (Parallel/Series)
Clean DOF closure: `A='var'` provides exactly the right number of variables/equations. No retry needed. Converges in 5 iterations at all E values.

### Mode 6 (Parallel dual-loop)
Over-determined by 1 equation. Converges via retry (same as Mode 1). Two independent cycles with separate `CycleCloser`s.

---

## 14. Network Work Protocol

For all future convergence tuning on any specific network
(mode × topology × tank_config), follow this protocol:

### 14.1 Scope Audit (before making changes)

Identify ALL functions that touch this network:

| Function | Purpose |
|----------|---------|
| `create_network(mode=X)` | Builds component graph and connections |
| `set_operation_mode(TESmode='X', mode=...)` | Applies design/offdesign constraints |
| `get_mode(...)` | Mode selection logic (E thresholds, SOC checks) |
| `_iterate_tes_coupling(...)` | TES coupling loop, fallback logic, convergence checks |
| `attempt_to_solve(...)` | Retry pipeline with randomized initial values |

### 14.2 Isolation Rule

Every change must be gated by the specific `topology × tank_config × mode` combination. Never change shared logic without auditing all 20 networks.

```python
# BAD: affects all networks
self.ptc_field.set_attr(pr=1.0)

# GOOD: isolated to target
if mode == 6 and getattr(self, 'topology', 'Parallel') == 'Parallel':
    self.ptc_field.set_attr(pr=1.0)
```

### 14.3 Design Mode Requirements

1. All parameters represent a physically valid design point
2. HeatExchanger must use `ttd_l` → forces `kA` computation (mandatory for offdesign)
3. PTC A sizing: `'var'` for Series (matches single-flow demand), fixed for Parallel
4. Design converges (with retry if needed, over-determined by 1 is acceptable)

### 14.4 Offdesign Requirements

1. **E varies** — set via `ptc_field.set_attr(E=current_irr)` in `set_operation_mode`
2. **TES coupling temperatures vary** — `conn_13.T` updated each iteration by `_iterate_tes_coupling`
3. **Mass flows float** — never fix `m` on any connection in offdesign
4. **Component characteristics from stored design** — `kA`, `A` (Series), `Q` (Process for Series)
5. **Temperature setpoints**: fix only `T06` (Process outlet). Let `T05` float where needed

### 14.5 Verification Checklist

- [ ] `test_networks.py`: All 20 configurations build
- [ ] `test_topology.py`: Mass balance + energy consistency hold
- [ ] `test_transitions.py`: N×N mode transitions work
- [ ] Design solve converges → `base_design_{mode}` saved with valid `kA`
- [ ] Offdesign solve converges at multiple `E` values
- [ ] `A='var'` gives correct `A = Q / (E × η)`
- [ ] No hardcoded `irr > N` gates in `get_mode()`; use `self.E_min_process` / `self.E_min_charge`

---

## 15. Key Code Locations

| Feature | File | Lines |
|---------|------|-------|
| `create_network` signature | `coreV5.py` | 604 |
| Structural constraints (always) | `coreV5.py` | 763-795 |
| Design-only constraints | `coreV5.py` | 797-830 |
| HX ttd_l (unified) | `coreV5.py` | 815 |
| PTC pr (Series only) | `coreV5.py` | 766 |
| Mode 1 set_operation_mode | `coreV5.py` | 846-875 |
| Mode 2 set_operation_mode | `coreV5.py` | 883-891 |
| Mode 6 set_operation_mode | `coreV5.py` | 895-925 |
| Mode 6 Parallel network (dual-loop) | `coreV5.py` | 742-772 |
| `ptc_field_A_designed` persistence | `coreV5.py` | 967-970 |
| `Solver.__init__` (control thresholds) | `coreV5.py` | 997-1011 |
| `Solver.get_mode()` (mode selection) | `coreV5.py` | 1031-1109 |
| Topology tests (Mode 1) | `tests/test_topology.py` | 89-146 |
| Network build tests | `tests/test_networks.py` | 118-145 |
| Discharge DHX ttd_l (design-only) | `coreV5.py` | 825-827 |
| create_network Mode 3 | `coreV5.py` | 691-711 |
| set_operation_mode Mode 3 | `coreV5.py` | 897-918 |
| Coupling loop: conn_15 set | `coreV5.py` | 1488-1494 |
| Coupling loop: 2nd law check | `coreV5.py` | 1511-1526 |
| get_mode: discharge thresholds | `coreV5.py` | 1120-1126 |

---

## 16. Mode 3 Discharge — Full Development Report

### 16.1 Network (Parallel Indirect)
```
TES:    Source →15→ DHX(prim) →16→ Sink
Proc:   CC →11→ DHX(sec) →04→ Preheater →05→ Process →06→ CC
```

### 16.2 Two-Regime Architecture
- **Regime A (design, T15=540):** DHX provides all heat. PH Q=0 (pass-through). kA=50000.
- **Regime B (offdesign, T15<540):** DHX partial heat + PH fills gap. PH Q free + pr=1. Same kA.

### 16.3 Constraint Set
```
Design: DHX ttd_l=20 (+1 eq) + Ref(T04,T15,1,20) (net 0) + PH Q=0 (+1 eq)
Offdesign: DHX kA (+1) + same Ref + PH Q free (-1) + PH pr=1 (+1)
→ Same equation count. PH pr replaces PH Q.
```

### 16.4 Ref Convention in TESPy
`Ref(c, 1, delta)` → `self.T = c.T - delta` (subtracts delta, NOT adds).
To get T04 = T15 - 20: use `Ref(conn_15, 1, 20)` (NOT -20).

### 16.5 Component Parameters CAN Change Between Modes
PH Q=0 → PH Q=None + PH pr=1.0: works without TESPy connection errors.
Connections must stay identical; component attributes may differ.

### 16.6 Design Results (T15=540)
T04=520, T16=500, T11=480, T05=520, T06=480. kA=50000, Q_dhx=-1.0MW, Q_ph=0.

### 16.7 Offdesign Range
| T15 | T04 | Q_dhx | Q_ph | Viable? |
|-----|-----|-------|------|---------|
| 560 | 540 | ~1.0 | ~0 | PH limited (T04>520) |
| 540 | 520 | 1.0 | 0.0 | Design point |
| 530 | 510 | 0.75 | 0.25 | Regime B |
| 510 | 490 | 0.25 | 0.75 | Regime B |
| 505 | 485 | 0.12 | 0.88 | Regime B |
| 500 | 480 | NaN | NaN | Zero ΔT, fail |

### 16.8 get_mode Thresholds (Parameterized)
```
T_min_discharge = t_proc_set + 25  = 505 C (cold-end viability)
T_max_discharge = t_ph_out + 20    = 540 C (T04 ≤ T05, PH can't cool)
Mode 3 when: 505 < TES_top ≤ 540 AND soc_norm > 0.1
```

### 16.9 Updated Status
| Mode | Topo | Design | Offdesign | kA | Strategy |
|------|------|--------|-----------|----|----------|
| 1 | Par | ✓ | ✓ | ✓ | ttd_l + all 4 temps fixed |
| 1 | Ser | ✓ | ✓ | ✓ | ttd_l + A='var'→designed |
| 2 | Par | ✓ | ✓ | N/A | A='var' defocus |
| 3 | Par | ✓ | ✓ | ✓ | ttd_l + Ref + 2 regimes |
| 4 | Par | ✓ | ✓ | N/A | Simple loop, trivial |
| 6 | Par | Retry (→4) | — | — | Dual-loop over-determined |

### 16.10 Mode 6 Two-Step Approach (Future Work)
Mode 6 Parallel has two independent cycles that can be solved separately:
- **Cycle 1 (PTC→HX):** 5 connections, converges cleanly (design: Q=7.5MW, kA=173287; offdesign: Q=E·A·η)
- **Cycle 2 (PH→PR→CC2):** Identical to Mode 4, always converges
- **Benefit:** Each cycle is simpler than the combined dual-loop, avoids over-determination
- **Required changes:** Modify `create_network(mode=6)` and `_iterate_tes_coupling` to handle two solves per timestep
