"""
pbtes/analysis/exergoeconomics.py

Exergoeconomic assessment module for the PBTES solar thermal plant.
Calculates plant-level exergy efficiencies, exergy destruction, and specific
costs of exergy.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from pbtes.analysis.economics import EconomicAssessment

class ExergoeconomicAssessment(EconomicAssessment):
    """
    Evaluates the exergoeconomic performance of a PBTES plant design.
    Inherits from EconomicAssessment to access CAPEX and OPEX values.
    
    This implements a simplified plant-level assessment since detailed
    state points (h, s) for every connection are not stored by default.
    """
    
    # Sun temperature in Kelvin for Petela theorem
    T_SUN = 5770.0
    
    def run_exergoeconomic_assessment(self) -> Dict[str, float]:
        """
        Runs the exergoeconomic assessment at the plant level.
        
        Returns:
            Dictionary containing exergy and exergoeconomic metrics.
        """
        # First, run the standard economic assessment to get costs
        eco_results = self.run_assessment()
        
        # We need time series data to calculate exergy integrals
        df = self.df
        
        # Ensure we have the necessary columns, fill missing with 0
        E_dni = df['E'].fillna(0.0) if 'E' in df.columns else np.zeros(len(df))
        T_amb_C = df['Tamb'].fillna(20.0) if 'Tamb' in df.columns else np.full(len(df), 20.0)
        T_zinc_C = df['T_zinc'].fillna(450.0) if 'T_zinc' in df.columns else np.full(len(df), 450.0)
        
        Q_solar_to_proc = df['solar_to_proc_kJ'].fillna(0.0) if 'solar_to_proc_kJ' in df.columns else np.zeros(len(df))
        Q_tes_to_proc = df['tes_to_proc_kJ'].fillna(0.0) if 'tes_to_proc_kJ' in df.columns else np.zeros(len(df))
        Q_aux = df['aux_to_proc_kJ'].fillna(0.0) if 'aux_to_proc_kJ' in df.columns else np.zeros(len(df))
        
        # Temperatures in Kelvin
        T_0 = T_amb_C + 273.15
        T_zinc_K = T_zinc_C + 273.15
        
        # 1. Solar Exergy Input (Petela theorem)
        # Solar energy incident on the collector aperture
        area = self.ptc_area
        Q_sun_incident_W = E_dni * area
        Q_sun_incident_kJ = Q_sun_incident_W * self.cfg.solver.time_step / 1000.0
        
        petela_factor = 1.0 - (4.0/3.0)*(T_0 / self.T_SUN) + (1.0/3.0)*(T_0 / self.T_SUN)**4
        Ex_solar_kJ = Q_sun_incident_kJ * petela_factor
        
        # 2. Auxiliary Exergy Input (assuming high quality, exergy approx equal to energy)
        Ex_aux_kJ = Q_aux * 1.0
        
        # 3. Product Exergy (Exergy delivered to the Zinc pool)
        # Carnot factor based on the sink temperature (zinc pool)
        carnot_factor = 1.0 - (T_0 / T_zinc_K)
        # Clamp carnot factor to 0 if Tamb >= Tzinc (unlikely, but safe)
        carnot_factor = np.maximum(carnot_factor, 0.0)
        
        Q_delivered_total_kJ = Q_solar_to_proc + Q_tes_to_proc + Q_aux
        Ex_product_kJ = Q_delivered_total_kJ * carnot_factor
        
        # Aggregate totals (in MWh)
        total_Ex_solar_MWh = Ex_solar_kJ.sum() / 3600000.0
        total_Ex_aux_MWh = Ex_aux_kJ.sum() / 3600000.0
        total_Ex_product_MWh = Ex_product_kJ.sum() / 3600000.0
        
        total_Ex_fuel_MWh = total_Ex_solar_MWh + total_Ex_aux_MWh
        
        # Plant Exergy Efficiency
        eta_exergy = (total_Ex_product_MWh / total_Ex_fuel_MWh) * 100.0 if total_Ex_fuel_MWh > 0 else 0.0
        
        # Total Exergy Destruction (and losses)
        Ex_destruction_MWh = total_Ex_fuel_MWh - total_Ex_product_MWh
        
        # 4. Exergoeconomic Costing
        # Z_tot: Annualized CAPEX + O&M
        annualized_Z = eco_results['annualized_capex'] + eco_results['cost_om']
        
        # Cost of fuel
        # Solar exergy is free (c_solar = 0)
        # Aux fuel has a cost
        cost_aux = eco_results['cost_aux_fuel'] + eco_results['cost_electricity']
        
        # Cost balance: C_P = C_F + Z
        # c_P * Ex_P = c_F * Ex_F + Z  ->  c_P = (cost_aux + Z) / Ex_P
        if total_Ex_product_MWh > 0:
            c_p_usd_per_MWh_ex = (cost_aux + annualized_Z) / total_Ex_product_MWh
        else:
            c_p_usd_per_MWh_ex = float('inf')
            
        # Cost of exergy destruction
        # C_D = c_P * Ex_D (assuming product cost rate applies to destruction in simplified model)
        # Or C_D = c_F * Ex_D. Since c_solar=0, we use average c_F or c_P. We'll use c_P for the plant level.
        cost_exergy_destruction = c_p_usd_per_MWh_ex * Ex_destruction_MWh if c_p_usd_per_MWh_ex != float('inf') else 0.0
        
        # Exergoeconomic factor f = Z / (Z + C_D)
        if (annualized_Z + cost_exergy_destruction) > 0:
            f_factor = annualized_Z / (annualized_Z + cost_exergy_destruction)
        else:
            f_factor = 0.0
            
        # Combine results
        exergo_results = {
            **eco_results,
            'total_Ex_solar_MWh': total_Ex_solar_MWh,
            'total_Ex_aux_MWh': total_Ex_aux_MWh,
            'total_Ex_product_MWh': total_Ex_product_MWh,
            'Ex_destruction_MWh': Ex_destruction_MWh,
            'eta_exergy': eta_exergy,
            'c_p_usd_per_MWh_ex': c_p_usd_per_MWh_ex,
            'cost_exergy_destruction_usd': cost_exergy_destruction,
            'exergoeconomic_f_factor': f_factor
        }
        
        return exergo_results
