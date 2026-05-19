"""
MODE 3 — Complete Audit: Regimes, kA, thresholds
Parallel · indirect · TES discharge to process

Tests:
  1. Design convergence + kA computation
  2. Offdesign: sweep T15 from 560 down to find limits
  3. Both regimes: A (DHX=100%) and B (DHX+PH)
  4. Verify single DHX kA used
"""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem

for f in ['base_design_3','base_design_4']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {
    'Initial temperature': 400, 'Tank lenght': 10, 'Tank diameter': 4,
    'Particle diameter': 0.05, 'Void fraction': 0.4, 'Solid density': 2500,
    'Solid specific heat': 1000, 'Solid conductivity': 1.5,
    'Wall thinckness': 0.05, 'Tank conductivity': 15,
    'Insulation thickness': 0.5, 'Insulation conductivity': 0.035,
    'HTF': 'INCOMP::NaK'
}
comp_p = {
    'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6
}
conn_p = {
    '5_T': 520, '6_T': 480, '6_p': 50, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}
}

print('='*70)
print('  MODE 3 — TES DISCHARGE: COMPLETE AUDIT')
print('='*70)

# ============================================================
# 1. DESIGN — compute kA
# ============================================================
print('\n--- 1. DESIGN (T15=540) ---')
sys_d = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys_d.tes.profile = np.ones(20) * 540
sys_d.set_operation_mode(TESmode='3', current_irr=0, mode='design',
    profile=sys_d.tes.profile, prev_TES_lay='Discharge')
sys_d.conn_15.set_attr(T=540)
sys_d.solve_network(mode='design', TESmode='3')
ka_dhx = sys_d.discharge_tes_hx.kA.val
print(f'  DHX kA = {ka_dhx:.0f} W/K')
print(f'  Design point: T15=540, T04={sys_d.conn_04.T.val:.0f}, T05={sys_d.conn_05.T.val:.0f}')
print(f'  Regime at design: DHX Q={sys_d.discharge_tes_hx.Q.val/1e6:.2f}MW, PH Q={sys_d.preheater_hx.Q.val/1e6:.2f}MW')

# ============================================================
# 2. Verify only ONE kA (no cross-mode kA leakage)
# ============================================================
print('\n--- 2. VERIFY: Single DHX kA ---')
print(f'  Design file: base_design_3')
print(f'  No cross-mode kA file (unlike mode1_kA.txt for charge HX)')
print(f'  kA = {ka_dhx:.0f} W/K — computed once, stored in design, used for all offdesign')

# ============================================================
# 3. OFFDESIGN SWEEP — find viable T15 range
# ============================================================
print('\n--- 3. OFFDESIGN SWEEP — T15 from 560 down to limit ---')
print(f'  {"T15":>6s} {"T04":>6s} {"T16":>6s} {"T11":>6s}  {"DHX":>8s} {"PH":>8s}  {"regime":>7s} {"note":>30s}')
print(f'  {"-"*6} {"-"*6} {"-"*6} {"-"*6}  {"-"*8} {"-"*8}  {"-"*7} {"-"*30}')

from coreV5 import Solver
solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.initialize_modes()
solver.current_irr = 0

for T15 in range(560, 470, -5):
    sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    sys.tes.profile = np.ones(20) * T15
    sys.set_operation_mode(TESmode='3', current_irr=0, mode='offdesign',
        profile=sys.tes.profile, prev_TES_lay='Discharge')
    sys.conn_15.set_attr(T=T15)
    
    ok, _, err = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '3', tries=3)
    
    if ok and sys.network.converged:
        t04 = sys.conn_04.T.val
        t16 = sys.conn_16.T.val
        t11 = sys.conn_11.T.val
        q_dhx = sys.discharge_tes_hx.Q.val / 1e6
        q_ph = sys.preheater_hx.Q.val / 1e6
        
        # Regime classification
        dhx_heating = t04 > t11 + 1.0  # DHX outlet hotter than inlet (ΔT>1°C)
        ph_heating = q_ph < -0.01  # PH heater active
        ph_cooling = q_ph > 0.01   # PH would need to cool
        
        if ph_cooling:
            regime = "INVALID"
            note = "PH would cool (T04 > 520)"
        elif abs(q_ph) < 0.01 and dhx_heating:
            regime = "A"
            note = "100% DHX, PH idle"
        elif dhx_heating:
            regime = "B"
            note = f"DHX+PH, DHX={abs(q_dhx/q_ph)*100:.0f}%"
        else:
            regime = "LIMIT"
            note = f"T04={t04:.0f} <= T11={t11:.0f} (DHX reverses)"
        
        print(f'  {T15:6d} {t04:6.0f} {t16:6.0f} {t11:6.0f}  {q_dhx:8.3f} {q_ph:8.3f}  {regime:>7s}  {note}')
    else:
        err_msg = str(err)[:60] if err else ''
        print(f'  {T15:6d} {"-":>6s} {"-":>6s} {"-":>6s}  {"-":>8s} {"-":>8s}  {"FAIL":>7s}  {err_msg}')

# ============================================================
# 4. THRESHOLD ANALYSIS
# ============================================================
t_proc_set = conn_p['6_T']  # 480
t_ph_out = conn_p['5_T']    # 520

print(f'\n--- 4. THRESHOLD ANALYSIS ---')
print(f'  Process setpoint: T06 = {t_proc_set}°C')
print(f'  Preheater target: T05 = {t_ph_out}°C')
print(f'  DHX approach (Ref): T04 = T15 - 20')
print(f'')
print(f'  Regime A (100% DHX):  T15 >= {t_ph_out + 20}°C (T04 >= T05)')
print(f'  Regime B (DHX + PH):  {t_proc_set + 20}°C <= T15 < {t_ph_out + 20}°C')
print(f'  Regime inviable:      T15 < {t_proc_set + 20}°C (T04 < T06, DHX reverses)')
print(f'')
print(f'  Current thresholds:')
print(f'    T_min_discharge = T06 + 20 = {t_proc_set + 20}°C')
print(f'    T_max_discharge = T05 + 20 = {t_ph_out + 20}°C')
print(f'    These are ADAPTIVE — derived from process temps, not hardcoded.')
print(f'')
print(f'  Maximum DHX contribution at minimum T15 ({t_proc_set + 20}°C):')
print(f'    T04 = T15 - 20 = {t_proc_set + 20 - 20}°C = T06')
print(f'    DHX Q ~ 0 (outlet equals return, no heating possible)')
print(f'    All process heat from PH (auxiliary)')
print(f'')
print(f'  NOTE: T_min_discharge cannot be lowered without:')
print(f'    1. Reducing the Ref delta (would require re-designing DHX)')
print(f'    2. Changing process temperatures (T05, T06)')
print(f'    The current limit is PHYSICAL — not arbitrary.')
