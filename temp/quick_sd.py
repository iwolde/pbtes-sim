import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tp, cp, cn = baseline_config()
tp['Initial temperature'] = 450
cp['ptc_A'] = 1000.0

cache = '.tespy_cache'
for i in range(1, 7):
    p = os.path.join(cache, f'base_design_{i}')
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)

# Design
s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                        HTF='INCOMP::NaK', topology='Series', tank_config='direct')
s.hot_tes.profile = np.ones(20) * 520.0
s.cold_tes.profile = np.ones(20) * 440.0
s.set_operation_mode(TESmode='1', current_irr=1000, profile=s.hot_tes.profile,
                      prev_TES_lay='Charge', mode='design')
s.solve_network(mode='design', TESmode='1')
designed_A = s.ptc_field_A_designed
print(f'Design: A={s.ptc_field.A.val:.0f}, designed_A={designed_A}, Q={s.ptc_field.Q.val/1e6:.3f}MW')
print(f'  T02={s.conn_02.T.val:.0f}C, T05={s.conn_05.T.val:.0f}C, T06={s.conn_06.T.val:.0f}C')
print()

# Offdesign with propagated designed_A
E_vals = [1000, 900, 800]
T_vals = [440, 470, 490]
print('SD Mode 1 Offdesign (with ptc_field_A_designed):')
for E in E_vals:
    for T in T_vals:
        so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                                 HTF='INCOMP::NaK', topology='Series', tank_config='direct')
        so.hot_tes.profile = np.ones(20) * float(T)
        so.cold_tes.profile = np.ones(20) * float(T)
        so.ptc_field_A_designed = designed_A  # Simulate solver propagation
        so.set_operation_mode(TESmode='1', current_irr=float(E),
                               profile=so.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')
        try:
            so.solve_network(mode='offdesign', TESmode='1', use_init_path=True)
            T2 = so.conn_02.T.val
            Q = so.ptc_field.Q.val / 1e6
            print(f'E={E:4d} T={T:3d}: T02={T2:.0f}C Q={Q:.3f}MW')
        except Exception as e:
            print(f'E={E:4d} T={T:3d}: FAIL ({type(e).__name__})')
