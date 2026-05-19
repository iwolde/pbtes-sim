"""Mode 5 audit: High-T Series charge."""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem, Solver

for f in ['base_design_1','base_design_5','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {'Initial temperature':400,'Tank lenght':10,'Tank diameter':4,
    'Particle diameter':0.05,'Void fraction':0.4,'Solid density':2500,
    'Solid specific heat':1000,'Solid conductivity':1.5,'Wall thinckness':0.05,
    'Tank conductivity':15,'Insulation thickness':0.5,'Insulation conductivity':0.035,
    'HTF':'INCOMP::NaK'}
comp_p = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,'eta_opt':0.75,
    'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-1e6}
conn_p = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
    '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}

solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.initialize_modes()
solver.current_irr = 0
print(f'Design done. M1 kA={solver.charge_hx_kA:.0f}')

for E in [1000, 800, 600]:
    for T_bot in [450, 400]:
        sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        sys.tes.profile = np.ones(20)*T_bot
        sys.set_operation_mode(TESmode='5', current_irr=E, mode='offdesign',
            profile=sys.tes.profile, prev_TES_lay='Charge')
        sys.conn_13.set_attr(T=T_bot)
        ok, _, _ = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '5', tries=3)
        status = 'OK' if ok and sys.network.converged else 'FAIL'
        t02 = sys.conn_02.T.val if ok and hasattr(sys,'conn_02') else '?'
        t14 = sys.conn_14.T.val if ok and hasattr(sys,'conn_14') else '?'
        print(f'  E={E} T_bot={T_bot}: {status} T02={t02} T14={t14}')
