"""
pbtes/analysis/economics.py

Economic and Exergoeconomic assessment module for the PBTES solar thermal plant.
Calculates Levelized Cost of Heat (LCOH) and breaks down equipment CAPEX & OPEX
based on simulation results.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from pbtes.config import SimulationConfig

class EconomicAssessment:
    """
    Evaluates the economic performance of a PBTES plant design given 
    its hourly simulation results.
    """
    
    def __init__(self, df: pd.DataFrame, meta: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None):
        """
        Args:
            df: Simulation results DataFrame.
            meta: Metadata dictionary from the CSV header.
            overrides: Optional dictionary to override default EconomicConfig values
                       (e.g., {'electricity_price_per_kwh': 0.12}).
        """
        self.df = df
        self.meta = meta
        self.cfg = SimulationConfig()
        
        # Apply overrides to economics configuration if provided
        if overrides:
            for k, v in overrides.items():
                if hasattr(self.cfg.economics, k):
                    setattr(self.cfg.economics, k, v)
                    
        # Extract sizing parameters from metadata
        self.ptc_area = self.meta.get('sim_args', {}).get('aperture_area', self.cfg.ptc.aperture_area)
        self.tank_diameter = self.meta.get('sim_args', {}).get('tank_diameter', self.cfg.tes.tank_diameter)
        self.tank_height = self.meta.get('sim_args', {}).get('tank_height', self.cfg.tes.tank_height)
        
    def estimate_hx_capex(self, name: str, UA_max: float, T_op: float) -> float:
        """
        Stub cost function for Heat Exchangers.
        TODO: Implement detailed cost correlation based on UA and operating T.
        
        Args:
            name: Identifier for the HX (e.g., 'charge_hx', 'process_hx').
            UA_max: Maximum required overall heat transfer coefficient * Area [W/K].
            T_op: Design operating temperature [°C].
            
        Returns:
            Estimated CAPEX in USD.
        """
        # Placeholder cost assumption:
        base_cost = 50000.0
        return base_cost

    def estimate_ptc_capex(self, area: float) -> float:
        """
        Cost function for Parabolic Trough Collector field.
        
        Args:
            area: Total aperture area [m²].
            
        Returns:
            Estimated CAPEX in USD.
        """
        # Placeholder: 200 USD/m2
        return area * 200.0

    def estimate_tes_capex(self, volume: float, htf_mass: float) -> float:
        """
        Cost function for Thermal Energy Storage (tank + material + HTF).
        
        Args:
            volume: Internal volume of the tank [m³].
            htf_mass: Mass of the HTF in the tank [kg].
            
        Returns:
            Estimated CAPEX in USD.
        """
        tank_cost = volume * self.cfg.economics.tank_cost_per_m3
        htf_cost = htf_mass * self.cfg.economics.htf_cost_per_kg
        # Add rock/ceramic fill cost here
        fill_cost = volume * (1 - self.cfg.tes.void_fraction) * self.cfg.tes.solid_density * 0.10 # $0.10/kg
        return tank_cost + htf_cost + fill_cost

    def estimate_pump_capex(self, W_pump_max_kW: float) -> float:
        """
        Stub cost function for Pumps.
        TODO: Implement detailed pump cost function.
        
        Args:
            W_pump_max_kW: Maximum pump power required [kW].
            
        Returns:
            Estimated CAPEX in USD.
        """
        # Placeholder cost assumption:
        base_cost = 20000.0 + (W_pump_max_kW * 500.0)
        return base_cost

    def calculate_annualized_capex(self, total_capex: float) -> float:
        """Calculates the annualized capital cost using the Capital Recovery Factor."""
        r = self.cfg.economics.discount_rate
        n = self.cfg.economics.lifetime
        crf = (r * (1 + r)**n) / (((1 + r)**n) - 1)
        return total_capex * crf

    def run_assessment(self) -> Dict[str, float]:
        """
        Runs the full economic assessment.
        
        Returns:
            A dictionary containing CAPEX, OPEX, LCOH, and other economic metrics.
        """
        # 1. Size Components and Calculate CAPEX
        tes_volume = np.pi * (self.tank_diameter / 2.0)**2 * self.tank_height
        htf_mass_tes = tes_volume * self.cfg.tes.void_fraction * self.cfg.economics.htf_density_for_mass
        
        capex_ptc = self.estimate_ptc_capex(self.ptc_area)
        capex_tes = self.estimate_tes_capex(tes_volume, htf_mass_tes)
        
        # Max pump power from results
        W_pump_max = self.df['W_pump_kW'].max() if 'W_pump_kW' in self.df.columns else 0.0
        capex_pumps = self.estimate_pump_capex(W_pump_max)
        
        # HX Stubs (using dummy UA values until we calculate them properly in simulation)
        capex_hx_charge = self.estimate_hx_capex('charge_hx', 10000.0, 500.0)
        capex_hx_discharge = self.estimate_hx_capex('discharge_hx', 10000.0, 500.0)
        capex_hx_process = self.estimate_hx_capex('process_hx', 20000.0, 480.0)
        
        capex_total = (capex_ptc + capex_tes + capex_pumps + 
                       capex_hx_charge + capex_hx_discharge + capex_hx_process + 
                       self.cfg.economics.base_capex)
                       
        annualized_capex = self.calculate_annualized_capex(capex_total)
        
        # 2. Calculate OPEX
        # Annual electricity cost
        total_pump_kWh = self.df['W_pump_kW'].sum() if 'W_pump_kW' in self.df.columns else 0.0
        cost_electricity = total_pump_kWh * self.cfg.economics.electricity_price_per_kwh
        
        # Annual auxiliary heater fuel cost
        # aux_to_proc_kJ is in kJ; convert to kWh
        total_aux_kWh = (self.df['aux_to_proc_kJ'].sum() / 3600.0) if 'aux_to_proc_kJ' in self.df.columns else 0.0
        cost_aux_fuel = total_aux_kWh * self.cfg.economics.aux_fuel_price_per_kwh
        
        # O&M
        cost_om = capex_total * self.cfg.economics.om_rate_fraction
        
        opex_total = cost_electricity + cost_aux_fuel + cost_om
        
        # 3. Calculate Energy Delivered
        # process energy is the sum of direct solar, tes discharge, and aux
        solar_kJ = self.df['solar_to_proc_kJ'].sum() if 'solar_to_proc_kJ' in self.df.columns else 0.0
        tes_kJ = self.df['tes_to_proc_kJ'].sum() if 'tes_to_proc_kJ' in self.df.columns else 0.0
        aux_kJ = self.df['aux_to_proc_kJ'].sum() if 'aux_to_proc_kJ' in self.df.columns else 0.0
        
        q_delivered_kWh = (solar_kJ + tes_kJ + aux_kJ) / 3600.0
        q_delivered_MWh = q_delivered_kWh / 1000.0
        
        # 4. LCOH [USD/MWh]
        if q_delivered_MWh > 0:
            lcoh = (annualized_capex + opex_total) / q_delivered_MWh
        else:
            lcoh = float('inf')
            
        results = {
            'capex_ptc': capex_ptc,
            'capex_tes': capex_tes,
            'capex_pumps': capex_pumps,
            'capex_hxs': capex_hx_charge + capex_hx_discharge + capex_hx_process,
            'capex_total': capex_total,
            'annualized_capex': annualized_capex,
            'cost_electricity': cost_electricity,
            'cost_aux_fuel': cost_aux_fuel,
            'cost_om': cost_om,
            'opex_total': opex_total,
            'q_delivered_MWh': q_delivered_MWh,
            'lcoh_usd_per_MWh': lcoh
        }
        
        return results


