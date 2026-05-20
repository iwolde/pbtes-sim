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

The quasi-steady simulation utilizes six distinct operating modes depending on the current Solar Irradiance (DNI) and the TES State of Charge (SoC).

| Mode | Name | Solar | TES | Aux | Active Components |
|------|------|-------|-----|-----|-------------------|
| **1** | Solar charges TES | ✔️ | Charge | - | PTC, Charge TES HX |
| **2** | Solar to process + TES standby | ✔️ | Standby | - | PTC, Process HX |
| **3** | Solar + TES Co-Discharging | ✔️ | Discharge | - | PTC, Discharge TES HX, Process HX |
| **4** | TES discharge to process | - | Discharge | - | Discharge TES HX, Process HX |
| **5** | Auxiliary heater only | - | Standby | ✔️ | **Auxiliary Heater (Preheater)**, Process HX |
| **6** | Solar charges TES + process | ✔️ | Charge | - | PTC, Charge TES HX, Process HX |

*Note: In Mode 5, the high-temperature Auxiliary Heater (labeled `Preheater_HX` in the TESPy code) fires to guarantee the process heat demand is met when solar is unavailable and the TES is fully depleted.*
