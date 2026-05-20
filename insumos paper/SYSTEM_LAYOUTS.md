# PBTES Solar Plant: Layouts, Modes, and Configurations

This document provides a comprehensive overview of the plant configurations, the distinction between different topologies, and how the operating modes dictate fluid routing.

---

## 1. Topologies & Tank Configurations

The project matrix explores four distinct architectural variants, formed by combining two routing **Topologies** (Parallel vs Series) and two **Tank Configurations** (Indirect vs Direct).

### 1.1 Parallel vs. Series (Topologies)
This defines how the Solar Field (PTC) interfaces with the Process Heat Exchanger and the Thermal Energy Storage.

- **Parallel Topology**: The hot fluid exiting the PTC encounters a splitter. The flow is divided into two parallel branches: one branch serves the process heat demand (passing through the Discharge HX and Aux Heater), and the other branch goes to charge the TES. The returns from both branches are merged before heading back to the PTC.
- **Series Topology**: The hot fluid from the PTC travels through the system in a single series loop. It passes through the Discharge HX, Aux Heater, and Process HX to satisfy the industrial demand, and the remaining sensible heat is then passed through the Charge HX to charge the TES, before returning to the PTC.

### 1.2 Indirect vs. Direct (Tank Configurations)
This defines whether the primary Heat Transfer Fluid (HTF) physically enters the packed bed.

- **Indirect Config**: The Primary Loop (PTC and Process) is completely isolated from the Secondary Loop (TES). They exchange heat via two dedicated heat exchangers: `Charge_TES_HX` and `Discharge_TES_HX`.
- **Direct Config**: There is only one fluid loop. The primary HTF flows directly through the void spaces of the packed bed. The heat exchangers are removed (represented as simple pipes in the model) to eliminate the temperature approach (TTD) penalty.

---

## 2. System Architecture Diagrams

Below are the complete drawings (PFDs) for the four possible plant dispositions. Note the inclusion of the **Discharge TES HX** and the **Auxiliary Heater (Preheater HX)** which provides high-temperature heat during Mode 5.

### 2.1 Parallel / Indirect (Baseline)
The solar loop splits to serve the process branch and an isolated TES charging branch. During discharge, the TES secondary loop transfers heat to the process branch via the Discharge HX.

```mermaid
graph LR
    subgraph Primary Loop (NaK)
        Pump --> PTC[Parabolic Trough]
        PTC --> SP{Splitter}
        
        %% Charging Branch
        SP -->|Branch 1| CHX(Charge TES HX)
        
        %% Process Branch
        SP -->|Branch 2| DHX(Discharge TES HX)
        DHX --> AUX(Auxiliary Heater / Preheater)
        AUX --> PHX(Process HX)
        
        PHX --> MG{Merge}
        CHX --> MG
        MG --> Pump
    end
    
    subgraph Secondary Loop (TES)
        CHX -.->|Charge| TES[(Packed Bed)]
        TES -.->|Discharge| DHX
        DHX -.->|Cold Return| TES
        TES -.->|Cold Return| CHX
    end
    
    subgraph Process Loop
        PHX ===>|Heat| ZP[[Zinc Pool]]
    end
```

### 2.2 Series / Indirect
A single primary path. Fluid serves the process branch (including Discharge HX and Aux Heater) first, then passes through the Charge HX to store remaining heat.

```mermaid
graph LR
    subgraph Primary Loop (NaK)
        Pump --> PTC[Parabolic Trough]
        PTC --> DHX(Discharge TES HX)
        DHX --> AUX(Auxiliary Heater / Preheater)
        AUX --> PHX(Process HX)
        PHX --> CHX(Charge TES HX)
        CHX --> Pump
    end
    
    subgraph Secondary Loop (TES)
        CHX -.->|Charge| TES[(Packed Bed)]
        TES -.->|Discharge| DHX
        DHX -.->|Cold Return| TES
        TES -.->|Cold Return| CHX
    end
    
    subgraph Process Loop
        PHX ===>|Heat| ZP[[Zinc Pool]]
    end
```

### 2.3 Parallel / Direct
A single fluid loop (NaK) that splits. One branch flows directly through the packed bed. The heat exchangers are replaced with virtual pipe connections for direct fluid routing.

```mermaid
graph LR
    subgraph Single Loop (NaK)
        Pump --> PTC[Parabolic Trough]
        PTC --> SP{Splitter}
        
        %% Charging Branch
        SP -->|Branch 1| CHX(Virtual Charge Pipe)
        
        %% Process Branch
        SP -->|Branch 2| DHX(Virtual Discharge Pipe)
        DHX --> AUX(Auxiliary Heater)
        AUX --> PHX(Process HX)
        
        PHX --> MG{Merge}
        CHX --> MG
        MG --> Pump
    end
    
    subgraph TES Storage
        CHX -.->|Flow In| TES[(Packed Bed)]
        TES -.->|Flow Out| DHX
    end
    
    subgraph Process Loop
        PHX ===>|Heat| ZP[[Zinc Pool]]
    end
```

### 2.4 Series / Direct
The simplest architecture. Fluid flows from the PTC, through the virtual discharge connection, the Aux Heater, the Process HX, and then directly through the packed bed.

```mermaid
graph LR
    subgraph Single Loop (NaK)
        Pump --> PTC[Parabolic Trough]
        PTC --> DHX(Virtual Discharge Pipe)
        DHX --> AUX(Auxiliary Heater)
        AUX --> PHX(Process HX)
        PHX --> CHX(Virtual Charge Pipe)
        CHX --> Pump
    end
    
    subgraph TES Storage
        CHX -.->|Flow In| TES[(Packed Bed)]
        TES -.->|Flow Out| DHX
    end
    
    subgraph Process Loop
        PHX ===>|Heat| ZP[[Zinc Pool]]
    end
```

---

## 3. Operating Modes

The quasi-steady simulation utilizes six distinct operating modes depending on the current Solar Irradiance (DNI) and the TES State of Charge (SoC). *Note: This corrects previous documentation that misaligned the mode numbers.*

| Mode | Name | Description |
|------|------|-------------|
| **1** | Pure Charging | **Solar charges TES.** Used when process demand is off or fully met, routing all solar heat to the TES. |
| **2** | Solar to Process (TES Standby) | **Solar serves process only.** Solar irradiance matches process demand; TES is inactive. |
| **3** | TES Discharge | **TES discharging.** Solar is insufficient/off. TES discharges heat to the process loop. |
| **4** | Auxiliary Heater Only | **Auxiliary firing.** Solar is off and TES is depleted. The Auxiliary Heater provides 100% of process heat. |
| **5** | High-Temperature Charging | **High-T Charging + Process.** A special series mode (even in Parallel plants). Fluid flows from PTC → Charge TES HX (highest temp) → Additional HX (Preheater/Aux) → Process HX. This charges the TES at a higher temperature than Mode 6. |
| **6** | Normal Charging + Process | **Simultaneous operation.** Solar field serves the process first (or in parallel), and the remaining heat/flow is used to charge the TES. |

### Note on Mode 5 vs Mode 6
- In **Mode 6 (Series)**, the flow is `PTC → Process HX → Charge TES HX`. The process gets the hottest fluid, and the TES charges with the cooler return fluid.
- In **Mode 5**, the flow is reversed: `PTC → Charge TES HX → Additional HX (Preheater) → Process HX`. The TES receives the hottest fluid directly from the PTC for high-temperature charging, and the process is served afterwards, utilizing the additional HX (Preheater) to top up the heat if necessary.
