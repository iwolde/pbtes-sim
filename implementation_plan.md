# PBTES Simulation — Comprehensive Diagnostic & Testing Plan

## Current Status Summary

| Mode | Description | Design Init | Status | Issue |
|------|-------------|:-----------:|--------|-------|
| 1 | PTC → Process + TES charge | ✅ | **Working** | `pr > 1` and `zeta < 0` warnings on PTCField (cosmetic, converges) |
| 2 | PTC → Process only | ✅ | **Working** | Clean |
| 3 | TES → Process | ✅ | **Falls back to 4** | `Q > 0` on discharge pipe triggers second-law guard → Mode 4 |
| 4 | Standby (preheater only) | ✅ | **Working** | Clean |
| 5 | ~~Re-stratification~~ | ❌ | **Removed** | Deleted in Phase 1.2 |
| 6 | PTC → TES + Preheater → Process | ❌ | **BLOCKED** | DOF mismatch: "12 required, 11 supplied" |

### Changes Already Applied (Phase 1.2)
- Mode 5 completely removed (11 locations)
- Mode 6: removed invalid cross-loop `m=Ref(conn_04)`, added `preheater_hx.pr=1.0`
- Fixed 3 assignment bugs (`==` vs `=`)
- Fixed energy accounting (`_get_Q_kw()` now called, `dt_s` defined)
- Added mode dwell counter (2-step minimum)
- Cleaned up 100+ stale `base_design_*` folders

---

## Issue #1: Mode 6 DOF Mismatch (BLOCKING)

### Root Cause Analysis

Mode 6 Parallel has **two independent CycleCloser loops** sharing one TESPy Network:

```
Loop 1: CC → PTCField → charge_tes_pipe → CC    (3 connections: conn_01, conn_02, conn_10)
Loop 2: CC2 → preheater_hx → process_hx → CC2   (3 connections: conn_04, conn_05, conn_06)
```

TESPy says **12 parameters required, 11 supplied**. Here's the full constraint inventory:

#### Currently Set Constraints

| # | Source | Constraint | Loop |
|---|--------|-----------|------|
| 1 | `create_network` L702 | `conn_02.p = 50` | 1 |
| 2 | `create_network` L702 | `conn_02.fluid = {NaK: 1}` | 1 |
| 3 | `create_network` L703 | `charge_tes_pipe.pr = 0.98` | 1 |
| 4 | Common L711 | `ptc_field.A = 1000` (+ all PTC model params) | 1 |
| 5 | Common L725 | `conn_05.T = 520` | 2 |
| 6 | Common L728-731 | `conn_06.T = 480, p = 50, fluid = {NaK: 1}` | 2 (×3) |
| 7 | Common L735 | `process_hx.pr = 1.0, Q = -450000` | 2 (×2) |
| 8 | `set_operation_mode` | `preheater_hx.pr = 1.0` | 2 |
| 9 | `set_operation_mode` | `ptc_field.A = 'var'` | 1 (frees A → -1) |
| 10 | `_iterate_tes_coupling` | `conn_10.T = TES_bottom` | 1 |

**Count:** 1 + 1 + 1 + (1 PTC energy → A was freed by 'var') + 1 + 3 + 2 + 1 + 0 (freed) + 1 = **12 if A counted, 11 if A freed**

> [!IMPORTANT]
> The issue: `ptc_field.A = 'var'` in `set_operation_mode` **overrides** `A = 1000` set in the common section. But TESPy's DOF count happens at solve time. When `A='var'`, the PTC model loses its area constraint, creating an **under-determined** system — the PTC energy equation has no fixed area to anchor the heat balance.

### Proposed Fix

Instead of freeing `A`, we need to **add one more constraint** to Loop 1 to reach 12. The missing piece: **Loop 1 has no mass flow or temperature target beyond `conn_10.T` from TES coupling**.

**Option A (Recommended):** Set `conn_02.m` (PTC outlet mass flow) based on an energy balance estimate:
```python
# In set_operation_mode, Mode 6 Parallel:
# Estimate charging mass flow from PTC capacity
Q_ptc_est = component_params['ptc_A'] * component_params['ptc_E'] * component_params['eta_opt']  # W
Cp_nak = 1050  # J/(kg·K) approximate for NaK at 500°C
delta_T = conexion_params['5_T'] - 410  # (PTC outlet - TES cold end) estimate
m_charge_est = Q_ptc_est / (Cp_nak * delta_T)  # kg/s
self.conn_02.set_attr(m=m_charge_est)
```

**Option B:** Set `conn_01.T` (PTC inlet temperature) to TES bottom temperature explicitly.

**Option C:** Remove `ptc_field.A='var'` (restore fixed A) and remove `conn_10.T` from `_iterate_tes_coupling` initialization. Instead, let the TES coupling loop set `conn_10.T` only after the first solve.

> [!WARNING]
> Option C changes the TES coupling initialization pattern and may cause first-solve divergence. Option A is safest because it gives TESPy a concrete mass flow to start from, which the offdesign solver can then relax.

### DOF Fix Implementation

```python
# In set_operation_mode, elif TESmode == '6':
else:  # Parallel
    # Keep A fixed (from common section) — do NOT set A='var'
    # Add mass flow estimate for Loop 1 based on PTC energy balance
    try:
        Q_ptc_W = self.component_params['ptc_A'] * self.component_params['ptc_E'] * self.component_params['eta_opt']
        Cp_nak = 1050.0  # J/(kg·K)
        delta_T = max(self.conexion_params['5_T'] - profile[-1], 10.0)  # PTC_out - TES_cold
        m_est = Q_ptc_W / (Cp_nak * delta_T)
        self.conn_02.set_attr(m=m_est)
    except Exception:
        self.conn_02.set_attr(m=5.0)  # fallback
    self.preheater_hx.set_attr(pr=1.0)
```

This adds 1 constraint (mass flow) to Loop 1, giving 12/12.

---

## Issue #2: Mode 3 Second-Law Violation

Mode 3 initializes and converges, but `discharge_tes_pipe.Q.val > 0` triggers the second-law guard and falls back to Mode 4.

**Root cause:** The TES initial temperature for Mode 3 init is 510°C, and the process demands 520°C outlet. The TES is too cold to supply the process without the preheater boosting the temperature. However, the discharge pipe itself shows positive Q (heat flowing INTO the pipe from surroundings), which is physically wrong.

### Proposed Fix
- Increase Mode 3 init temperature to 540°C (ensure TES can supply process)
- OR relax the second-law check to allow small positive Q values (noise)
- Verify that `conn_04.T = TES_top - 20` is reasonable for discharge

---

## Issue #3: PTCField Warnings (pr > 1, zeta < 0)

These are **cosmetic TESPy warnings**, not errors. The PTC model doesn't enforce `pr ≤ 1` as a hard constraint — it's an advisory. The negative zeta similarly indicates the pressure drop model isn't physical for this component configuration, but doesn't affect the energy balance convergence.

### Proposed Fix
- Can be silenced by setting `ptc_field.pr = 1.0` explicitly in the common section, but this may over-constrain some modes
- OR accept the warnings as non-fatal (document in the article methodology)

---

## Testing Strategy

### Phase A: Unit Test Each Mode (Isolation)

Create `test_modes.py` that tests each mode independently:

```python
# For each mode in [1, 2, 3, 4, 6]:
#   1. Create SolarThermalSystem
#   2. Set operation mode
#   3. Solve design
#   4. Assert convergence
#   5. Print DOF count, key outputs (Q, T, m)
```

**What to verify per mode:**

| Mode | Check | Expected |
|------|-------|----------|
| 1 | `ptc_field.Q.val < 0` | PTC absorbs heat (negative convention) |
| 1 | `charge_tes_pipe.Q.val < 0` | Heat flows into TES |
| 1 | `preheater_hx.Q.val == 0` | Preheater off |
| 2 | `ptc_field.Q.val < 0` | PTC absorbs heat |
| 2 | `preheater_hx.Q.val == 0` | Preheater off |
| 3 | `discharge_tes_pipe.Q.val < 0` | Heat flows from TES |
| 3 | `preheater_hx.Q.val` | Free (can be 0 or negative) |
| 4 | `preheater_hx.Q.val < 0` | Preheater supplies full process |
| 6 | `ptc_field.Q.val < 0` | PTC absorbs heat |
| 6 | `charge_tes_pipe.Q.val < 0` | Heat flows into TES |
| 6 | `preheater_hx.Q.val < 0` | Preheater supplies full process |

### Phase B: Mode Transition Test (3-day)

Run a 3-day simulation with controlled irradiance data to verify:
- Mode transitions happen at expected irradiance thresholds
- No rapid toggling (dwell counter works)
- Energy signals are non-zero and physically consistent
- TES temperature stays within [300, 600]°C

### Phase C: Full Year Baseline

Run 365-day simulation with TMY data:
- All modes exercised across seasons
- Solar fraction computed
- Cumulative energy balance checked
- Results saved to CSV for post-processing

### Phase D: Parametric Sweep

Sweep over:
- PTC outlet temperature: [480, 500, 520, 540]°C
- TES tank length: [3, 5, 7, 10] m
- PTC area: [500, 1000, 1500, 2000] m²

---

## Files & Configuration Audit

### `run_baseline.py` Configuration Review

| Parameter | Current Value | Concern |
|-----------|:---:|---------|
| `HTF` | `INCOMP::NaK` | ✅ Correct for molten salt |
| `5_T` (PTC outlet / process inlet) | 520°C | ✅ |
| `6_T` (process outlet) | 480°C | ✅ |
| `6_p` | 50 bar | ✅ |
| `ptc_A` | 1000 m² | ✅ |
| `ptc_E` | 900 W/m² | ✅ Design irradiance |
| `PR_Q` | -450000 W | ✅ Process heat demand |
| `TES init temp` | 490°C | ⚠️ Overridden per mode in `initialize_modes` |
| `topology` | `'Parallel'` | ✅ |

### `coreV5.py` Key Functions to Audit

| Function | Status | Notes |
|----------|--------|-------|
| `create_network(mode)` | ⚠️ | Mode 6 Parallel needs DOF fix |
| `set_operation_mode(TESmode)` | ⚠️ | Mode 6 needs mass flow constraint |
| `get_mode(irr, profile, lay)` | ✅ | Mode 5 removed, dwell added |
| `get_system_mode(irr)` | ✅ | Dwell counter reset added |
| `initialize_modes()` | ⚠️ | Mode 3 init temp may need increase |
| `_iterate_tes_coupling()` | ✅ | Mode 5 branches removed |
| `_collect_step_signals()` | ✅ | Energy accounting fixed |
| `attempt_to_solve()` | ✅ | Retry logic with randomization |
| `run_quasi_steady_simulation()` | ✅ | Mode 5 removed, bugs fixed |

---

## Execution Order

1. **Fix Mode 6 DOF** → Apply Option A (mass flow estimate) in `set_operation_mode`
2. **Fix Mode 3 init temp** → Raise to 540°C in `initialize_modes`
3. **Create `test_modes.py`** → Unit test each mode in isolation
4. **Run `test_modes.py`** → Verify all 5 modes converge in design mode
5. **Run `run_baseline.py`** → Full year simulation
6. **Analyze results** → Solar fraction, energy balance, mode distribution
7. **Parametric sweep** → Multiple PTC temperatures and TES sizes

---

## Open Questions

> [!IMPORTANT]
> **Q1:** For Mode 6, should the preheater supply heat at the SAME temperature/pressure as the PTC would (520/50), or can it operate at different conditions? Currently Loop 2 uses `conn_05.T = 520` and `conn_06.T = 480, p = 50` from the common section — same as all other modes.

> [!IMPORTANT]
> **Q2:** The `ptc_pr: 1` in `component_params` is never used (only `ptc_field.set_attr(pr=...)` would apply it). Should we explicitly set `ptc_field.pr = 1.0` in the common section to suppress the `pr > 1` warnings? This adds 1 constraint per mode — need to verify DOF impact.

> [!NOTE]
> **Q3:** Mode 3's second-law guard (`Q > 0` on discharge pipe) currently forces fallback to Mode 4. Is this the desired behavior, or should Mode 3 be allowed to proceed with preheater supplementing the TES discharge?
