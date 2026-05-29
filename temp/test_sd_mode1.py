import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tes_p, comp_p, conn_p = baseline_config()
tes_p['Initial temperature'] = 450

cache = '.tespy_cache'
for i in range(1,7):
    p = os.path.join(cache, f'base_design_{i}')
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)

# ---- SD Mode 1 Design ----
print('=== SD Mode 1 Design ===')
sys_d = SolarThermalSystem(rows=1, tes_params=tes_p, component_params=comp_p,
                            conexion_params=conn_p, HTF='INCOMP::NaK',
                            topology='Series', tank_config='direct')
sys_d.hot_tes.profile = np.ones(20) * 520.0
sys_d.cold_tes.profile = np.ones(20) * 440.0
sys_d.set_operation_mode(TESmode='1', current_irr=1000,
                          profile=sys_d.hot_tes.profile,
                          prev_TES_lay='Charge', mode='design')
sys_d.solve_network(mode='design', TESmode='1')
print(f'  Design converged: {sys_d.network.converged}')
print(f'  PTC outlet T={sys_d.conn_02.T.val:.0f}C')
print(f'  PTC Q={sys_d.ptc_field.Q.val/1e6:.3f} MW')
print(f'  PTC A={sys_d.ptc_field.A.val:.0f} m2')
print()

# ---- SD Mode 1 Offdesign grid ----
E_vals = [1000, 900, 800]
Tbot_vals = [450, 470, 480, 490]
print('SD Mode 1 Offdesign grid:')
header = '       '
for t in Tbot_vals: header += f'  T_bot={t}'
print(header)
for E in E_vals:
    row = f'E={E:4d}  '
    for Tbot in Tbot_vals:
        sys_o = SolarThermalSystem(rows=1, tes_params=tes_p, component_params=comp_p,
                                    conexion_params=conn_p, HTF='INCOMP::NaK',
                                    topology='Series', tank_config='direct')
        sys_o.hot_tes.profile = np.ones(20) * float(Tbot)
        sys_o.cold_tes.profile = np.ones(20) * float(Tbot)
        sys_o.set_operation_mode(TESmode='1', current_irr=float(E),
                                  profile=sys_o.hot_tes.profile,
                                  prev_TES_lay='Charge', mode='offdesign')
        try:
            sys_o.solve_network(mode='offdesign', TESmode='1', use_init_path=True)
            conv = sys_o.network.converged
            T_ptc_out = sys_o.conn_02.T.val
            row += f'  OK(T2={T_ptc_out:.0f})'
        except Exception as e:
            err = str(e)[:30]
            row += f'  FAIL    '
    print(row)
