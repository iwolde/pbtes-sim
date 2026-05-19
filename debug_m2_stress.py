"""Mode 2 convergence: isolated design + offdesign sweep with attempt_to_solve."""
import os, shutil, numpy as np, time
from coreV5 import SolarThermalSystem, Solver

for f in ['base_design_2','base_design_4']:
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
print('Design done.')

fails = 0
total = 0
for E in [1000, 900, 800, 700, 600, 500, 400, 300]:
    for _ in range(5):  # 5 attempts per E
        total += 1
        sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        sys.tes.profile = np.ones(20)*400
        sys.set_operation_mode(TESmode='2', current_irr=E, mode='offdesign',
            profile=sys.tes.profile, prev_TES_lay='Charge')
        ok, _, err = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '2', tries=5)
        if not (ok and sys.network.converged):
            fails += 1
            err_msg = str(err)[:60] if err else 'unknown'
            print(f'  E={E}: FAIL ({err_msg})')

print(f'\nTotal: {fails}/{total} failed')
