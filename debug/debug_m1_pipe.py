"""Mode 1 test using full initialize_modes pipeline."""
import os, shutil, numpy as np; from coreV5 import Solver
for f in ['base_design_1','base_design_2','base_design_3','base_design_4','base_design_5','base_design_6','mode1_kA.txt']:
    if os.path.exists(f):
        if os.path.isfile(f): os.remove(f)
        else: shutil.rmtree(f, ignore_errors=True)

tp = {'Initial temperature':400,'Tank length':10,'Tank diameter':4,'Particle diameter':0.05,'Void fraction':0.4,
    'Solid density':3500,'Solid specific heat':968,'Solid conductivity':1.5,'Wall thickness':0.05,
    'Tank conductivity':15,'Insulation thickness':0.5,'Insulation conductivity':0.035,'HTF':'INCOMP::NaK'}
cp = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,'eta_opt':0.75,'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,
    'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-450000}
np_ = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},'13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}

s = Solver(tes_params=tp, component_params=cp, conexion_params=np_, HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
s.initialize_modes()
print(f'M1 kA = {s.charge_hx_kA:.0f}')
s.current_irr = 0

oks = 0; total = 0
for E in [1000, 800, 600]:
    for T_bot in [400, 450, 500]:
        total += 1
        import types; from coreV5 import SolarThermalSystem
        s2 = SolarThermalSystem(tes_params=dict(tp), component_params=dict(cp), conexion_params=dict(np_),
            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        s2.tes.profile = np.ones(20)*T_bot
        s2.set_operation_mode(TESmode='1', current_irr=E, mode='offdesign',
            profile=s2.tes.profile, prev_TES_lay='Charge')
        s2.conn_13.set_attr(T=T_bot)
        ok, _, _ = s.attempt_to_solve(s2, 'offdesign', 'base_design', '1', tries=3)
        if ok and s2.network.converged:
            oks += 1
            print(f'E={E} T_bot={T_bot}: OK')
        else:
            print(f'E={E} T_bot={T_bot}: FAIL')
print(f'\n{oks}/{total} converged')
