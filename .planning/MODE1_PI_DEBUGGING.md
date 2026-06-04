# Mode 1 Parallel/Indirect (PI) Convergence & Debugging Guide

This document gathers all technical findings, options attempted, failure modes, and mathematical analyses for **Mode 1 Parallel/Indirect (PI)** operation in the PBTES simulation codebase. It is designed to guide a subsequent agent in debugging the solver convergence issues without breaking existing functionality.

---

## 1. Overview of Mode 1 PI Topology & Governing Physics

In the **Parallel / Indirect (PI)** layout, Mode 1 represents the operational state where solar irradiance is high enough to simultaneously serve the galvanizing process and charge the thermal energy storage (TES) tank.

### 1.1 Physical Layout
- **Primary Loop**: Heat Transfer Fluid (Solar Salt) is pumped through the Parabolic Trough Collector (PTC) field, where it is heated. The flow then splits:
  - Part goes to the process branch: through the **Preheater HX** (auxiliary heater, which is off in Mode 1) and the **Process HX** (extracts $Q_{\text{proc}} = -450\text{ kW}$).
  - Part goes to the storage branch: through the hot side of the **Charge TES HX** (transfers heat to the storage loop).
  - The two streams merge and return to the PTC field.
- **Secondary Loop**: Driven by a separate pump, Solar Salt is drawn from the bottom of the TES tank (cold side, $T_{13} = T_{\text{tes, bot}}$), heated in the **Charge TES HX** (cold side), and reinjected at the top of the TES tank ($T_{14} = T_{\text{charge, in}}$).

### 1.2 Mathematical Formulation (Degrees of Freedom)
In TESPy, the system must have exactly zero degrees of freedom (DOFs) to solve.

#### Design Mode
- **Splitter/Merge**: Mass flow fraction is determined by the solver to satisfy the design constraints.
- **Fixed Parameters**:
  - Process HX heat load: $Q_{\text{proc}} = -450\text{ kW}$
  - Preheater HX heat load: $Q_{\text{pre}} = 0$ (auxiliary off)
  - Process inlet temperature: $T_5 = 520^\circ\text{C}$
  - Process return temperature: $T_6 = 480^\circ\text{C}$
  - PTC outlet temperature: $T_2 = 560^\circ\text{C}$
  - Charge HX lower terminal temperature difference: $\text{ttd}_l = 20\text{ K}$
  - TES secondary cold inlet: $T_{13} = 450^\circ\text{C}$ (design point bottom)
  - TES secondary hot outlet: $T_{14} = 490^\circ\text{C}$ (design point top)
- **Solved Variables**: PTC aperture area ($A_{\text{ptc}}$), Charge HX size ($\text{kA}$), loop mass flows.

#### Off-Design Mode
- **Fixed Parameters**:
  - PTC aperture area: $A_{\text{ptc}}$ fixed to design value (e.g., $1500\text{ m}^2$).
  - Charge HX heat transfer coefficient: $\text{kA}$ fixed to design value.
  - Process HX heat load: $Q_{\text{proc}} = -450\text{ kW}$
  - Preheater HX heat load: $Q_{\text{pre}} = 0$
  - Process inlet temperature: $T_5 = 520^\circ\text{C}$
  - Process return temperature: $T_6 = 480^\circ\text{C}$
  - TES secondary cold inlet: $T_{13} = T_{\text{tes, bot}}$ (from transient tank model)
  - TES secondary mass flow: $m_{13} = m_{\text{tes, design}}$ (from design point)
- **Solved Variables**: PTC outlet temperature ($T_2$), primary split mass flows, secondary outlet temperature ($T_{14}$).

---

## 2. Options and Procedures Attempted

The following strategies have been implemented to improve solver robustness:

1. **Design Pre-Calculation**:
   - Limited the process heat load during design to a maximum of $60\%$ of the PTC field's design-point heat output ($Q_{\text{ptc, design}}$). This guarantees that at least $40\%$ surplus power is available for charging, allowing the design solver to converge reliably for small PTC areas ($500\text{ m}^2$) and large areas ($3000\text{ m}^2$) alike.
2. **$\epsilon$-NTU Effectiveness Seeding**:
   - Seeded initial guesses for the Charge HX outlet temperatures ($T_{10}$ and $T_{14}$) using a counter-flow $\epsilon$-NTU effectiveness model based on the current estimated mass flows and fixed $\text{kA}$.
3. **Warm-Starting Off-Design**:
   - Configured the off-design solver to load connection values ($T_0, m_0, h_0$) from the design-point solutions as starting guesses. This prevents the solver from using default fluid properties that crash CoolProp.
4. **Retry with Randomization**:
   - On solver failures, the orchestrator performs up to 5 attempts, randomizing the initial guesses of connection temperatures, mass flows, and pressures.

---

## 3. Failure Modes Analysis (The "Why")

Despite the improvements, the solver still encounters instability and failures during transient simulation (e.g., around step 559 and step 955 of a 90-day simulation), leading to fallback to Mode 2. Two critical issues have been identified:

### 3.1 The Thermodynamic Pinch-Point Conflict (Vanishing $\Delta T$)
In off-design Mode 1, the primary loop process inlet temperature $T_5$ is fixed at $520^\circ\text{C}$ and the preheater is off ($Q_{\text{pre}} = 0$). Since there is no temperature change across the preheater and the splitter, **the PTC outlet temperature $T_2$ is locked at $520^\circ\text{C}$**.

Consequently:
- The hot fluid entering the Charge HX ($T_9$) is always $520^\circ\text{C}$.
- The cold fluid entering the Charge HX is $T_{13} = T_{\text{tes, bot}}$.
- As the tank charges over several hours, the cold front moves up and the bottom temperature $T_{\text{tes, bot}}$ rises (approaching $480^\circ\text{C}$ or higher).
- The driving temperature difference for charging becomes extremely small: $\Delta T_{\text{drive}} = 520 - T_{\text{tes, bot}}$.
- Because the Charge HX has a large, fixed $\text{kA}$, the solver tries to transfer heat across a vanishing temperature difference. This forces the hot-side outlet temperature $T_{10}$ to pinch extremely close to the cold-side inlet $T_{13}$.
- Any numerical oscillation or solver step can easily push $T_{10} < T_{13}$, which corresponds to a negative terminal temperature difference ($\text{ttd}_l < 0$). This is physically impossible, causing CoolProp to fail and the solver to crash.

### 3.2 The Randomization Guess Bug
When a solver attempt fails, the retry loop randomizes connection temperatures within a broad range:
```python
T_bounds = (250.0, 650.0)  # or even wider (200.0, 700.0)
```
If the bottom of the tank is hot (e.g., $T_{\text{tes, bot}} = 450^\circ\text{C}$), and the randomization routine assigns a guess temperature of $300^\circ\text{C}$ to $T_{10}$ (the hot outlet), then:
$$\text{ttd}_l = T_{10} - T_{13} = 300 - 450 = -150\text{ K} < 0$$
TESPy detects this negative $\text{ttd}_l$ on the very first iteration of the retry and immediately raises an `Invalid value` exception, aborting the retry attempt. **Thus, the randomization logic itself generates invalid guesses that doom the retries to immediate failure.**

### 3.3 The Operational Gap
Currently, the threshold for Mode 1 viability is:
$$\text{charge\_viable} = (T_{\text{ptc\_est}} > T_{\text{tes, top}} + \Delta T_{\text{min}})$$
$$\text{with } \Delta T_{\text{min}} = 35\text{ K} \quad \text{and} \quad T_{\text{charge\_in}} - T_{\text{tes, bot}} \ge 35\text{ K}$$
However, this check does not account for the pinch point between the fixed process temperature ($520^\circ\text{C}$) and the rising tank bottom temperature ($T_{\text{tes, bot}}$). If $T_{\text{tes, bot}} > 480^\circ\text{C}$, charging via a $520^\circ\text{C}$ source is no longer thermodynamically stable.

---

## 4. Actionable Debugging Instructions for the Next Agent

To resolve these issues, follow these steps sequentially:

### Step 1: Constraint-Aware Randomization
Modify `_randomize_conn_guesses` in `pbtes/simulation/solver.py` so that it respects thermodynamic boundaries:
- For any connection that acts as a heat exchanger outlet, the randomized guess must be bounded by the inlet temperature of the opposite side.
- For example, in charging modes, the hot outlet $T_{10}$ must be guessed in the range $[T_{13} + 2.0, 560.0]$, never below $T_{13}$.

### Step 2: Dynamic Mode 1 Viability Threshold
Refine the `get_mode` logic in `pbtes/simulation/solver.py`:
- Explicitly disable Mode 1 if the tank bottom temperature is too high relative to the process temperature:
  $$T_{\text{tes, bot}} > T_5 - \Delta T_{\text{pinch}}$$
  where $T_5 = 520^\circ\text{C}$ and $\Delta T_{\text{pinch}} \approx 35\text{ K}$ (i.e., disable Mode 1 if $T_{\text{tes, bot}} > 485^\circ\text{C}$).
- Ensure that when Mode 1 is disabled, the system transitions smoothly to Mode 2 (solar to process only) or Mode 5 (if the top of the tank is hot enough for high-T charging), leaving no operational gaps.

### Step 3: Verify Separately
- Fix and test **Mode 1 first**. Do not attempt to debug multiple modes simultaneously.
- Verify using `python -m pytest tests/test_modes.py` to ensure design-point convergence is preserved.
- Verify using short simulation runs (e.g., 7 days) before launching full seasonal runs.
