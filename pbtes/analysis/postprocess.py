"""
pbtes/analysis/postprocess.py

Post-processing utilities to calculate pressure drops and pump power
from simulation results, avoiding inline convergence issues in TESPy.
"""

import numpy as np
import pandas as pd
import CoolProp.CoolProp as cp
from typing import Dict, Any

from pbtes.config import SimulationConfig

def calculate_ergun_pressure_drop(mdot: float, T_fluid_C: float, tank_diameter: float, 
                                  tank_height: float, particle_diameter: float, void_fraction: float, 
                                  htf_fluid: str) -> float:
    """
    Calculates the pressure drop across the packed bed using the Ergun equation.
    
    Args:
        mdot: Mass flow rate [kg/s]. If 0 or NaN, returns 0.
        T_fluid_C: Average fluid temperature in the bed [°C].
        tank_diameter: Internal tank diameter [m].
        tank_height: Height of the packed bed [m].
        particle_diameter: Particle diameter (dp) [m].
        void_fraction: Porosity (eps) [-].
        htf_fluid: CoolProp fluid string (e.g., 'INCOMP::NaK').
        
    Returns:
        Pressure drop across the bed [Pa].
    """
    if pd.isna(mdot) or mdot <= 1e-6:
        return 0.0
        
    # Convert T to Kelvin and clamp to avoid CoolProp errors
    T_K = max(T_fluid_C + 273.15, 273.15 + 20)  # Min 20C safeguard
    P_Pa = 101325.0
    
    try:
        # Get fluid properties
        rho = cp.PropsSI('D', 'T', T_K, 'P', P_Pa, htf_fluid)  # Density [kg/m^3]
        mu = cp.PropsSI('V', 'T', T_K, 'P', P_Pa, htf_fluid)   # Dynamic viscosity [Pa*s]
    except Exception as e:
        # Fallback to rough Solar Salt properties if CoolProp fails
        rho = 1850.0  
        mu = 0.001
        
    # Cross-sectional area and superficial velocity
    A_cs = np.pi * (tank_diameter / 2.0)**2
    u = mdot / (rho * A_cs)  # [m/s]
    
    # Ergun Equation components
    term1 = 150.0 * ((1.0 - void_fraction)**2 / (void_fraction**3)) * (mu * u / (particle_diameter**2))
    term2 = 1.75 * ((1.0 - void_fraction) / (void_fraction**3)) * (rho * u**2 / particle_diameter)
    
    dp_bed_pa = (term1 + term2) * tank_height
    return dp_bed_pa

def calculate_system_pump_power(df: pd.DataFrame, meta: Dict[str, Any]) -> pd.DataFrame:
    """
    Appends pressure drop and pump power columns to the results DataFrame.
    Assumes standard pressure drops for non-TES components.
    
    Args:
        df: The simulation results DataFrame.
        meta: Metadata dictionary from the CSV header.
        
    Returns:
        Updated DataFrame with pump power metrics.
    """
    # Configuration and parameters
    cfg = SimulationConfig()
    
    # Dimensions from meta or fallback to baseline
    tank_diameter = meta.get('sim_args', {}).get('tank_diameter', cfg.tes.tank_diameter)
    tank_height = meta.get('sim_args', {}).get('tank_height', cfg.tes.tank_height)
    htf = meta.get('sim_args', {}).get('htf', cfg.htf.htf)
    tank_config = meta.get('tank_config', 'indirect')
    
    dp = cfg.tes.particle_diameter
    eps = cfg.tes.void_fraction
    eta_pump = cfg.process.pump_isentropic_efficiency
    
    # Fixed pressure drop assumptions (placeholders) [bar]
    DP_PTC_BAR = 2.0
    DP_HX_BAR = 0.5
    PIPING_MULTIPLIER = 1.2  # 20% overhead
    
    # Pre-allocate output arrays
    dp_tes_pa = np.zeros(len(df))
    W_pump_kw = np.zeros(len(df))
    
    # Iterate through each row to calculate timestep-specific values
    for idx, row in df.iterrows():
        mode = str(row.get('TESmode', '4'))
        
        # Determine average TES fluid temperature
        T_top = row.get('T_tes_top', 450.0)
        T_bot = row.get('T_tes_bottom', 400.0)
        T_avg = (T_top + T_bot) / 2.0
        if pd.isna(T_avg):
            T_avg = 450.0
            
        # Get mass flows
        m_ptc = row.get('mdot_ptc_kg_s', 0.0)
        m_tes_chg = row.get('mdot_tes_charge_kg_s', 0.0)
        m_tes_dch = row.get('mdot_tes_discharge_kg_s', 0.0)
        m_proc = row.get('mdot_process_kg_s', 0.0)
        
        # Handle missing mass flows gracefully
        m_ptc = 0.0 if pd.isna(m_ptc) else m_ptc
        m_tes_chg = 0.0 if pd.isna(m_tes_chg) else m_tes_chg
        m_tes_dch = 0.0 if pd.isna(m_tes_dch) else m_tes_dch
        m_proc = 0.0 if pd.isna(m_proc) else m_proc
        
        m_tes_total = m_tes_chg + m_tes_dch
        
        # 1. PBTES Pressure Drop (Ergun)
        dp_bed = calculate_ergun_pressure_drop(
            m_tes_total, T_avg, tank_diameter, tank_height, dp, eps, htf
        )
        dp_tes_pa[idx] = dp_bed
        
        # Determine fluid density for pump power (W = mdot * dP / (rho * eta))
        T_K_pump = max(T_avg + 273.15, 273.15 + 20)
        try:
            rho = cp.PropsSI('D', 'T', T_K_pump, 'P', 101325.0, htf)
        except Exception:
            rho = 1850.0
            
        # 2. Total Pressure Drop & Power depending on layout
        power_W = 0.0
        
        if tank_config == 'indirect':
            # Primary loop (PTC -> CHX or PROC_HX)
            if m_ptc > 0:
                dp_primary_bar = DP_PTC_BAR
                # Add HX pressure drops depending on routing
                if mode in ['1']:
                    dp_primary_bar += DP_HX_BAR # Charge HX
                elif mode in ['2', '3', '4', '5']:
                    dp_primary_bar += DP_HX_BAR # Process HX
                elif mode in ['6']:
                    dp_primary_bar += DP_HX_BAR * 2 # Split to both
                    
                dp_primary_pa = dp_primary_bar * 1e5 * PIPING_MULTIPLIER
                power_W += (m_ptc * dp_primary_pa) / (rho * eta_pump)
                
            # Secondary loop (TES -> CHX or DHX)
            if m_tes_total > 0:
                dp_secondary_pa = (dp_bed + DP_HX_BAR * 1e5) * PIPING_MULTIPLIER
                power_W += (m_tes_total * dp_secondary_pa) / (rho * eta_pump)
                
            # Process loop
            if m_proc > 0:
                # Flowing through process heat exchanger and process load
                dp_proc_pa = (DP_HX_BAR * 2 * 1e5) * PIPING_MULTIPLIER
                power_W += (m_proc * dp_proc_pa) / (rho * eta_pump)
                
        else: # direct configuration
            # In direct, it's one large loop with splits
            # We take the maximum mass flow and sum the pressure drops along the longest path
            m_max = max(m_ptc, m_proc, m_tes_total)
            if m_max > 0:
                dp_total_bar = 0.0
                if m_ptc > 0:
                    dp_total_bar += DP_PTC_BAR
                if m_tes_total > 0:
                    dp_total_bar += (dp_bed / 1e5) # convert bed Pa to bar
                if m_proc > 0:
                    dp_total_bar += DP_HX_BAR # process HX
                    
                dp_total_pa = dp_total_bar * 1e5 * PIPING_MULTIPLIER
                power_W += (m_max * dp_total_pa) / (rho * eta_pump)
                
        W_pump_kw[idx] = power_W / 1000.0

    # Append to DataFrame
    df['dP_tes_bar'] = dp_tes_pa / 1e5
    df['W_pump_kW'] = W_pump_kw
    
    return df
