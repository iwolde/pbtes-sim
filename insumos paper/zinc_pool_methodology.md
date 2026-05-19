# Dynamic Zinc Pool Model — Methodology

## Nomenclature

| Symbol | Description | Units |
|--------|-------------|-------|
| $T_z$ | Zinc pool temperature | °C |
| $T_a$ | Ambient temperature | °C |
| $T_s$ | Steel parts inlet temperature | °C |
| $T_{\text{HX,out}}$ | Process heat exchanger hot-side outlet temperature | °C |
| $m_z$ | Mass of zinc in the bath | kg |
| $c_{p,z}$ | Specific heat of molten zinc | J/(kg·K) |
| $c_{p,s}$ | Specific heat of steel | J/(kg·K) |
| $\dot{m}_s$ | Steel mass throughput | kg/h |
| $UA$ | Overall heat loss coefficient | W/K |
| $\dot{Q}_{\text{HX}}$ | Heat delivered by process heat exchanger | kW |
| $\dot{Q}_{\text{loss}}$ | Heat loss to ambient | kW |
| $\dot{Q}_{\text{parts}}$ | Heat absorbed by dipped steel parts | kW |
| $\Delta T_{\text{TTD}}$ | Terminal temperature difference (HX approach) | K |
| $\Delta t$ | Time step | s (3600) |
| $H_{\text{op}}$ | Operating hours (start, end) | h |
| $D_{\text{op}}$ | Operating days per week | — |

---

## 1. Physical Motivation

Hot-dip galvanizing baths are large, open vessels containing molten zinc maintained between approximately 445–460 °C. Steel components are immersed in the bath, extracting heat as they are heated from ambient to the zinc temperature. Simultaneously, the bath loses heat to the surroundings through its insulated walls and exposed surface. The process heat exchanger—fed by the solar field, the packed-bed thermal energy storage (PBTES), or an auxiliary heater—must supply sufficient thermal power to compensate for both heat sinks and maintain the zinc pool within its operational temperature band.

Conventional quasi-steady simulations treat the process side as a fixed-temperature, fixed-demand boundary condition. This simplification neglects (a) the substantial thermal inertia of the zinc inventory (~50–200 metric tons), (b) the production schedule that modulates the heat extraction rate, and (c) the feedback between zinc pool temperature and the heat transfer rate through the process HX. The model presented here addresses these limitations while preserving full compatibility with the existing quasi-steady simulation framework.

---

## 2. Model Description

### 2.1 Lumped-Capacitance Formulation

The zinc bath is modeled as a well-mixed, lumped thermal mass. The single-node energy balance is:

\[
\boxed{m_z \, c_{p,z} \, \frac{dT_z}{dt} = \dot{Q}_{\text{HX}} - \dot{Q}_{\text{loss}} - \dot{Q}_{\text{parts}}}
\qquad \text{(1)}
\]

This formulation is justified by:
- **High thermal conductivity of liquid zinc** (~50 W/(m·K)), which promotes rapid internal equilibration.
- **Continuous convection induced by part immersion**, which aids mixing.
- **Slow dynamics**: with $m_z \sim 150$ t and $c_{p,z} \sim 512$ J/(kg·K), the thermal capacitance is ~77 MJ/K, yielding characteristic thermal time constants of hours—well matched to the 1 h simulation step.

### 2.2 Heat Loss to Ambient

Heat loss through the bath insulation and exposed surface is modeled via a lumped overall heat transfer coefficient:

\[
\dot{Q}_{\text{loss}} = UA \, (T_z - T_a) \times 10^{-3}
\qquad \text{(2)}
\]

where $UA$ (W/K) aggregates conduction through the refractory lining and natural convection/radiation from the bath surface. For a typical industrial galvanizing kettle of ~7 m diameter with 0.75 m insulation ($k \approx 0.03$ W/(m·K)), $UA \approx 300$–$800$ W/K.

### 2.3 Heat Extraction by Dipped Parts

Steel parts entering the bath at ambient temperature must be heated to the zinc pool temperature. The sensible heat extracted is:

\[
\dot{Q}_{\text{parts}}(t) =
\begin{cases}
\dot{m}_s \, c_{p,s} \, (T_z - T_s) \times (3600)^{-1} \times 10^{-3}, & \text{if operating at hour } t \\[4pt]
0, & \text{otherwise}
\end{cases}
\qquad \text{(3)}
\]

This formulation conservatively neglects:
- The latent heat of zinc solidification onto the part surface (coating mass is small relative to bulk zinc).
- The enthalpy of phase change in the steel (the Curie and austenitization transitions occur above typical galvanizing temperatures or are negligible).
- Pre-heating of parts prior to immersion (a common industrial practice that would reduce $\dot{Q}_{\text{parts}}$).

These simplifications make the model a worst-case upper bound on process heat demand.

### 2.4 Production Schedule

Production is assumed to follow a deterministic weekly schedule defined by three parameters:

\[
\text{is\_operating}(t) =
\begin{cases}
\text{True}, & \text{if } H_{\text{start}} \leq t_{\text{hour}} < H_{\text{end}} \;\land\; \text{weekday}(t) < D_{\text{op}} \\
\text{False}, & \text{otherwise}
\end{cases}
\qquad \text{(4)}
\]

Default values are $H_{\text{start}} = 8$, $H_{\text{end}} = 20$ (12 h/day operation) and $D_{\text{op}} = 5$ (Monday through Friday). The schedule is fully parameterized and can be adapted to any industrial shift pattern.

---

## 3. Coupling with the Quasi-Steady Simulation

### 3.1 Process Heat Exchanger: From Fixed Boundary to Dynamic Coupling

In the base simulation, the process HX is constrained in off-design mode by **both** a fixed heat duty $Q = Q_{\text{design}}$ and a fixed hot-side outlet temperature $T_{\text{HX,out}} = T_{\text{6,design}}$. This double constraint forces the heat exchanger to deliver a predetermined amount of heat regardless of the downstream process state.

When the zinc pool model is active, the coupling is modified as follows:

| Constraint | Design mode (sizing) | Off-design (base) | Off-design (zinc pool active) |
|-----------|---------------------|-------------------|-------------------------------|
| $Q_{\text{HX}}$ | Fixed ($Q_{\text{design}}$) | Fixed ($Q_{\text{design}}$) | **Free** |
| $T_{\text{HX,out}}$ | Fixed ($T_{\text{6,design}}$) | Fixed ($T_{\text{6,design}}$) | **$T_z + \Delta T_{\text{TTD}}$** |

In off-design mode with the zinc pool active, the process HX operates with its stored heat transfer area ($kA$) from the design point, a free heat duty, and a hot-side outlet temperature driven by the instantaneous zinc pool temperature:

\[
T_{\text{HX,out}} = T_z + \Delta T_{\text{TTD}}
\qquad \text{(5)}
\]

where $\Delta T_{\text{TTD}}$ is the minimum terminal temperature difference (default 20 K). This constraint ensures thermodynamic consistency: the heat-transfer fluid (NaK, molten salt, or CO₂) leaving the HX must be hotter than the zinc pool to transfer heat into it. The TESPy solver then computes the actual heat duty $\dot{Q}_{\text{HX}}$ from the component $kA$ and the prevailing inlet conditions, yielding a physically consistent heat transfer rate that responds to the zinc pool's thermal state:

- **Cold zinc pool** ($T_z \downarrow$) → lower $T_{\text{HX,out}}$ → larger $\Delta T$ across HX → increased $\dot{Q}_{\text{HX}}$ → accelerated warm-up.
- **Hot zinc pool** ($T_z \uparrow$) → higher $T_{\text{HX,out}}$ → smaller $\Delta T$ across HX → reduced $\dot{Q}_{\text{HX}}$ → self-limiting feedback.

This feedback loop operates across all operating modes (1 through 6), as the process HX participates in every network topology.

### 3.2 Integration into the Simulation Loop

Figure 1 illustrates the modified quasi-steady time-marching algorithm. The zinc pool model is interleaved with the existing TES–network coupling iteration, adding negligible computational overhead (~1 ms per time step for the lumped-capacitance update).

```
┌─────────────────────────────────────────────────────┐
│  For each time step t = 1 ... N_hours:              │
│                                                     │
│  1. Set T_HX_out = T_z(t) + ΔT_TTD                  │ ← Zinc pool → network
│     (modifies process HX boundary condition)         │
│                                                     │
│  2. Select operating mode (1–6) based on:            │
│     irradiance, TES state, zinc temperature          │
│                                                     │
│  3. Solve TESPy network (off-design)                 │
│     ├─ PTC, HX components, TES coupling iteration    │
│     └─ Output: Q̇_HX(t), mass flows, temperatures     │
│                                                     │
│  4. Update zinc pool:                                │ ← Network → zinc pool
│     T_z(t+1) = T_z(t) + (Q̇_HX − Q̇_loss − Q̇_parts)·Δt │
│                              ──────────────────────  │
│                                  m_z · c_p,z         │
│                                                     │
│  5. Store: T_z(t+1), Q̇_HX(t), T_HX_out(t)            │
└─────────────────────────────────────────────────────┘
```

The sequential coupling (network solve → pool update → next step) corresponds to a forward Euler integration of the pool ODE. This is numerically stable given the large thermal capacitance ($\sim 10^8$ J/K) relative to the 3600 s time step.

### 3.3 Initial Condition

The zinc pool is initialized at a user-specified temperature $T_{z,0}$ (default 450 °C), representing either a freshly heated bath or a steady operating condition. A spin-up period of $\sim$24–48 h is recommended before analyzing results to allow the pool dynamics to reach a quasi-periodic state driven by the solar diurnal cycle and production schedule.

---

## 4. Numerical Implementation

### 4.1 Time Discretization

Equation (1) is integrated with an explicit forward Euler scheme:

\[
T_z^{n+1} = T_z^n + \frac{\Delta t}{m_z \, c_{p,z}} \left( \dot{Q}_{\text{HX}}^n - \dot{Q}_{\text{loss}}^n - \dot{Q}_{\text{parts}}^n \right)
\qquad \text{(6)}
\]

where superscripts $n$ and $n+1$ denote successive time steps and $\Delta t = 3600$ s (1 hour).

### 4.2 Convergence Handling

The process HX off-design constraint modification (Section 3.1) is applied automatically by the `set_operation_mode` routine whenever the zinc pool is active and the solve mode is `offdesign`. The existing retry pipeline (`attempt_to_solve`)—which randomizes initial guesses and falls back to Mode 4 (standby) on persistent non-convergence—remains in place and applies identically with or without the zinc pool coupling. No additional solver tuning was required, as the change replaces one fixed constraint ($Q$) with another fixed constraint ($T_{\text{HX,out}}$), preserving the degrees of freedom in the TESPy equation system.

### 4.3 Optional Activation

The zinc pool model is activated by passing a `zinc_pool_params` dictionary to the `Solver` constructor. When absent or `None`, the legacy fixed-demand behavior is preserved without any code-path modification. This design allows direct A/B comparison of simulation results with and without dynamic process modeling.

---

## 5. Parameters and Default Values

| Parameter | Symbol | Default | Source / Rationale |
|-----------|--------|---------|--------------------|
| Zinc mass | $m_z$ | 150 000 kg | Typical medium-size galvanizing kettle (~7 m × 3 m, ~60% fill) |
| Initial temperature | $T_{z,0}$ | 450 °C | Midpoint of industrial operating range (445–460 °C) |
| Zinc specific heat | $c_{p,z}$ | 512 J/(kg·K) | CoolProp, INCOMP::Zinc at 450 °C |
| Heat loss coefficient | $UA$ | 500 W/K | Estimated from 0.75 m mineral wool insulation, 7 m tank diameter, ~40 m² exposed area |
| Terminal temperature difference | $\Delta T_{\text{TTD}}$ | 20 K | Typical design margin for liquid–liquid HX; tunable |
| Steel throughput | $\dot{m}_s$ | 5000 kg/h | Representative hourly processing rate |
| Steel specific heat | $c_{p,s}$ | 460 J/(kg·K) | AISI 1010 carbon steel, 20–450 °C average |
| Steel inlet temperature | $T_s$ | 25 °C | Ambient; conservatively assumes no pre-heating |
| Operating start hour | $H_{\text{start}}$ | 8 | Industrial morning shift |
| Operating end hour | $H_{\text{end}}$ | 20 | 12 h/day operation |
| Operating days/week | $D_{\text{op}}$ | 5 | Monday–Friday |

All parameters are user-configurable. The model accepts a flat dictionary, enabling straightforward parametric sweeps.

---

## 6. Energy Accounting

### 6.1 Direct Measurements

The modified `_collect_step_signals` routine directly reads the process HX heat duty ($\dot{Q}_{\text{HX}}$) from the solved TESPy network via `process_hx.Q.val`. This value—not the design-point heat demand—is the actual heat transferred to the zinc pool during the time step.

### 6.2 Cumulative Metrics

The following cumulative quantities are tracked for post-processing and reported in the output CSV:

- **`zinc_pool_temp`**: Instantaneous zinc pool temperature at end of time step (°C).
- **`process_hx_Q_kW`**: Actual heat transferred through process HX (kW).

The existing energy contributions—`solar_to_proc_kJ`, `tes_to_proc_kJ`, `aux_to_proc_kJ`—continue to be reported and represent the energy *supplied* by each source. The zinc pool model adds the *utilization* side: the actual heat received by the process, accounting for thermal inertia and the feedback between pool temperature and HX performance.

---

## 7. Model Assumptions and Limitations

### 7.1 Assumptions

1. **Perfect mixing**: The zinc pool is treated as a single lumped node. Temperature stratification within the bath is neglected.
2. **Constant thermophysical properties**: $c_{p,z}$, $c_{p,s}$, and $UA$ are held constant over the simulation. Temperature-dependent property variation is small over the $445$–$460$ °C operating range (< 3% for zinc $c_p$).
3. **Negligible latent effects**: Zinc solidification on part surfaces and steel phase transformations are omitted. Their thermal contribution is small relative to sensible heating (< 5% of total part heat extraction for typical coating thicknesses of 50–100 µm).
4. **Deterministic schedule**: Production follows a fixed weekly pattern. Stochastic variations (line stoppages, maintenance, variable throughput) are not modeled.
5. **No pre-heating**: Parts enter the bath at ambient temperature. In practice, many lines use pre-heating or drying ovens that reduce the thermal load.
6. **Quasi-steady network**: The TESPy network solves a steady-state problem at each time step. The 1 h step is assumed short enough that irradiance, ambient temperature, and zinc pool temperature are approximately constant within each step.

### 7.2 Limitations

- **Single-node pool**: Cannot resolve axial or radial temperature gradients in very large baths. For baths exceeding ~300 t, a multi-node extension may be warranted.
- **Constant $UA$**: Heat loss varies with bath level, surface condition (oxide layer), and wind speed. The lumped $UA$ is a first-order approximation.
- **No zinc consumption accounting**: The mass of zinc in the bath decreases as coating is deposited on parts. The associated mass loss is negligible over daily timescales (~0.1–0.3% per day).
- **Unidirectional coupling**: The zinc temperature drives $T_{\text{HX,out}}$, but the pool does not feed back into the TES state-of-charge calculation or mode selection logic (other than through the solved network). Future extensions could make zinc temperature a mode-selection criterion.

---

## 8. Validation Strategy

Validation is performed at two levels:

1. **Unit-level**: Standalone tests verify the `ZincPool` class energy balance (the pool temperature must respond correctly to applied heat, ambient losses, and part throughput) and schedule logic (weekend/weekday, operating/non-operating hours).

2. **System-level**: The integrated simulation is validated by:
   - Comparing results with and without the zinc pool model (the pool temperature trace should drift toward its equilibrium when $\dot{Q}_{\text{HX}}$ is balanced by losses and part demand).
   - Checking that the pool temperature remains within the physical operating band ($445$–$460$ °C) under nominal solar conditions.
   - Verifying that the solar fraction computed with the dynamic pool is consistent with (and not higher than) the fixed-demand case—the dynamic model is more conservative because it does not credit heat "delivered" that cannot be transferred due to temperature pinch.

---

## 9. Reference Implementation

The model is implemented in the `ZincPool` class within the file `coreV5.py`. Usage example:

```python
from coreV5 import Solver

zinc_pool_params = {
    'mass': 150e3,              # 150 metric tons of zinc
    'temp_initial': 450,         # starting temperature, °C
    'UA_loss': 500,              # heat loss coefficient, W/K
    'ttd_hx': 20,                # terminal temperature difference, K
    'mass_steel_per_hour': 5000, # kg/h steel throughput
    'op_start_hour': 8,          # production starts at 08:00
    'op_end_hour': 20,           # production ends at 20:00
    'op_days_per_week': 5,       # Mon–Fri
}

solver = Solver(
    tes_params=tes_params,
    component_params=component_params,
    conexion_params=conexion_params,
    HTF='INCOMP::SolarSalt',
    zinc_pool_params=zinc_pool_params,  # ← enables dynamic pool model
)
solver.initialize_modes()
results = solver.run_quasi_steady_simulation(days_to_simulate=365)
```

Omitting `zinc_pool_params` (or passing `None`) restores the legacy fixed-demand behavior.
