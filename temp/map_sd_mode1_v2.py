import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tp, cp, cn = baseline_config()
tp['Initial temperature'] = 450

cache = '.tespy_cache'
for i in range(1, 7):
    p = os.path.join(cache, f'base_design_{i}')
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)

# Design
s_d = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                          HTF='INCOMP::NaK', topology='Series', tank_config='direct')
s_d.hot_tes.profile = np.ones(20) * 520.0
s_d.cold_tes.profile = np.ones(20) * 440.0
s_d.set_operation_mode(TESmode='1', current_irr=1000, profile=s_d.hot_tes.profile,
                        prev_TES_lay='Charge', mode='design')
s_d.solve_network(mode='design', TESmode='1')
A_des = s_d.ptc_field_A_designed
print(f'Design: A={A_des:.0f}, Q={s_d.ptc_field.Q.val/1e6:.3f}MW, T02={s_d.conn_02.T.val:.0f}C')
print()

# Test offdesign at design conditions but WITHOUT use_init_path
print('=== At design point (H=520, C=440) with/without warm-start ===')
for warm in [True, False]:
    for E in [1000, 900]:
        so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                                 HTF='INCOMP::NaK', topology='Series', tank_config='direct')
        so.hot_tes.profile = np.ones(20) * 520.0
        so.cold_tes.profile = np.ones(20) * 440.0
        so.ptc_field_A_designed = A_des
        so.set_operation_mode(TESmode='1', current_irr=float(E),
                               profile=so.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')
        try:
            so.solve_network(mode='offdesign', TESmode='1', use_init_path=warm)
            conv = so.network.converged
            T2 = so.conn_02.T.val if conv else 'nan'
            print(f'  warm_start={warm}, E={E:4d}: converged={conv}, T02={T2}')
        except Exception as e:
            print(f'  warm_start={warm}, E={E:4d}: EXCEPTION {type(e).__name__}: {str(e)[:80]}')

print()

# Test with different design (lower PTC temp, different T spread)
print('=== Alternative design: lower T_spread ===')
# Try design with lower deltas
for hot_bot_d in [490, 480, 470]:
    for cold_bot_d in [460, 450, 440]:
        if hot_bot_d <= cold_bot_d: continue
        clear_cache()
        try:
            s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                                    HTF='INCOMP::NaK', topology='Series', tank_config='direct')
            s.hot_tes.profile = np.ones(20) * float(hot_bot_d)
            s.cold_tes.profile = np.ones(20) * float(cold_bot_d)
            s.set_operation_mode(TESmode='1', current_irr=1000,
                                  profile=s.hot_tes.profile, prev_TES_lay='Charge', mode='design')
            s.solve_network(mode='design', TESmode='1')
            A = s.ptc_field_A_designed
            
            # Offdesign at same conditions
            so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                                     HTF='INCOMP::NaK', topology='Series', tank_config='direct')
            so.hot_tes.profile = np.ones(20) * float(hot_bot_d)
            so.cold_tes.profile = np.ones(20) * float(cold_bot_d)
            so.ptc_field_A_designed = A
            so.set_operation_mode(TESmode='1', current_irr=1000,
                                   profile=so.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')
            so.solve_network(mode='offdesign', TESmode='1', use_init_path=False)
            conv = so.network.converged
            print(f'  D(H={hot_bot_d},C={cold_bot_d}) A={A:.0f}: od_conv={conv}')
        except Exception as e:
            print(f'  D(H={hot_bot_d},C={cold_bot_d}): FAIL {type(e).__name__}')
