# Mode Simplification — 4-Mode Topology for PI

*Created: 2026-06-10*  
*Status: **Implemented & Verified** (full-year simulation: SF=54.5%, 100% convergence)*

---

## 1. Motivation

The PI (Parallel/Indirect) topology currently defines 6 operating modes. Mode 1
(split-flow solar charging + process) has a fundamental thermodynamic constraint:
the splitter + preheater Q=0 chain locks PTC outlet to 520°C (recently fixed
with DNI-aware conn_02.T anchoring, but convergence remains fragile).

Mode 6 (dedicated PTC→TES charging with independent auxiliary process cycle) is
architecturally simpler and has proven robust convergence. Mode 5 (series
high-T charge via dedicated HX) covers the hot-TES charging niche.

**Question**: If Mode 6 covers cold/warm-TES charging and Mode 5 covers hot-TES
charging, is Mode 1 necessary?

## 2. Analysis

### 2.1 Mode 1's Thermodynamic Niche

Mode 1 tries to do two things at once:
- Serve process with solar heat (direct)
- Charge TES with excess solar (via splitter + Charge HX)

This is elegant because it avoids auxiliary fuel. The gap without Mode 1:
- **Medium DNI, warm TES (450-500°C)**: Mode 6 charges TES but burns aux for
  process (bad for SF). Mode 5 won't fire (thresholds too strict). Mode 2 wastes
  the charge opportunity. → Mode 1 fills this gap.

### 2.2 The Convergence Cost

After the conn_05.T fix, Mode 1 converges ~25% of attempted solar hours. The
rest fall back to Mode 2. The Charge HX kA (sized at 520°C) struggles with the
higher ΔT when PTC outlet exceeds its design temperature.

### 2.3 Mode 6 Already Covers Most of Mode 1's Function

| Condition | Mode 1 coverage | Mode 6 coverage |
|-----------|:---:|:---:|
| TES cold (<470°C), SOC < 0.40 | Yes | Yes (primary) |
| TES warm (470-500°C), SOC 0.4-0.8 | **Yes (fragile)** | Possible (sticky) |
| TES hot (>500°C), SOC < 0.90 | Blocked (ΔT too small) | Mode 5 takes over |

The only gap is warm-TES intermediate charging, which Mode 6 could cover if its
SoC threshold were raised from 0.40 to 0.80.

## 3. Proposed 4-Mode Scheme

| Mode | Solar | TES Action | Aux | When Selected |
|------|:-----:|:----------:|:---:|---------------|
| **2** | PTC→Process (direct) | Standby | No | Irr > E_proc, SoC > 0.80 or TES full |
| **5** | PTC→High-T HX→Process (series) | Charge | Yes* | Irr > E_charge, SoC < 0.90, T_bot < T_ptc_est − 20°C |
| **6** | PTC→Charge HX (dedicated cycle) | Charge | Yes** | Irr > E_charge, SoC < 0.80 |
| **3** | — | Discharge | No | Irr < E_proc, SoC > 0.02, T_top in range |
| **4** | — | Standby | Yes | Fallback (no sun, TES empty) |

\* Mode 5: Preheater tops up process temperature if needed.
\** Mode 6: Process runs on independent auxiliary-heated cycle (Cycle B).

### 3.1 Removed Modes

- **Mode 1**: Replaced by Mode 6 (cold-to-warm) + Mode 5 (warm-to-hot).
  Convergence fragility and splitter-temperature lock make it a poor tradeoff
  for PI topology.

### 3.2 Key Threshold Changes

| Threshold | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| Mode 5 trigger | `T_top > 520°C, SoC < 0.90` | `T_bot < T_ptc_est − 20°C, SoC < 0.90` | Bottom-cold check is physically meaningful for series-charge viability |
| Mode 6 sticky SoC | `SoC < 0.80` (sticky from 0.40) | `SoC < 0.80` (always) | Cover Mode 1's warm-TES niche |
| Mode 6 cold TES trigger | `SoC < 0.40, T_top < 470°C` | **Removed** | Simplified by universal SoC threshold |

### 3.3 Mode 6 Regimes (PI specific, from winter_logic)

| Regime | Season | Target T_set | Purpose |
|--------|--------|-------------|---------|
| **A** | Winter (JJA) | 300.1 °C | Freeze protection |
| **B** | Production (S-M) | 450.0 °C | Operational readiness |

The Mode 6 sticky logic keeps charging until SoC reaches 0.80 (Regime B) or
until the tank setpoint is reached (Regime A).

## 4. Tradeoff: Auxiliary Penalty

Under the 4-mode scheme, Mode 6 burns auxiliary to serve process while charging
TES. This reduces instantaneous solar fraction. However:

1. The auxiliary energy "spent" during Mode 6 charging is recovered later when
   Mode 3 discharges the same energy to process.
2. Mode 5 covers the solar-to-process-while-charging case without auxiliary.
3. The annual net SF impact depends on the ratio of Mode 6 to Mode 2+5 hours.

A quantitative comparison (6-mode vs 4-mode annual SF) should be part of the
control-logic assessment in the article.

## 5. Expected Benefits

1. **Convergence robustness**: Mode 1 convergence failures (~75% of attempts)
   are eliminated. Mode 6 has proven robust (dedicated PTC→TES loop).
2. **Simpler control logic**: 5 modes → 4 modes. Mode 1's heuristic `min_dT`
   checks (35K/65K/30K) are removed.
3. **Clearer article narrative**: Each mode has a distinct thermodynamic role
   with no overlapping function.
4. **SD topology unaffected**: SD has no splitter lock (Hot Tank upstream) and
   Mode 1 works robustly there. This proposal is PI-only.

## 6. Implementation Notes (Completed)

Changes made in:
- `pbtes/simulation/solver.py:get_mode()` — Mode 1 branch removed for PI; Mode 5/6 thresholds broadened; `_estimate_ptc_out` helper added; in-house PTC gate
- `pbtes/simulation/solver.py:_iterate_tes_coupling()` — Mode 5 coupling switch fixed (check both `charge_tes_hx` and `high_t_charge_hx`); `design_path` recalculated on Mode 4 fallback; Mode 4 fallback `use_init_path=False`
- `pbtes/network/system.py:create_network()` — Stale component `delattr` cleanup; conn_05.T=520 barrier extended for Parallel Mode 1 offdesign
- `pbtes/network/system.py:set_operation_mode()` — DNI-aware conn_02.T anchor for Mode 5 offdesign; Mode 1 DNI-aware anchor for Parallel topology
- `pbtes/config.py` — `E_min_mode1` disabled for PI (set to 1e9)
- `pbtes/network/system.py:solve_network()` — `design_path` passed conditionally with `use_init_path`
- Tests — all 101 pass (100 + 1 xpassed)

## 7. Relationship to Current Fix

The conn_05.T removal for PI Mode 1 (DNI-aware conn_02.T anchoring) was
implemented first and is used by the 4-mode scheme for Mode 5 offdesign.

## 8. Verification Results (2026-06-10)

Full-year simulation (A=1500 m², 8760 hours, 100% convergence):

| Metric | PI 6-mode (old) | PI 4-mode (new) | SD (reference) |
|---|---|---|---|
| Solar Fraction | 34.1% | **54.5%** | 55.4% |
| Mode 5 hours | 32 | **2,729** | — |
| Mode 3 hours | 808 | **4,446** | 3,697 |
| Mode 4 hours | 5,117 | **1,569** | 2,208 |
| to_tes (GJ/yr) | 1.34M | **6.25M** | 3.03M |
| tes_to_proc (GJ/yr) | 0.35M | **4.80M** | 3.89M |
| T_tes_top mean | 477°C | **515°C** | 499°C |
| Round-trip | 26.0% | **76.8%** | 128.1%* |

\* SD >100% due to direct-contact energy accounting convention.

Mode 6 was unused (0h) — Mode 5's `TES_bot < T_ptc_est − 20°C` fires first at
all solar hours. Mode 6 remains as backup for conditions where Mode 5 is not
viable (very warm TES bottom).

### Bugs fixed during implementation

- `design_path` not recalculated on Mode 4 fallback (`solver.py:1578`)
- Stale component references in `create_network` (added `delattr` cleanup)
- Mode 5 coupling switch checking wrong HX attribute (`hasattr(charge_tes_hx)` → also check `high_t_charge_hx`)
- Mode 4 fallback using `use_init_path=True` on incomplete design cache
- DNI-aware `conn_02.T` anchor for Mode 5 offdesign (replaces fragile fixed-aperture PTC solve)
- in-house PTC gate: 4-mode only activates for standard PTC model
