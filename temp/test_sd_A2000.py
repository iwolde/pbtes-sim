import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tp, cp, cn = baseline_config()
tp['Initial temperature'] = 450
cp['ptc_A'] = 2000.0

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
A_des = s.ptc_field_A_designed
print(f'Design: A={A_des:.0f} (nominal={cp["ptc_A"]}), Q={s.ptc_field.Q.val/1e6:.3f}MW')
print(f'  T02={s.conn_02.T.val:.0f}C, T05={s.conn_05.T.val:.0f}C, T06={s.conn_06.T.val:.0f}C')
print(f'  T_HTPX_out={s.conn_ht_ph.T.val:.0f}C, T_CTPX_out={s.conn_10.T.val:.0f}C')
print()

# Offdesign at design point
print('=== Offdesign at design conditions ===')
for E in [1000, 900, 800, 700]:
    for warm in [True, False]:
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
            print(f'  E={E:4d} warm={warm}: conv={conv}, T02={T2}')
        except Exception as e:
            print(f'  E={E:4d} warm={warm}: EXCEPTION {type(e).__name__}')
