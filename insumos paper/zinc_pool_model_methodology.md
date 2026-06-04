# Zinc Pool Dynamic Thermal Model — Methodology

## 1. Process Description

Hot-dip galvanizing consists of immersing steel parts in a bath of molten zinc
maintained at approximately 450 °C. The bath is a large, well-mixed reservoir
(typically 100–300 metric tons) that loses heat through two principal
mechanisms: (i) thermal losses through the insulated tank walls to the
environment, and (ii) sensible heat absorbed by cold steel parts introduced
into the bath. To sustain the target operating temperature, a thermal energy
supply system — in this work, a parabolic trough collector (PTC) field coupled
to a packed-bed thermal energy storage (PBTES) — delivers heat to the zinc pool
via an intermediate heat transfer fluid (HTF) loop and a process heat exchanger.


## 2. Lumped-Capacitance Model

Given the high thermal conductivity of molten zinc and the turbulent mixing
induced by the dipping operation, the bath is treated as a single lumped
thermal mass. The energy balance for the zinc pool is:

\[
m_z \, c_{p,z} \, \frac{dT_z}{dt} = \dot{Q}_{hx} - \dot{Q}_{\text{loss}} - \dot{Q}_{\text{parts}}
\tag{1}
\]

where:

| Symbol | Description | Units |
|--------|-------------|-------|
| \(m_z\) | Mass of zinc in the bath | kg |
| \(c_{p,z}\) | Specific heat of molten zinc | J·kg⁻¹·K⁻¹ |
| \(T_z\) | Zinc pool temperature | °C |
| \(\dot{Q}_{hx}\) | Heat transfer rate from the process HX into the pool | W |
| \(\dot{Q}_{\text{loss}}\) | Heat loss rate to ambient through tank insulation | W |
| \(\dot{Q}_{\text{parts}}\) | Heat extraction rate by cold steel parts | W |
| \(t\) | Time | s |

Equation (1) is integrated forward in time using an explicit Euler scheme with
a time step \(\Delta t = 3600\) s (1 hour), consistent with the quasi-steady
simulation framework:

\[
T_z^{n+1} = T_z^n + \frac{\Delta t}{m_z \, c_{p,z}}
\left( \dot{Q}_{hx}^n - \dot{Q}_{\text{loss}}^n - \dot{Q}_{\text{parts}}^n \right)
\tag{2}
\]

where the superscript \(n\) denotes quantities evaluated at the beginning of
timestep \(n\).


## 3. Sub-Models

### 3.1 Heat Loss to Ambient

Heat losses through the insulated tank walls are modelled using a lumped
heat-loss coefficient:

\[
\dot{Q}_{\text{loss}} = (UA)_{\text{loss}} \; (T_z - T_{\text{amb}})
\tag{3}
\]

where \((UA)_{\text{loss}}\) is an effective overall heat transfer
coefficient–area product (W·K⁻¹) and \(T_{\text{amb}}\) is the ambient air
temperature obtained from the meteorological data file at each timestep.

### 3.2 Heat Extraction by Dipped Steel Parts

Cold steel parts absorb sensible heat as they are heated from their inlet
temperature \(T_{\text{steel}}\) to the bath temperature \(T_z\). The
instantaneous heat extraction rate during production hours is:

\[
\dot{Q}_{\text{parts}} = \dot{m}_s \, c_{p,s} \, (T_z - T_{\text{steel}})
\tag{4}
\]

where \(\dot{m}_s\) is the steel mass throughput (kg·s⁻¹), \(c_{p,s}\) is the
specific heat of steel (J·kg⁻¹·K⁻¹), and \(T_{\text{steel}}\) is the
temperature of the steel parts entering the bath (taken as ambient).

Equation (4) assumes the steel parts reach thermal equilibrium with the bath
before exiting, and neglects the latent heat of the zinc coating that solidifies
on the part surface. These simplifications are consistent with the
lumped-capacitance approach and are conservative with respect to process demand
(the coating contribution is typically less than 5 % of the sensible heating
load).

### 3.3 Operating Schedule

The production line operates on a user-defined weekly schedule. Parts are
dipped only during designated working hours. The schedule is defined by three
parameters:

- \(h_{\text{start}}\): start hour of the working day (0–23)
- \(h_{\text{end}}\): end hour of the working day (0–23)
- \(D_w\): number of operating days per week (1 = Monday only, 5 = Monday–Friday)

The parts heat load is active only when the simulation timestamp satisfies both:

\[
h_{\text{start}} \leq t_{\text{hour}} < h_{\text{end}}
\quad \text{and} \quad
\text{weekday}(t) < D_w
\tag{5}
\]

Outside operating hours (nights, weekends), \(\dot{Q}_{\text{parts}} = 0\) and
the pool cools solely by ambient losses.


## 4. Coupling with the Quasi-Steady Solar Plant Simulation

### 4.1 Overview

The zinc pool model is integrated into the existing hourly quasi-steady
simulation of the solar thermal plant. The plant model, built with the TESPy
library, represents the PTC field, the packed-bed TES, the auxiliary heater,
and the process heat exchanger as a steady-state thermodynamic network solved
at each hourly timestep. The zinc pool introduces dynamic feedback between the
process side and the supply side of the system.

### 4.2 Process Heat Exchanger Coupling

The process heat exchanger (HX) is a shell-and-tube or similar unit where the
hot-side HTF (e.g., Solar Salt) transfers heat to the zinc bath. In the
TESPy network, it is modelled as a `SimpleHeatExchanger` component. The
coupling operates as follows:

**Design point.** During the design initialization, the process HX is sized with
a fixed heat duty \(\dot{Q}_{hx}^{\text{des}}\) and a fixed hot-side outlet
temperature \(T_{h,out}^{\text{des}}\). TESPy computes the heat transfer
coefficient–area product (\(kA\)) of the HX from these constraints.

**Off-design operation (zinc pool active).** At each hourly timestep, the
hot-side outlet temperature of the process HX is freed and replaced by a
terminal temperature difference (TTD) constraint:

\[
T_{h,out} = T_z + \Delta T_{\text{TTD}}
\tag{6}
\]

where \(\Delta T_{\text{TTD}}\) is the minimum approach temperature (default
20 K). The heat duty \(\dot{Q}_{hx}\) is left unconstrained; TESPy solves for
the actual heat transfer from the stored \(kA\), the hot-side inlet conditions,
and the outlet temperature boundary condition given by (6).

This formulation captures the correct physical behaviour: when the zinc pool
temperature is below the design value, the larger temperature difference across
the HX drives a higher heat transfer rate, helping the pool recover toward the
target. Conversely, if the pool approaches or exceeds the target, the heat
transfer rate self-limits.

### 4.3 Feedback Loop

The coupling follows a sequential, explicit scheme at each hourly timestep
\(n\):

1. **Set boundary condition.** The zinc pool temperature \(T_z^n\) (known from
   the previous timestep) determines the process HX outlet constraint via (6).
2. **Solve supply network.** The TESPy network is solved in off-design mode,
   iterating between the packed-bed TES 1D model and the HTF loop until
   convergence. The process HX outlet temperature is fixed to the value from
   step 1, and the heat duty \(\dot{Q}_{hx}^n\) emerges from the solution.
3. **Update zinc pool.** The heat duty \(\dot{Q}_{hx}^n\) obtained from the
   network solve is used together with Equations (3)–(5) to advance the zinc
   pool temperature to \(T_z^{n+1}\) via (2).
4. **Proceed to next timestep.** The updated zinc temperature becomes the
   boundary condition for timestep \(n+1\).

The explicit coupling is justified by the large thermal inertia of the zinc
bath: with a typical heat capacity of \(\sim 70\)–\(100\) MJ·K⁻¹, the
temperature changes by at most a few Kelvin per hour, making the decoupling
error negligible.

### 4.4 Fixed-Demand Mode (Legacy)

When the zinc pool model is disabled (i.e., `zinc_pool_params = None`), the
simulation reverts to a constant-demand behaviour: the process HX operates with
a fixed heat duty \(\dot{Q}_{hx}^{\text{des}}\) and a fixed outlet temperature
\(T_{h,out}^{\text{des}}\). This mode is retained for backward compatibility,
testing, and comparison with constant-demand baselines. All production
simulations use the dynamic zinc pool model (always ON).


## 5. Model Parameters

The zinc pool model exposes the parameters listed in Table 1. All have
reasonable defaults suitable for a medium-scale galvanizing plant.

**Table 1. Zinc pool model parameters.**

| Parameter | Symbol | Default | Description |
|-----------|--------|---------|-------------|
| `mass` | \(m_z\) | \(150 \times 10^3\) kg | Mass of zinc in the bath |
| `temp_initial` | \(T_z^0\) | 450 °C | Initial zinc temperature |
| `cp_zinc` | \(c_{p,z}\) | 512 J·kg⁻¹·K⁻¹ | Specific heat of molten zinc |
| `UA_loss` | \((UA)_{\text{loss}}\) | 500 W·K⁻¹ | Heat loss coefficient to ambient |
| `target_temp` | \(T_{\text{target}}\) | 450 °C | Target operating temperature |
| `ttd_hx` | \(\Delta T_{\text{TTD}}\) | 20 K | Terminal temperature difference |
| `op_start_hour` | \(h_{\text{start}}\) | 8 | Start of working day |
| `op_end_hour` | \(h_{\text{end}}\) | 20 | End of working day |
| `op_days_per_week` | \(D_w\) | 5 | Operating days per week |
| `mass_steel_per_hour` | \(\dot{m}_s\) | 5000 kg·h⁻¹ | Steel throughput |
| `cp_steel` | \(c_{p,s}\) | 460 J·kg⁻¹·K⁻¹ | Specific heat of steel |
| `T_steel_inlet` | \(T_{\text{steel}}\) | 25 °C | Steel inlet temperature |


## 6. Assumptions and Limitations

1. **Lumped thermal mass.** The zinc bath is treated as isothermal. In practice,
   temperature gradients may exist near the bath surface and the HX, but the
   high thermal conductivity of molten zinc (\(\sim 50\) W·m⁻¹·K⁻¹) and
   continuous convective mixing make this a reasonable approximation for
   system-level studies.

2. **Constant thermophysical properties.** The specific heat and density of
   zinc are held constant. Over the narrow operating range of 430–470 °C, these
   properties vary by less than 3 %.

3. **Constant heat loss coefficient.** The \((UA)_{\text{loss}}\) lumps
   conduction through the refractory lining and insulation, as well as
   convection and radiation from the tank exterior, into a single linear
   coefficient. Radiation losses, which scale with \(T_z^4\), are small relative
   to conduction through a well-insulated tank in this temperature range.

4. **Neglected coating latent heat.** The heat extracted by the solidification
   of the zinc coating layer on the steel parts is omitted. For a typical
   coating thickness of 80–100 μm, the latent heat contribution is below 5 % of
   the sensible heat demand.

5. **Explicit coupling.** The explicit sequential coupling between the TESPy
   network and the zinc pool introduces a small temporal decoupling error. Given
   the one-hour timestep and the large thermal inertia of the bath, this error
   is negligible for system-level energy balances and solar fraction estimation.

6. **No upper temperature control.** The model does not impose a maximum
   operating temperature or active cooling. In practice, a galvanizing line
   would reduce or divert heat input if the bath overheats. In the simulated
   scenarios, the natural self-regulation of the HX (reduced heat transfer at
   higher \(T_z\)) mitigates overheating risk.


## 7. Nomenclature

| Symbol | Description | Units |
|--------|-------------|-------|
| \(c_{p,s}\) | Steel specific heat | J·kg⁻¹·K⁻¹ |
| \(c_{p,z}\) | Zinc specific heat | J·kg⁻¹·K⁻¹ |
| \(D_w\) | Operating days per week | — |
| \(h_{\text{start}}, h_{\text{end}}\) | Working day start/end hour | h |
| \(kA\) | HX conductance–area product | W·K⁻¹ |
| \(m_z\) | Zinc bath mass | kg |
| \(\dot{m}_s\) | Steel mass throughput | kg·s⁻¹ |
| \(\dot{Q}_{hx}\) | Heat from process HX to zinc pool | W |
| \(\dot{Q}_{\text{loss}}\) | Heat loss to ambient | W |
| \(\dot{Q}_{\text{parts}}\) | Heat to steel parts | W |
| \(t\) | Time | s |
| \(\Delta t\) | Simulation timestep | s |
| \(T_{\text{amb}}\) | Ambient temperature | °C |
| \(T_{h,out}\) | HTF temperature at process HX outlet | °C |
| \(T_{\text{steel}}\) | Steel inlet temperature | °C |
| \(T_z\) | Zinc pool temperature | °C |
| \((UA)_{\text{loss}}\) | Heat loss coefficient | W·K⁻¹ |
| \(\Delta T_{\text{TTD}}\) | Terminal temperature difference | K |


## 8. References

The lumped-capacitance approach follows standard practice for modelling
well-mixed thermal baths in industrial process heat applications. The explicit
coupling scheme is analogous to the sequential solver strategy used by the TESPy
library for off-design network calculations [Witte & Tuschy, 2020, *TESPy:
Thermal Engineering Systems in Python*, J. Open Source Softw.].

