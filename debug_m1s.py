"""Mode 1 offdesign sweep across A, D, E, T_bot."""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem

tests = []
for A in [1000, 2500, 5000]:
    for D in [4, 7]:
        for E in [1000, 800, 600]:
            for T_bot in [400, 450]:
                tests.append((A, D, E, T_bot))

results = []
for A, D, E, T_bot in tests:
    for f in ['base_design_1','mode1_kA.txt']:
        if os.path.exists(f):
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
    
    tp = {'Initial temperature':400,'Tank length':10,'Tank diameter':D,
        'Particle diameter':0.05,'Void fraction':0.4,'Solid density':3500,
        'Solid specific heat':968,'Solid conductivity':1.5,'Wall thickness':0.05,
        'Tank conductivity':15,'Insulation thickness':0.5,'Insulation conductivity':0.035,
        'HTF':'INCOMP::NaK'}
    cp = {'ptc_A':A,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,'eta_opt':0.75,
        'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-450000}
    np_ = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
        '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}
    
    try:
        sys = SolarThermalSystem(tes_params=dict(tp), component_params=dict(cp), conexion_params=dict(np_),
            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        sys.tes.profile = np.ones(20)*400
        sys.set_operation_mode(TESmode='1', current_irr=1000, mode='design',
            profile=sys.tes.profile, prev_TES_lay='Charge')
        sys.conn_13.set_attr(T=400)
        sys.solve_network(mode='design', TESmode='1')
        if not sys.network.converged:
            results.append((f'A={A} D={D} E={E} Tb={T_bot}', 'DES_FAIL'))
            continue
        
        s2 = SolarThermalSystem(tes_params=dict(tp), component_params=dict(cp), conexion_params=dict(np_),
            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        s2.tes.profile = np.ones(20)*T_bot
        s2.set_operation_mode(TESmode='1', current_irr=E, mode='offdesign',
            profile=s2.tes.profile, prev_TES_lay='Charge')
        s2.conn_13.set_attr(T=T_bot)
        s2.network.set_attr(iterinfo=False)
        s2.solve_network(mode='offdesign', design_path='base_design_1', TESmode='1', use_init_path=True)
        results.append((f'A={A} D={D} E={E} Tb={T_bot}', 'OK' if s2.network.converged else 'NO_CONV'))
    except Exception as e:
        results.append((f'A={A} D={D} E={E} Tb={T_bot}', f'ERR:{str(e)[:40]}'))

for cfg, res in results:
    print(f'{cfg:<28s} {res}')
oks = sum(1 for _,r in results if r=='OK')
print(f'\n{oks}/{len(results)} converged')
