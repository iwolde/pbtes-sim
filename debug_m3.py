"""Mode 3 audit: TES discharge to process."""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem, Solver

for f in ['base_design_3','base_design_4']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {'Initial temperature':400,'Tank lenght':10,'Tank diameter':4,
    'Particle diameter':0.05,'Void fraction':0.4,'Solid density':2500,
    'Solid specific heat':1000,'Solid conductivity':1.5,
    'Wall thinckness':0.05,'Tank conductivity':15,
    'Insulation thickness':0.5,'Insulation conductivity':0.035,
    'HTF':'INCOMP::NaK'}
comp_p = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,
    'eta_opt':0.75,'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,
    'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-1e6}
conn_p = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
    '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}

# --- DESIGN ---
sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys.tes.profile = np.ones(20)*540
sys.set_operation_mode(TESmode='3', current_irr=0, mode='design',
    profile=sys.tes.profile, prev_TES_lay='Discharge')
sys.conn_15.set_attr(T=540)
print('=== MODE 3 DESIGN (T15=540) ===')
try:
    sys.solve_network(mode='design', TESmode='3')
    conv = sys.network.converged
    print(f'Converged: {conv}')
    if conv:
        print(f'  DHX kA={sys.discharge_tes_hx.kA.val:.0f}')
        print(f'  T04={sys.conn_04.T.val:.0f} T05={sys.conn_05.T.val:.0f} T11={sys.conn_11.T.val:.0f}')
        print(f'  Q_DHX={sys.discharge_tes_hx.Q.val/1e6:.2f} MW  Q_PH={sys.preheater_hx.Q.val/1e6:.2f} MW')
        print(f'  m_proc={sys.conn_05.m.val:.1f} kg/s')
except Exception as e:
    print(f'FAILED: {str(e)[:120]}')

# --- OFFDESIGN at multiple T15 ---
print('\n=== MODE 3 OFFDESIGN ===')
solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.current_irr = 0
for T_tes in [540, 530, 520, 510, 505]:
    sys3 = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    sys3.tes.profile = np.ones(20)*T_tes
    sys3.set_operation_mode(TESmode='3', current_irr=0, mode='offdesign',
        profile=sys3.tes.profile, prev_TES_lay='Discharge')
    sys3.conn_15.set_attr(T=T_tes)
    ok, _, _ = solver.attempt_to_solve(sys3, 'offdesign', 'base_design', '3', tries=5)
    if ok and sys3.network.converged:
        Q_dhx = sys3.discharge_tes_hx.Q.val/1e6
        Q_ph = sys3.preheater_hx.Q.val/1e6
        t04 = sys3.conn_04.T.val
        t16 = sys3.conn_16.T.val
        m = sys3.conn_05.m.val
        print(f'  T15={T_tes}: DHX={Q_dhx:.2f}MW PH={Q_ph:.2f}MW T04={t04:.0f} T16={t16:.0f} m={m:.1f}')
    else:
        print(f'  T15={T_tes}: FAILED')
