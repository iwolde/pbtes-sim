"""
Map SD Mode 1 offdesign:
- Design uses PTC A='var', conn_02.T=560 (matching actual simulation)
- Offdesign clears tank Q, uses ptc_field_A_designed
- Tests with zinc pool conn_06.T constraint
"""
import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tp, cp, cn = baseline_config()
tp['Initial temperature'] = 450
cp['ptc_A'] = 1000.0  # simulation override

cache = '.tespy_cache'
for i in range(1, 7):
    p = os.path.join(cache, f'base_design_{i}')
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)

# ---- Design (same as solver's initialize_modes) ----
s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                        HTF='INCOMP::NaK', topology='Series', tank_config='direct')
s.hot_tes.profile = np.ones(20) * 520.0
s.cold_tes.profile = np.ones(20) * 440.0
s.set_operation_mode(TESmode='1', current_irr=1000, profile=s.hot_tes.profile,
                      prev_TES_lay='Charge', mode='design')
s.solve_network(mode='design', TESmode='1')
A_des = s.ptc_field_A_designed
print(f'Design: A={A_des:.0f} m2, Q={s.ptc_field.Q.val/1e6:.3f}MW, T02={s.conn_02.T.val:.0f}C')
print(f'  T05(proc_in)={s.conn_05.T.val:.0f}C T06(proc_out)={s.conn_06.T.val:.0f}C')
print(f'  H_bot={s.conn_ht_ph.T.val:.0f}C C_bot={s.conn_10.T.val:.0f}C')
print()

# ---- Zinc pool effect: conn_06.T is set to process return temp ----
# For SD Mode 1 design, T06=480C; zinc pool would set ~480-490C
# Test: does offdesign converge when conn_06.T is constrained?

def test_od(hot_bot_od, cold_bot_od, E_od, T06_od=None):
    """Return (status, T02 or None)"""
    so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                             HTF='INCOMP::NaK', topology='Series', tank_config='direct')
    so.hot_tes.profile = np.ones(20) * float(hot_bot_od)
    so.cold_tes.profile = np.ones(20) * float(cold_bot_od)
    so.ptc_field_A_designed = A_des
    so.set_operation_mode(TESmode='1', current_irr=float(E_od),
                           profile=so.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')
    if T06_od is not None:
        so.conn_06.set_attr(T=float(T06_od))
    try:
        so.solve_network(mode='offdesign', TESmode='1', use_init_path=True)
        if so.network.converged:
            return 'OK', so.conn_02.T.val
        return 'NOCONV', None
    except Exception as e:
        msg = str(e)[:60]
        if 'Singularity' in msg:
            return 'SING', None
        if 'too many' in msg.lower():
            return 'OVER', None
        if 'not enough' in msg.lower():
            return 'UNDER', None
        return 'FAIL', None

# ---- Grid: H_bot, C_bot, E, with and without conn_06.T ----
hot_vals = [520, 510, 500, 490, 480, 470]
cold_vals = [440, 450, 460, 470, 480, 490]
E_vals = [1000, 900, 800, 700]

print('=== Without zinc pool (conn_06.T NOT constrained) ===')
print(f'Design point: H=520, C=440, E=1000')
for E in E_vals:
    row = f'E={E:4d}: '
    for H in [520, 500, 480]:
        C = H - 40  # 40C spread
        if C < 440: continue
        st, T2 = test_od(H, C, E, None)
        if st == 'OK':
            row += f'(H={H},C={C}):T2={T2:.0f} '
        else:
            row += f'(H={H},C={C}):{st} '
    print(row)

print()
print('=== With zinc pool (conn_06.T=480) ===')
for E in E_vals:
    row = f'E={E:4d}: '
    for H in [520, 500, 480]:
        C = H - 40
        if C < 440: continue
        st, T2 = test_od(H, C, E, 480)
        if st == 'OK':
            row += f'(H={H},C={C}):T2={T2:.0f} '
        else:
            row += f'(H={H},C={C}):{st} '
    print(row)
