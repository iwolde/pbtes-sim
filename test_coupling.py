from coreV5 import SolarThermalSystem; import numpy as np, os, shutil

for f in ['base_design_1', 'base_design_5']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {'Initial temperature': 400, 'Tank lenght': 10, 'Tank diameter': 3,
    'Particle diameter': 0.05, 'Void fraction': 0.4, 'Solid density': 2500,
    'Solid specific heat': 1000, 'Solid conductivity': 1.5, 'Wall thinckness': 0.05,
    'Tank conductivity': 15, 'Insulation thickness': 0.2, 'Insulation conductivity': 0.05,
    'HTF': 'INCOMP::NaK'}
comp_p = {'ptc_A': 3000, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6}
conn_p = {'5_T': 520, '6_T': 480, '6_p': 50, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}}

# Design Mode 5
sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p,
    conexion_params=conn_p, HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys.set_operation_mode(TESmode='5', profile=np.ones(20)*400, prev_TES_lay='Charge', mode='design')
sys.conn_13.set_attr(T=400)
sys.network.solve('design', max_iter=100)
sys.network.save('base_design_5')
print(f'Mode 5 design: kA={sys.charge_tes_hx.kA.val:.0f} T02={sys.conn_02.T.val:.0f}C T14=460C')
print()

# Offdesign coupling: T14 = T13+60, iterate T13
T_bot = 400.0
print('Hour | T_bot  T14   T02   T10   Q_ptc Q_ph  Q_hx')
print('-----|---------------------------------------------')
for hour in range(15):
    sys.conn_13.set_attr(T=T_bot)
    sys.conn_14.set_attr(T=T_bot + 60)
    sys.conn_10.set_attr(T=None)
    try:
        sys.network.solve('offdesign', max_iter=100, design_path='base_design_5')
    except:
        print(f'  {hour+1:2d} | NOT CONVERGED')
        break
    if not sys.network.converged:
        print(f'  {hour+1:2d} | NOT CONVERGED')
        break
    T14 = sys.conn_14.T.val; T02 = sys.conn_02.T.val; T10 = sys.conn_10.T.val
    Q_ptc = sys.ptc_field.Q.val/1e6; Q_ph = sys.preheater_hx.Q.val/1e6
    Q_hx = abs(sys.charge_tes_hx.Q.val)/1e6
    print(f'  {hour+1:2d} | {T_bot:5.0f} {T14:5.0f} {T02:5.0f} {T10:5.0f} {Q_ptc:5.1f} {Q_ph:4.1f} {Q_hx:4.1f}')
    T_bot += (T14 - T_bot) * 0.05
    if T_bot >= 480: break
print(f'\nAfter {hour+1}h: T_bot={T_bot:.0f}C, T14≈{T_bot+60:.0f}C')
print(f'Mode 3 viable at T14≈{T_bot+60:.0f}C > 505C: {T_bot+60>=505}')
