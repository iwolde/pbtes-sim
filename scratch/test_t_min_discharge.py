import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pbtes.simulation.solver import Solver
from run_simulation import run_single_simulation

# Original get_mode function
original_get_mode = Solver.get_mode

def run_with_offset(offset):
    print(f"\n==================================================")
    print(f" TESTING WITH OFFSET = {offset} K (T_min_discharge = {480 + offset} C)")
    print(f"==================================================")
    
    # Monkeypatch Solver.get_mode
    def custom_get_mode(self, irr, TES_profile, prev_TES_lay):
        # We can call the original but override the T_min_discharge local variable.
        # Since T_min_discharge is a local variable, we have to rewrite the relevant part of get_mode.
        # Or we can just let it call original and post-process, but wait: the original get_mode
        # returns the mode string. If it returns '4' because TES_top was below 500, we want it to return '3'.
        # Let's inspect get_mode logic:
        #
        # t_proc_set = 480.0, t_ph_out = 520.0
        # T_min_discharge = t_proc_set + 20 = 500 C
        #
        # If TES_top > T_min_discharge and TES_top <= T_max_discharge and soc_norm > 0.02:
        #     return '3'
        #
        # So we can just rewrite get_mode completely for our test, or we can use a wrapper that changes
        # the thresholds. Let's write a clean custom_get_mode:
        
        lay = prev_TES_lay or getattr(self, 'TES_lay', 'Charge')
        is_series_direct = (self.tank_config == 'direct' and self.topology == 'Series'
                            and hasattr(self.solar_system, 'cold_tes'))
        if is_series_direct:
            if lay == 'Charge':
                TES_top = self.solar_system.hot_tes.profile[0]
                TES_bot = self.solar_system.cold_tes.profile[-1]
            else:
                TES_top = self.solar_system.hot_tes.profile[-1]
                TES_bot = self.solar_system.cold_tes.profile[0]
        else:
            if lay == 'Charge':
                TES_top = TES_profile[0];  TES_bot = TES_profile[-1]
            else:  # 'Discharge'
                TES_top = TES_profile[-1]; TES_bot = TES_profile[0]
            
        t_proc_set = self.solar_system.conexion_params['6_T']
        t_ph_out   = self.solar_system.conexion_params['5_T']
        
        if is_series_direct:
            T_min_discharge = t_proc_set
        else:
            T_min_discharge = t_proc_set + offset
            
        T_max_discharge = 580.0
        
        if is_series_direct:
            hot_soc = self.solar_system.hot_tes.calculate_SoC(self.solar_system.hot_tes.profile)
            cold_soc = self.solar_system.cold_tes.calculate_SoC(self.solar_system.cold_tes.profile)
            current_soc = hot_soc + cold_soc
            soc_empty_h = self.solar_system.hot_tes.calculate_SoC(np.ones_like(self.solar_system.hot_tes.profile) * 400.0)
            soc_full_h = self.solar_system.hot_tes.calculate_SoC(np.ones_like(self.solar_system.hot_tes.profile) * 560.0)
            soc_empty_c = self.solar_system.cold_tes.calculate_SoC(np.ones_like(self.solar_system.cold_tes.profile) * 400.0)
            soc_full_c = self.solar_system.cold_tes.calculate_SoC(np.ones_like(self.solar_system.cold_tes.profile) * 560.0)
            soc_norm = ((current_soc - soc_empty_h - soc_empty_c)
                        / max(soc_full_h + soc_full_c - soc_empty_h - soc_empty_c, 1e-3))
        else:
            current_soc = self.solar_system.tes.calculate_SoC(TES_profile)
            soc_empty = self.solar_system.tes.calculate_SoC(np.ones_like(TES_profile) * 400.0)
            soc_full = self.solar_system.tes.calculate_SoC(np.ones_like(TES_profile) * 560.0)
            soc_norm = (current_soc - soc_empty) / max(soc_full - soc_empty, 1e-3)
            
        # Dwell:
        prev_is_solar = self.prev_TESmode in ('1', '2', '5', '6')
        curr_has_solar = irr > self.E_min_process
        if hasattr(self, '_mode_dwell') and self._mode_dwell < 2:
            if prev_is_solar or not curr_has_solar:
                self._mode_dwell += 1
                return self.prev_TESmode

        # Pegajosidad:
        if (self.prev_TESmode == '6' and soc_norm < 0.8
                and irr > self.E_min_process and self.topology == 'Parallel'):
            return '6'
            
        if soc_norm < 0.05 and irr < self.E_min_process:
            return '4'
            
        if soc_norm < 0.4 and TES_top < 470 and self.topology == 'Parallel':
            return '6' if irr > self.E_min_charge else '4'
            
        if irr > self.E_min_charge:
            if TES_top > t_ph_out and soc_norm < 0.90 and self.topology == 'Parallel':
                return '5'
            T_in_nom = self.solar_system.conexion_params.get('6_T', 480.0)
            T_out_design = 560.0
            E_design = self.component_params.get('ptc_E', 900.0)
            irr_frac = min(irr / E_design, 1.2)
            T_ptc_est = T_in_nom + irr_frac * (T_out_design - T_in_nom)
            min_dt_mode1 = 65.0 if self.topology == 'Parallel' else 30.0
            charge_viable = (T_ptc_est > TES_top + min_dt_mode1)
            if self.tank_config == 'indirect':
                T_charge_in = T_ptc_est if self.topology == 'Parallel' else t_proc_set
                tes_cold_side = TES_profile[-1] if prev_TES_lay == 'Charge' else TES_profile[0]
                if T_charge_in - tes_cold_side < min_dt_mode1:
                    charge_viable = False
            if irr >= self.E_min_mode1 and charge_viable and soc_norm < 0.99:
                return '1'
            else:
                return '2'
                
        if irr > self.E_min_process:
            if TES_top > T_min_discharge and TES_top <= T_max_discharge and soc_norm > 0.02:
                return '3'
            return '2'
            
        if TES_top > T_min_discharge and TES_top <= T_max_discharge and soc_norm > 0.02:
            return '3'
        return '4'

    Solver.get_mode = custom_get_mode
    
    # Run the simulation
    df, filename, meta = run_single_simulation(
        days=7,
        topology='Parallel',
        tank_config='indirect',
        tag=f"test_offset_{offset}",
        aperture=1000.0
    )
    
    # Calculate stats
    mode_counts = df['TESmode'].astype(str).value_counts()
    q_ch = df['to_tes_kJ'].sum() / 1e6
    q_dis = df['tes_to_proc_kJ'].sum() / 1e6
    q_aux = df['aux_to_proc_kJ'].sum() / 1e6
    
    sol_useful = df['solar_to_proc_kJ'].sum() + df['tes_to_proc_kJ'].sum()
    total_demand = sol_useful + df['aux_to_proc_kJ'].sum()
    sf = (sol_useful / total_demand * 100) if total_demand > 0 else 0.0
    
    print(f"\n--- RESULTS FOR OFFSET = {offset} K ---")
    print(f"Solar Fraction: {sf:.2f}%")
    print(f"Energy Charged: {q_ch:.2f} GJ")
    print(f"Energy Discharged: {q_dis:.2f} GJ")
    print(f"Energy Auxiliary: {q_aux:.2f} GJ")
    print(f"Mode distribution:")
    for mode, count in mode_counts.items():
        print(f"  Mode {mode}: {count} hours ({count/len(df)*100:.1f}%)")
        
    # Check convergence status
    iter_counts = df['iter_status'].astype(str).value_counts()
    print("Iteration Status:")
    for status, count in iter_counts.items():
        print(f"  Status {status}: {count} steps ({count/len(df)*100:.1f}%)")
        
    return {
        'offset': offset,
        'sf': sf,
        'q_ch': q_ch,
        'q_dis': q_dis,
        'q_aux': q_aux,
        'mode_counts': mode_counts.to_dict(),
        'convergence': iter_counts.to_dict()
    }

if __name__ == '__main__':
    offsets = [20, 15, 10, 5, 2]
    results = []
    for off in offsets:
        try:
            res = run_with_offset(off)
            results.append(res)
        except Exception as e:
            print(f"Failed for offset = {off}: {e}")
            
    print("\n\n" + "="*50)
    print(" COMPARISON SUMMARY")
    print("="*50)
    print(f"{'Offset (K)':<10} | {'SF%':<6} | {'Q_ch (GJ)':<10} | {'Q_dis (GJ)':<10} | {'M3 Hours':<8}")
    print("-"*50)
    for r in results:
        m3_hours = r['mode_counts'].get('3', 0)
        print(f"{r['offset']:<10} | {r['sf']:<6.2f} | {r['q_ch']:<10.2f} | {r['q_dis']:<10.2f} | {m3_hours:<8}")
    print("="*50)
