# PBTES Solar Plant: Layouts, Modes, and Configurations

This document provides a comprehensive overview of the plant configurations, the distinction between different topologies, and how the operating modes dictate fluid routing.

---

## 1. Topologies & Tank Configurations

The project matrix explores four distinct architectural variants, formed by combining two routing **Topologies** (Parallel vs Series) and two **Tank Configurations** (Indirect vs Direct).

### 1.1 Parallel vs. Series (Topologies)

This defines how the Solar Field (PTC) interfaces with the Process Heat Exchanger and the Thermal Energy Storage during **charging modes (Mode 1 and Mode 6)**.

- **Parallel Topology**: The hot fluid exiting the PTC encounters a splitter. The flow is divided into two parallel branches: one branch serves the process heat demand, and the other branch goes to charge the TES. The returns from both branches are merged before heading back to the PTC.
- **Series Topology**: The hot fluid from the PTC travels through the system in a single series loop. It first passes through the Process Heat Exchanger to satisfy the industrial demand, and the remaining sensible heat is then passed through the TES to charge it, before returning to the PTC.

### 1.2 Indirect vs. Direct (Tank Configurations)

This defines whether the primary Heat Transfer Fluid (HTF) physically enters the packed bed.

- **Indirect Config**: The Primary Loop (PTC and Process) is completely isolated from the Secondary Loop (TES). They exchange heat via dedicated heat exchangers (`Charge_TES_HX` and `Discharge_TES_HX`). This allows using different fluids (e.g., NaK in the primary loop, molten salts in the TES loop) and protects the primary loop from dust or contamination from the packed bed rocks.
- **Direct Config**: There is only one fluid loop. The primary HTF (NaK) flows directly through the void spaces of the packed bed rock. The heat exchangers are removed (represented as simple pipes in the model) to eliminate the temperature approach (TTD) penalty.

---

## 2. System Architecture Diagrams

Below are the simplified drawings (PFDs) for the four possible plant dispositions during a standard charging/processing operation (e.g., Mode 6).

### 2.1 Parallel / Indirect (Baseline)
The baseline design. The solar loop splits to serve the process and an isolated TES loop.

```mermaid
graph LR
    subgraph Primary Loop (NaK)
        Pump --> PTC[Parabolic Trough]
        PTC --> SP{Splitter}
        SP -->|Branch 1| PHX(Process HX)
        SP -->|Branch 2| CHX(Charge TES HX)
        PHX --> MG{Merge}
        CHX --> MG
        MG --> Pump
    end
    
    subgraph Secondary Loop (TES)
        CHX -.->|Hot| TES[(Packed Bed)]
        TES -.->|Cold| CHX
    end
    
    subgraph Process Loop
        PHX ===>|Heat| ZP[[Zinc Pool]]
    end
```

### 2.2 Series / Indirect
A single primary path. It serves the process first, then the isolated TES loop.

```mermaid
graph LR
    subgraph Primary Loop (NaK)
        Pump --> PTC[Parabolic Trough]
        PTC --> PHX(Process HX)
        PHX --> CHX(Charge TES HX)
        CHX --> Pump
    end
    
    subgraph Secondary Loop (TES)
        CHX -.->|Hot| TES[(Packed Bed)]
        TES -.->|Cold| CHX
    end
    
    subgraph Process Loop
        PHX ===>|Heat| ZP[[Zinc Pool]]
    end
```

### 2.3 Parallel / Direct
A single fluid loop (NaK) that splits. One branch flows directly through the packed bed.

```mermaid
graph LR
    subgraph Single Loop (NaK)
        Pump --> PTC[Parabolic Trough]
        PTC --> SP{Splitter}
        SP -->|Branch 1| PHX(Process HX)
        SP -->|Branch 2| TES[(Packed Bed)]
        PHX --> MG{Merge}
        TES --> MG
        MG --> Pump
    end
    
    subgraph Process Loop
        PHX ===>|Heat| ZP[[Zinc Pool]]
    end
```

### 2.4 Series / Direct
The simplest architecture. A single loop where fluid flows from the PTC, to the process, directly through the bed, and back to the PTC.

```mermaid
graph LR
    subgraph Single Loop (NaK)
        Pump --> PTC[Parabolic Trough]
        PTC --> PHX(Process HX)
        PHX --> TES[(Packed Bed)]
        TES --> Pump
    end
    
    subgraph Process Loop
        PHX ===>|Heat| ZP[[Zinc Pool]]
    end
```

---

## 3. Operating Modes

The quasi-steady simulation utilizes six distinct operating modes depending on the current Solar Irradiance (DNI) and the TES State of Charge (SoC). The `system.py` module dynamically reconstructs the TESPy network to match the active mode.

### Mode 1: Pure Charging
- **Condition**: High solar irradiance, Process is OFF (or Process demand is fully met and excess is routed here).
- **Flow**: PTC → Splitter (Parallel) or direct (Series) → Charge TES → Pump.
- **Process HX**: Bypassed or zero duty.

### Mode 2: Direct Solar to Process (TES Standby)
- **Condition**: Solar irradiance exactly matches the process demand, or TES is fully charged and cannot accept more heat.
- **Flow**: PTC → Process HX → Pump.
- **TES**: Isolated (Standby). No charging or discharging.

### Mode 3: Solar + TES Co-Discharging
- **Condition**: Low solar irradiance (cloudy/late afternoon). The solar field provides some heat, but not enough for the process.
- **Flow**:
  - `Indirect`: PTC → Process HX (Preheat). Then, TES discharges via `Discharge_TES_HX` to provide the remaining heat to the process loop.
  - `Direct`: PTC → Process HX → Pump. TES fluid is routed directly to supplement the process.

### Mode 4: Pure Discharging
- **Condition**: No solar irradiance (night time). TES SoC > 5%.
- **Flow**: 
  - `Indirect`: TES secondary loop discharges through `Discharge_TES_HX` to the Process HX. The PTC is bypassed entirely.
  - `Direct`: Fluid flows backwards from the top of the TES → Process HX → Bottom of TES.

### Mode 5: Auxiliary Heater Only
- **Condition**: No solar irradiance AND TES is completely depleted (SoC < 5%).
- **Flow**: Solar and TES loops are bypassed/standby. The Auxiliary Heater (gas/electric) in the process loop provides 100% of the required heat to the Zinc Pool.

### Mode 6: Solar Charging + Process (Simultaneous)
- **Condition**: High solar irradiance (excess power available) and Process is ON.
- **Flow**: 
  - `Parallel`: Splitter divides the hot PTC fluid. A portion goes to the Process HX, and the remainder goes to the TES for charging.
  - `Series`: PTC fluid goes to the Process HX, drops in temperature, and the remaining sensible heat goes to the TES for charging.
