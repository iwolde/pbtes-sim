# Zinc Pool Transient Operating Assumptions & Methodology Bundle

This document establishes the authoritative mathematical, physical, and operational specifications for the transient behavior of the zinc galvanizing pool. It serves as a scientific reference for the journal publication to ensure absolute consistency in system-level thermal coupling and performance analysis.

---

## 1. Governing Dynamics (Lumped-Capacitance)

The zinc galvanizing bath is modeled using a transient, single-node lumped-capacitance energy balance. Due to the high thermal conductivity of molten zinc ($k_{\text{Zn}} \approx 50\text{ W/(m}\cdot\text{K)}$) and continuous convective mixing induced by the dipping process, spatial temperature gradients are neglected.

The transient energy equation is:
$$C_{\text{pool}} \frac{dT_{\text{Zn}}}{dt} = \dot{Q}_{\text{hx}} - \dot{Q}_{\text{losses}} - \dot{Q}_{\text{parts}}$$

where:
* **$C_{\text{pool}} = m_{\text{Zn}} \cdot c_{p,\text{Zn}}$**: Total thermal capacity of the molten bath.
* **$m_{\text{Zn}} = 150,000\text{ kg}$**: Mass of zinc in the bath.
* **$c_{p,\text{Zn}} = 512\text{ J/(kg}\cdot\text{K)}$**: Specific heat of molten zinc.
* **$\dot{Q}_{\text{hx}}$**: Thermal power input delivered from the primary HTF loop via the process heat exchanger (`Process_HX`) [W].
* **$\dot{Q}_{\text{losses}}$**: Environmental heat loss rate through the insulated tank walls [W].
* **$\dot{Q}_{\text{parts}}$**: Heat extraction rate by cold steel parts being dipped [W].

---

## 2. Transient Operating Regimes & Load Profiles

The plant operates on a rigid weekly schedule, defining two distinct thermal regimes:

```
        Active Production (Mon-Fri, 8 AM - 8 PM)
        ├── Steel throughput: ṁ_steel = 5,000 kg/h
        └── Q_parts = ṁ_steel * cp_steel * (T_Zn - T_amb) ≈ 271 kW
        
        Hot-Standby (Nights & Weekends)
        ├── Steel throughput: ṁ_steel = 0 kg/h
        └── Q_parts = 0 kW (Pool cools only via ambient losses)
```

### 2.1 Active Production Regime
* **Occurrence**: Monday through Friday, from **8:00 AM to 8:00 PM** (12 hours/day, 60 hours/week).
* **Thermal Load**: The steel parts enter the bath at ambient temperature ($T_{\text{steel,in}} = 25^\circ\text{C}$) and absorb sensible heat to reach the bath temperature ($T_{\text{Zn}}$):
  $$\dot{Q}_{\text{parts}} = \dot{m}_{\text{steel}} \cdot c_{p,\text{steel}} \left(T_{\text{Zn}} - T_{\text{steel,in}}\right)$$
  where $\dot{m}_{\text{steel}} = 5,000\text{ kg/h}$ ($1.389\text{ kg/s}$) and $c_{p,\text{steel}} = 480\text{ J/(kg}\cdot\text{K)}$.
  * *Typical Value*: At $T_{\text{Zn}} = 450^\circ\text{C}$, the parts heat rate is:
    $$\dot{Q}_{\text{parts}} = 1.389 \cdot 480 \cdot (450 - 25) \approx 283.3\text{ kW}$$

### 2.2 Hot-Standby Regime (Nights & Weekends)
* **Occurrence**: Monday through Friday from **8:00 PM to 8:00 AM**, plus the entire weekend (Saturday and Sunday).
* **Thermal Load**: No parts are processed ($\dot{m}_{\text{steel}} = 0\text{ kg/s}$), yielding $\dot{Q}_{\text{parts}} = 0\text{ W}$. The bath loses heat solely to the environment:
  $$\dot{Q}_{\text{losses}} = (UA)_{\text{loss}} \left(T_{\text{Zn}} - T_{\text{amb}}\right)$$
  where $(UA)_{\text{loss}} = 500\text{ W/K}$ and $T_{\text{amb}}$ is the hourly ambient temperature.
  * *Typical Value*: At $T_{\text{Zn}} = 450^\circ\text{C}$ and $T_{\text{amb}} = 15^\circ\text{C}$, the ambient heat loss is:
    $$\dot{Q}_{\text{losses}} = 500 \cdot (450 - 15) = 217.5\text{ kW}$$

---

## 3. Supply-Side Coupling & Thermostatic Self-Regulation

### 3.1 Heat Exchanger Coupling Boundary
The thermal coupling between the supply loop and the zinc bath is mediated by the Process Heat Exchanger (`Process_HX`). The outlet temperature of the primary HTF loop is constrained by the pool temperature and the approach temperature difference:
$$T_{\text{process,out}} = T_{\text{Zn}} + \Delta T_{\text{TTD}}$$
where $\Delta T_{\text{TTD}} = 20\text{ K}$ is the terminal temperature difference. 

### 3.2 Dynamic Self-Regulation
This boundary condition drives a physically accurate self-regulating feedback loop:
* **Temperature Crash**: If the zinc bath cools down (e.g., due to a high production load and low solar input), the temperature difference across the Process HX ($T_{\text{process,in}} - T_{\text{process,out}}$) widens. For a fixed heat transfer conductance ($kA$), this increases the heat transfer rate $\dot{Q}_{\text{hx}}$, helping the bath recover.
* **Overheating Mitigation**: As the bath temperature approaches or exceeds the target, the temperature difference narrows, which naturally caps the heat transfer rate $\dot{Q}_{\text{hx}}$.

### 3.3 Thermostatic Heat Capping in Code
To prevent the solar loop from overheating the bath above the target operating setpoint ($T_{\text{target}} = 450^\circ\text{C}$), the solver caps the absorbed heat input:
$$\dot{Q}_{\text{hx, used}} = \begin{cases}
\min\left(\dot{Q}_{\text{hx, available}}, \dot{Q}_{\text{needed}}\right), & \text{if } T_{\text{Zn}} \ge T_{\text{target}} \\
\dot{Q}_{\text{hx, available}}, & \text{if } T_{\text{Zn}} < T_{\text{target}}
\end{cases}$$
where:
$$\dot{Q}_{\text{needed}} = \dot{Q}_{\text{losses}} + \dot{Q}_{\text{parts}} + \frac{m_{\text{Zn}} \cdot c_{p,\text{Zn}} \left(T_{\text{target}} - T_{\text{Zn}}\right)}{\Delta t}$$
This represents a standard thermostatic bypass control where HTF bypasses the process heat exchanger once the bath has reached its setpoint.

---

## 4. Standby Heat Preservation & Auxiliary Heater Load

Because the bath must never solidify (the freezing point of eutectic zinc is $419.5^\circ\text{C}$), the auxiliary preheater (`Preheater_HX`) in the primary loop serves as the backup energy source during nighttime, weekends, and cloudy winter days.

* **Mode 4 Standby**: If solar input is zero ($\dot{Q}_{\text{ptc}} = 0$) and the storage is exhausted ($SoC < 0.05$), the system operates in Mode 4.
* **Standby Auxiliary Demand**: At night and on weekends, the auxiliary preheater must supply exactly enough thermal power to cover the ambient losses ($\approx 217.5\text{ kW}$) to keep the bath at $450^\circ\text{C}$. This constant thermal load represents the baseline parasitic loss of the plant.

---

## 5. Exergy Formulation of the Process Load

To characterize the thermodynamic quality of the heat delivered to the process, we define the transient process exergy demand. The exergy rate associated with the process heating ($\dot{E}x_{\text{process}}$) is:

$$\dot{E}x_{\text{process}} = \left(\dot{Q}_{\text{parts}} + \dot{Q}_{\text{losses}}\right) \cdot \left( 1 - \frac{T_{\text{amb}} + 273.15}{T_{\text{Zn}} + 273.15} \right)$$

The annual process exergy efficiency of the solar thermal plant is defined as:
$$\eta_{\text{ex, annual}} = \frac{\int \dot{E}x_{\text{process}} \, dt}{\int \dot{E}x_{\text{solar, in}} \, dt + \int \dot{E}x_{\text{aux, in}} \, dt}$$

where:
* **$\dot{E}x_{\text{solar, in}} = A_{\text{ptc}} \cdot DNI \cdot \left( 1 - \frac{4}{3}\frac{T_{\text{amb}, K}}{T_{\text{sun}, K}} + \frac{1}{3}\left(\frac{T_{\text{amb}, K}}{T_{\text{sun}, K}}\right)^4 \right)$**: Solar exergy input (Petela model, with $T_{\text{sun}} = 5778\text{ K}$).
* **$\dot{E}x_{\text{aux, in}} = \dot{Q}_{\text{aux}} \cdot \psi_{\text{fuel}}$**: Exergy input of the auxiliary heater (using a fuel exergy factor $\psi_{\text{fuel}} = 0.95$ for natural gas).

---

## 6. Model Assumptions & Scientific Boundaries

1. **Perfect Mixing**: We assume uniform spatial temperature ($T_{\text{Zn}}$) throughout the bath. Local temperature drops near the dipping point are neglected.
2. **Solidification Ignored**: The bath is assumed to remain liquid at all times ($T_{\text{Zn}} > 419.5^\circ\text{C}$). If $T_{\text{Zn}}$ falls below the freezing point in simulations due to a lack of auxiliary energy, the code does not model the latent heat of fusion or solid-phase thermal gradients.
3. **Linearized Convective Losses**: Conduction, convection, and radiation losses are lumped into a single linear coefficient $(UA)_{\text{loss}} = 500\text{ W/K}$. Since radiation scales with $T_{\text{Zn}}^4$, this represents an approximation that is valid over the narrow operating envelope ($430^\circ\text{C} - 470^\circ\text{C}$).
4. **Neglected Steel Oxidation**: The chemical reaction exergy (oxidation of zinc and steel) is omitted, as it contributes less than $1\%$ of the sensible heat requirements.
