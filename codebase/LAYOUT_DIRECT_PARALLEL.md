# Direct Parallel Layout — Complete Specification

## 1. Concept

**Direct Parallel** models a PBTES where the HTF flows through the packed bed
without an intermediate heat exchanger. The TES is represented as two
reservoirs — **hot** (top) and **cold** (bottom) — connected to the process
loop via TESPy `Source`/`Sink` components.

```
  ┌──────────────┐          ┌──────────────┐
  │   Hot Zone   │          │  Cold Zone   │
  │    (top)     │          │   (bottom)   │
  └──┬────────┬──┘          └──┬────────┬──┘
     │        │                │        │
     │ HotSource (draws)       │ ColdSource (draws)
     ▼        ▲                ▼        ▲
  ┌──┴────────┴────────────────┴────────┴──┐
  │           Process Loop                  │
  │   (PTC, HX, PH, PR, Splitter, Merge)    │
  └──┬────────┬────────────────┬────────┬──┘
     │        │                │        │
     ▼        ▲                ▼        ▲
  HotSink     │            ColdSink      │
  (delivers   │            (returns      │
   to top)    │             to bottom)   │
              └──────────────────────────┘
```

**Key design rules:**
- The tank has fixed total fluid volume. Mass entering must equal mass leaving
  every timestep: `∑ m_in = ∑ m_out`.
- `ColdSource` and `ColdSink` are separate connections to the **same** physical
  opening (tank bottom). One draws fluid, the other returns it.
- `HotSource` and `HotSink` are separate connections to the **same** physical
  opening (tank top).
- The 1D packed bed (thermocline) between the two zones is modeled by
  `ThermalEnergyStorage`. The coupling loop iterates between the TESPy
  network and the 1D model.

**Configuration:** `tank_config = '2tank_direct'` (new value).
Existing `'indirect'` and `'direct'` are unchanged.

---

## 2. Components

### 2.1 Tank Connections (Source/Sink)

| Component | TESPy type | Physical meaning |
|-----------|-----------|------------------|
| `ColdSource` | `Source` | Fluid drawn FROM tank bottom |
| `HotSource` | `Source` | Fluid drawn FROM tank top |
| `ColdSink` | `Sink` | Fluid returned TO tank bottom |
| `HotSink` | `Sink` | Fluid delivered TO tank top |

### 2.2 Process Components

| Component | TESPy type | Role |
|-----------|-----------|------|
| `PTCField` | `ParabolicTrough` | Solar collector |
| `Process_HX` (PR) | `SimpleHeatExchanger` | Process heat demand |
| `Preheater_HX` (PH) | `SimpleHeatExchanger` | Pass-through (Q=0) or auxiliary heater (Q free) |
| `HighT_Charge_HX` | `HeatExchanger` | **Mode 5 only.** Transfers premium PTC heat to TES |
| `CycleCloser` | `CycleCloser` | Closes recirculating loops |
| `Splitter1` | `Splitter` | Divides flow (Mode 1) |
| `Merge` | `Merge` | Combines flows (Mode 3-A) |

---

## 3. Mode-by-Mode Specification

### 3.1 Mode 1 — Normal Charge + Process (Direct Split)

**Trigger:** `irr > E_min_charge`, `soc_norm < 0.95`, `T_ptc_out > T_tes_top`.

**Topology:**
```
ColdSource(bot) ──→ PTC ──→ Splitter ──┬──→ PH(Q=0) ──→ PR ──→ ColdSink(bot)
                                        └──→ HotSink(top)
```

**Connections (6):**

| Conn | From | To | Label |
|------|------|----|-------|
| conn_01 | ColdSource.out1 | PTC.in1 | `01_CS_PTC` |
| conn_02 | PTC.out1 | Splitter.in1 | `02_PTC_SP1` |
| conn_04 | Splitter.out1 | PH.in1 | `04_SP1_PH` |
| conn_05 | PH.out1 | PR.in1 | `05_PH_PR` |
| conn_06 | PR.out1 | ColdSink.in1 | `06_PR_CSK` |
| conn_09 | Splitter.out2 | HotSink.in1 | `09_SP1_HSK` |

**Constraints (design mode):**

| Target | Parameter | Value |
|--------|-----------|-------|
| ColdSource | `p`, `fluid` | `6_p`, `6_f` |
| ColdSource | `T` | `T_tes_bottom` (from coupling) |
| HotSink | — | no constraint (receives hot fluid) |
| ColdSink | `p`, `fluid` | `6_p`, `6_f` |
| conn_05 | `T` | `5_T` (process inlet setpoint) |
| conn_06 | `T` | `6_T` (process return) |
| PH | `Q`, `pr` | `0`, `1.0` |
| PR | `Q`, `pr` | `PR_Q`, `1.0` |
| PTC | design params | `A`, `E`, `η_opt`, `aoi`, etc. |
| Splitter | — | no constraints (split ratio from solver) |

**Mass conservation:**
- Splitter enforces: `m_CS = m_04 + m_09` (m_cold = m_proc + m_charge)
- Tank: IN = m_proc + m_charge, OUT = m_cold → **IN = OUT** ✓

**Coupling:**
1. Set `ColdSource.T = T_tes_bottom_prev`
2. Solve → read `conn_09.T` (HotSink inlet), `conn_09.m` (charge mass flow)
3. `tes.update_temperature_profile(T_in=conn_09.T, mass_flow=conn_09.m)` (charge)
4. `ColdSource.T = tes.tout` (new T_tes_bottom)

**Purpose:** Normal high-irradiance operation. Process gets priority at 5_T. Excess PTC output charges the hot tank directly. Both paths receive the same PTC outlet temperature.

---

### 3.2 Mode 2 — PTC → Process Only

**Trigger:** `irr > E_min_process`, below charge threshold, or TES full.

**Topology:**
```
CC ──→ PTC ──→ PH(Q=0) ──→ PR ──→ CC
```

**Connections (4):**

| Conn | From | To | Label |
|------|------|----|-------|
| conn_01 | CC.out1 | PTC.in1 | `01_CC_PTC` |
| conn_02 | PTC.out1 | PH.in1 | `02_PTC_PH` |
| conn_05 | PH.out1 | PR.in1 | `05_PH_PR` |
| conn_06 | PR.out1 | CC.in1 | `06_PR_CC` |

**Constraints:** Standard. CC recirculates mass. No TES interaction.

**Mass:** Closed loop — CC enforces `m_in = m_out`. ✓

---

### 3.3 Mode 3 — TES Discharge → Process

Two regimes depending on whether the hot tank is above or below the process setpoint.

#### 3.3-A Cold Mixing (`T_tes_top ≥ 5_T`)

**Topology:**
```
HotSource(top) ──┐
                 ├──→ Merge ──→ PH(Q=0) ──→ PR ──→ ColdSink(bot)
ColdSource(bot) ─┘
```

**Connections (5):**

| Conn | From | To | Label |
|------|------|----|-------|
| conn_hot | HotSource.out1 | Merge.in1 | `HS_MG` |
| conn_cold | ColdSource.out1 | Merge.in2 | `CS_MG` |
| conn_04 | Merge.out1 | PH.in1 | `04_MG_PH` |
| conn_05 | PH.out1 | PR.in1 | `05_PH_PR` |
| conn_06 | PR.out1 | ColdSink.in1 | `06_PR_CSK` |

**Constraints (design):**

| Target | Parameter | Value |
|--------|-----------|-------|
| HotSource | `T`, `p`, `fluid` | `T_tes_top`, `6_p`, `6_f` |
| ColdSource | `T`, `p`, `fluid` | `T_tes_bottom`, `6_p`, `6_f` |
| ColdSink | `p`, `fluid` | `6_p`, `6_f` |
| conn_05 | `T` | `5_T` |
| conn_06 | `T` | `6_T` |
| PH | `Q`, `pr` | `0`, `1.0` |
| PR | `Q`, `pr` | `PR_Q`, `1.0` |
| Merge | — | no constraints |

**Mass conservation:**
- Merge: `m_hot + m_cold = m_total`
- Tank: IN = m_total (at ColdSink), OUT = m_hot + m_cold → **IN = OUT** ✓

**Physics:** The solver finds `m_hot` and `m_cold` such that:
1. Mixing: `m_hot × h(T_hot) + m_cold × h(T_cold) = m_total × h(5_T)`
2. Process: `m_total = |PR_Q| / [h(5_T) − h(6_T)]`

When `T_hot > 5_T`, cold fluid is mixed in to cool the stream to exactly 5_T.
This reduces hot tank depletion — the cold fluid "bypasses" the bed, drawn
from the bottom and returned to the bottom after mixing. The effective mass
flow through the thermocline is `m_hot`.

**Coupling:** Read `conn_06.T` (= 6_T), `conn_06.m` (total flow). Write `HotSource.T`.

#### 3.3-B Auxiliary Heating (`T_tes_top < 5_T`)

**Topology:**
```
HotSource(top) ──→ PH(Q>0) ──→ PR ──→ ColdSink(bot)
```

**Connections (3):**

| Conn | From | To | Label |
|------|------|----|-------|
| conn_04 | HotSource.out1 | PH.in1 | `04_HS_PH` |
| conn_05 | PH.out1 | PR.in1 | `05_PH_PR` |
| conn_06 | PR.out1 | ColdSink.in1 | `06_PR_CSK` |

**Constraints:** Same as 3-A except:
- No ColdSource, no Merge.
- PH: `Q` free (auxiliary bridges gap), `pr = 1.0`.

**Mass:** `m_out = m_in` (single path). ✓

**Coupling:** Same as 3-A.

**Regime detection:**
```python
if T_tes_top >= conexion_params['5_T']:
    regime = 'A'  # cold mixing
else:
    regime = 'B'  # auxiliary heating
```

---

### 3.4 Mode 4 — Auxiliary Standby

**Trigger:** Low irradiance, TES empty or too cold.

**Topology:**
```
CC ──→ PH ──→ PR ──→ CC
```

**Connections (3):**

| Conn | From | To | Label |
|------|------|----|-------|
| conn_04 | CC.out1 | PH.in1 | `04_CC_PH` |
| conn_05 | PH.out1 | PR.in1 | `05_PH_PR` |
| conn_06 | PR.out1 | CC.in1 | `06_PR_CC` |

**Constraints:** conn_05.T = 5_T, conn_06.T/p/fluid = 6_T/6_p/6_f, PH Q free,
PR Q = PR_Q. No TES interaction.

---

### 3.5 Mode 5 — High-Temperature Charge via HX

**Trigger:** `irr > E_min_charge`, `T_ptc_out > T_high_threshold`, `soc_norm < 0.85`.

Where `T_high_threshold` could be `5_T + 40` (e.g., 520°C). This mode only
activates when PTC can deliver **significantly super-process** temperatures.

**Topology:**
```
Main loop:   CC ──→ PTC ──→ HighT_HX(prim) ──→ PH(Q=0) ──→ PR ──→ CC
TES loop:    ColdSource(bot) ──→ HighT_HX(sec) ──→ HotSink(top)
```

**Connections (7):**

| Conn | From | To | Label |
|------|------|----|-------|
| conn_01 | CC.out1 | PTC.in1 | `01_CC_PTC` |
| conn_02 | PTC.out1 | HighT_HX.in1 | `02_PTC_HTHX` |
| conn_10 | HighT_HX.out1 | PH.in1 | `10_HTHX_PH` |
| conn_05 | PH.out1 | PR.in1 | `05_PH_PR` |
| conn_06 | PR.out1 | CC.in1 | `06_PR_CC` |
| conn_13 | ColdSource.out1 | HighT_HX.in2 | `13_CS_HTHX` |
| conn_14 | HighT_HX.out2 | HotSink.in1 | `14_HTHX_HSK` |

**How the HX connects the TES mass flow:**

The HX has two streams:
- **Primary (main loop):** Hot PTC fluid enters at in1, transfers heat to
  TES, exits at out1 (cooler). The residual goes to process via PH and PR.
  Mass is conserved by the CC.
- **Secondary (TES side):** Cold fluid from tank bottom enters at in2, is
  heated by the HX, exits at out2, and is delivered to the tank top via
  HotSink. Mass: `m_ColdSource = m_HotSink` (HX secondary continuity).

The two fluid circuits are separate — no mass exchange, only heat transfer.

**Constraints (design mode):**

| Target | Parameter | Value |
|--------|-----------|-------|
| conn_06 | `T`, `p`, `fluid` | `6_T`, `6_p`, `6_f` |
| conn_05 | `T` | `5_T` |
| ColdSource | `p`, `fluid` | `6_p`, `6_f` |
| ColdSource | `T` | `T_tes_bottom` (from coupling) |
| HotSink | — | no constraint |
| PH | `Q`, `pr` | `0`, `1.0` |
| PR | `Q`, `pr` | `PR_Q`, `1.0` |
| PTC | design params | `A`, `E`, `η_opt`, etc. |
| HighT_HX | `ttd_l` | `20` (forces kA computation) |
| HighT_HX | `pr1`, `pr2` | `0.98`, `0.98` |

**Mass conservation:**
- Main loop: CC recirculates → `m_in = m_out` ✓
- TES loop: `ColdSource.m = HotSink.m` (HX secondary continuity) ✓
- Tank: IN = m (at HotSink), OUT = m (at ColdSource) → **IN = OUT** ✓

**Coupling:**
1. Set `ColdSource.T = T_tes_bottom_prev`
2. Solve → read `conn_14.T` (HX secondary outlet → HotSink), `conn_14.m`
3. `tes.update_temperature_profile(T_in=conn_14.T, mass_flow=conn_14.m)` (charge)
4. `ColdSource.T = tes.tout` (new T_tes_bottom)

**Purpose:** Capture high-grade solar heat into the TES at temperatures above
the process setpoint. The HX primary receives the full, undiluted PTC outlet
temperature. This pushes the thermocline top to higher temperatures than
Mode 1 can achieve (where the same PTC outlet is split with process return).

The `HighT_Charge_HX` is a standard `HeatExchanger`. It is sized once in design
mode via `ttd_l = 20` and its kA is stored for offdesign use (shared with
Mode 1's `mode1_kA.txt` or a separate file).

**Proposed trigger change:**
```python
# Checked BEFORE Mode 1 in get_mode()
if irr > self.E_min_charge:
    T_ptc = _read_T_ptc_out()
    T_high_threshold = conexion_params['5_T'] + 40  # e.g. 520 C
    if T_ptc is not None and T_ptc > T_high_threshold and soc_norm < 0.85:
        return '5'  # High-T charge
    # else fall through to Mode 1 check
```

---

### 3.6 Mode 6 — Deep Charge + Auxiliary Process

**Trigger:** `soc_norm < 0.4` and `TES_top < 470`, or stickiness
(`soc_norm < 0.8`, `irr > E_min_process`, `prev == '6'`).

**Topology (two independent cycles):**
```
Cycle 1: ColdSource(bot) ──→ PTC ──→ HotSink(top)
Cycle 2: CC ──→ PH ──→ PR ──→ CC
```

**Connections (5):**

| Conn | From | To | Label | Cycle |
|------|------|----|-------|-------|
| conn_01 | ColdSource.out1 | PTC.in1 | `01_CS_PTC` | 1 |
| conn_02 | PTC.out1 | HotSink.in1 | `02_PTC_HSK` | 1 |
| conn_04 | CC.out1 | PH.in1 | `04_CC_PH` | 2 |
| conn_05 | PH.out1 | PR.in1 | `05_PH_PR` | 2 |
| conn_06 | PR.out1 | CC.in1 | `06_PR_CC` | 2 |

**Constraints:**

| Cycle | Target | Parameter | Value |
|-------|--------|-----------|-------|
| 1 | ColdSource | `p`, `fluid` | `6_p`, `6_f` |
| 1 | ColdSource | `T` | `T_tes_bottom` (coupling) |
| 1 | HotSink | — | no constraint |
| 1 | PTC | design params | `A`, `E`, `η_opt`, etc. |
| 2 | conn_05 | `T` | `5_T` |
| 2 | conn_06 | `T`, `p`, `fluid` | `6_T`, `6_p`, `6_f` |
| 2 | PH | `Q` free, `pr = 1.0` | auxiliary |
| 2 | PR | `Q = PR_Q`, `pr = 1.0` | |

**Mass conservation:**
- Cycle 1: `ColdSource.m = HotSink.m` ✓
- Cycle 2: `CC` recirculates ✓
- Tank: IN = m (HotSink), OUT = m (ColdSource) → **IN = OUT** ✓

**Coupling:** Read `conn_02.T` (PTC→HotSink), `conn_02.m`. Write `ColdSource.T`.

**Purpose:** Tank is very depleted. All PTC output directly charges the tank
(no HX — maximum mass flow, minimum thermal loss). Process is served
independently by the auxiliary heater.

---

## 4. Mass Conservation Summary

| Mode | IN to tank | OUT of tank | Conservation |
|------|-----------|-------------|:--:|
| 1 | `ColdSink.m + HotSink.m` | `ColdSource.m` | `m_cold = m_proc + m_charge` ✓ |
| 2 | — | — | N/A |
| 3-A | `ColdSink.m` | `HotSource.m + ColdSource.m` | `m_total = m_hot + m_cold` ✓ |
| 3-B | `ColdSink.m` | `HotSource.m` | `m_in = m_out` ✓ |
| 4 | — | — | N/A |
| 5 | `HotSink.m` | `ColdSource.m` | Main loop separate; TES: `m_in = m_out` ✓ |
| 6 | `HotSink.m` | `ColdSource.m` | `m_in = m_out` ✓ |

Every mode conserves total tank mass. The thermal effect (charge/discharge
of the thermocline) is handled by the 1D packed bed model.

---

## 5. Mode Selection Logic

```python
def get_mode(irr, TES_profile, prev_TES_lay):
    # Dwell: maintain previous mode for 2 steps (anti-oscillation)
    if dwell < 2: return prev_TESmode

    # Stickiness: Mode 6 persists until SOC >= 80%
    if prev == '6' and soc_norm < 0.8 and irr > E_min_process:
        return '6'

    # Dead: no solar, no TES
    if soc_norm < 0.05 and irr < E_min_process:
        return '4'

    # Deep charge needed
    if soc_norm < 0.4 and TES_top < 470:
        return '6' if irr > E_min_charge else '4'

    # High irradiance — charge possible
    if irr > E_min_charge:
        T_ptc = _read_T_ptc_out()
        T_high = conexion_params['5_T'] + 40  # 520 C threshold
        # Mode 5: high-temperature charge (checked first for priority)
        if T_ptc is not None and T_ptc > T_high and soc_norm < 0.85:
            return '5'
        # Mode 1: normal split charge + process
        charge_viable = (T_ptc > TES_top) if T_ptc else True
        if charge_viable and soc_norm < 0.95:
            return '1'
        return '2'

    # Medium irradiance — process only, maybe discharge
    if irr > E_min_process:
        if T_min_disch < TES_top <= T_max_disch and soc_norm > 0.1:
            return '3'
        return '2'

    return '4'
```

---

## 6. TES Coupling Interface

### 6.1 Charge Modes (1, 5, 6)

```
ColdSource.T  ←──  tes.tout  (cold fluid from tank bottom)
       │
       ▼  [PTC and/or HX heats fluid]
       │
   conn.T      ──→  T_in     (hot fluid to tank top)
```

Per iteration:
1. `ColdSource.set_attr(T = T_tes_bottom_prev)`
2. Solve network
3. Read `T_hot` and `m` from the charge outlet connection
4. `tes.set_state('charge')`
5. `tes.update_temperature_profile(T_in=T_hot, mass_flow=m)`
6. `ColdSource.set_attr(T = tes.tout)` (new `T_tes_bottom`)

### 6.2 Discharge Mode (3)

```
HotSource.T   ←──  tes.tout  (hot fluid from tank top)
       │
       ▼  [Process extracts heat]
       │
ColdSink.T    ──→   T_in     (process return to tank bottom)
```

Per iteration:
1. `HotSource.set_attr(T = T_tes_top_prev)`
2. Solve network
3. Read `T_cold` (= 6_T) and `m` from `conn_06`
4. `tes.set_state('discharge')`
5. `tes.update_temperature_profile(T_in=T_cold, mass_flow=m)`
6. `HotSource.set_attr(T = tes.tout)` (new `T_tes_top`)

### 6.3 Connection Mapping

| Mode | Read T + m from | Write T to | TES state |
|------|-----------------|------------|-----------|
| 1 | `conn_09` (Splitter→HotSink) | `ColdSource` | charge |
| 3 | `conn_06` (PR→ColdSink) | `HotSource` | discharge |
| 5 | `conn_14` (HX sec→HotSink) | `ColdSource` | charge |
| 6 | `conn_02` (PTC→HotSink) | `ColdSource` | charge |

---

## 7. Preheater Role by Mode

| Mode | PH Q | PH role |
|------|:----:|---------|
| 1 | 0 | Pass-through (process from PTC directly) |
| 2 | 0 | Pass-through |
| 3-A | 0 | Pass-through (cold mixing handles temperature) |
| 3-B | free | Auxiliary heater |
| 4 | free | Auxiliary heater |
| 5 | 0 | Pass-through (process from HX residual) |
| 6 | free | Auxiliary heater (process cycle) |

---

## 8. Component Inventory by Mode

| Component | M1 | M2 | M3-A | M3-B | M4 | M5 | M6 |
|-----------|:--:|:--:|:----:|:----:|:--:|:--:|:--:|
| PTCField | ✓ | ✓ | — | — | — | ✓ | ✓ |
| Process_HX | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Preheater_HX | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ColdSource | ✓ | — | ✓ | — | — | ✓ | ✓ |
| HotSource | — | — | ✓ | ✓ | — | — | — |
| ColdSink | ✓ | — | ✓ | ✓ | — | — | — |
| HotSink | ✓ | — | — | — | — | ✓ | ✓ |
| Splitter | ✓ | — | — | — | — | — | — |
| Merge | — | — | ✓ | — | — | — | — |
| CycleCloser | — | ✓ | — | — | ✓ | ✓ | ✓ |
| HighT_Charge_HX | — | — | — | — | — | ✓ | — |
| **Total conns** | 6 | 4 | 5 | 3 | 3 | 7 | 5 |

---

## 9. Implementation Notes

### 9.1 New `tank_config` value

Add `'2tank_direct'` branches to:
- `create_network()` — component creation and connections
- `set_operation_mode()` — constraints per mode/regime
- `_iterate_tes_coupling()` — TES inlet/outlet read/write
- `attempt_to_solve()` — boundary re-application

All existing `'indirect'` and `'direct'` branches are untouched.

### 9.2 Source/Sink specification

Sources require `p` and `fluid`:
```python
conn.set_attr(p=conexion_params['6_p'], fluid=conexion_params['6_f'])
```
Temperature is set by the coupling loop (or profile for initial guess).

Sinks accept whatever arrives — no explicit specification needed.

### 9.3 Mode 5 HX sizing

The `HighT_Charge_HX` is a `HeatExchanger`:
- Design: `ttd_l = 20` forces kA computation
- Offdesign: kA from stored design
- Pressure drops: `pr1 = 0.98, pr2 = 0.98`
- kA can be stored/loaded from `mode1_kA.txt` (shared with Mode 1) or a
  dedicated `mode5_kA.txt`

### 9.4 Mode 3 regime switching

In `set_operation_mode()`:
```python
if tank_cfg == '2tank_direct':
    T_top = profile[0] if prev_TES_lay == 'Charge' else profile[-1]
    if T_top >= conexion_params['5_T']:
        # Regime A: build cold mixing network
    else:
        # Regime B: build auxiliary network
```

### 9.5 Mode 5 trigger adjustment

Change `get_mode()` to check `T_ptc_out > 5_T + 40` before Mode 1,
using the already-available `_read_T_ptc_out()` function.
