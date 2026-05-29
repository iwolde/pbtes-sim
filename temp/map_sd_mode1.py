"""
Map SD Mode 1 offdesign convergence across:
  - Hot tank bottom temp (conn_ht_ph.T)
  - Cold tank bottom temp (conn_10.T) 
  - Irradiance (E)
"""
import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tp, cp, cn = baseline_config()
tp['Initial temperature'] = 450

def clear_cache():
    cache = '.tespy_cache'
    for i in range(1, 7):
        p = os.path.join(cache, f'base_design_{i}')
        if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)

def make_design(des_E=1000, hot_bot_des=520, cold_bot_des=440, proc_ret=480):
    clear_cache()
    s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                            HTF='INCOMP::NaK', topology='Series', tank_config='direct')
    s.hot_tes.profile = np.ones(20) * float(hot_bot_des)
    s.cold_tes.profile = np.ones(20) * float(cold_bot_des)
    s.set_operation_mode(TESmode='1', current_irr=float(des_E),
                          profile=s.hot_tes.profile, prev_TES_lay='Charge', mode='design')
    s.solve_network(mode='design', TESmode='1')
    return s

def test_offdesign(designed_A, hot_bot_od, cold_bot_od, E_od):
    so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                             HTF='INCOMP::NaK', topology='Series', tank_config='direct')
    so.hot_tes.profile = np.ones(20) * float(hot_bot_od)
    so.cold_tes.profile = np.ones(20) * float(cold_bot_od)
    so.ptc_field_A_designed = designed_A
    so.set_operation_mode(TESmode='1', current_irr=float(E_od),
                           profile=so.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')
    try:
        so.solve_network(mode='offdesign', TESmode='1', use_init_path=True)
        if not so.network.converged:
            return 'NOCONV', None
        T2 = so.conn_02.T.val
        Q = so.ptc_field.Q.val / 1e6
        T5 = so.conn_05.T.val
        T6 = so.conn_06.T.val
        return 'OK', (T2, Q, T5, T6)
    except Exception as e:
        return 'FAIL', str(e)[:60]

# ---- Build design ----
print('=== SD Mode 1 Design ===')
s_d = make_design()
A_des = s_d.ptc_field_A_designed
print(f'  PTC A={A_des:.0f} m2, Q={s_d.ptc_field.Q.val/1e6:.3f} MW')
print(f'  T02(PTC_out)={s_d.conn_02.T.val:.0f}C')
print(f'  T05(proc_in)={s_d.conn_05.T.val:.0f}C, T06(proc_out)={s_d.conn_06.T.val:.0f}C')
print(f'  T_HTPX_out={s_d.conn_ht_ph.T.val:.0f}C, T_CTPX_out={s_d.conn_10.T.val:.0f}C')
print()

print('=== SD Mode 1 Offdesign Map (E=1000) ===')
hot_vals = [520, 510, 500, 490, 480, 470, 460, 450, 440]
cold_vals = [440, 450, 460, 470, 480]

header = 'H_bot\\C_bot'
for c in cold_vals: header += f'  C={c:3d}'
print(header)
print('=' * (10 + 9 * len(cold_vals)))

for h in hot_vals:
    row = f'H={h:3d}   '
    for c in cold_vals:
        if h <= c:
            row += '  skip_hle   '
            continue
        status, info = test_offdesign(A_des, h, c, 1000)
        if status == 'OK':
            row += f'  T2={info[0]:.0f}    '
        elif status == 'FAIL':
            row += '  FAIL     '
        else:
            row += '  NOCONV   '
    print(row)

print()
print('=== Varying E, fixed T (H=500, C=460) ===')
for E in [1000, 900, 800, 700]:
    status, info = test_offdesign(A_des, 500, 460, E)
    if status == 'OK':
        print(f'E={E:4d}: T2={info[0]:.0f}C, Q={info[1]:.3f}MW, T5={info[2]:.0f}C, T6={info[3]:.0f}C')
    else:
        print(f'E={E:4d}: {status} ({info})')
