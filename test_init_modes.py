from coreV5 import Solver
import os, shutil

for f in ['base_design_1','base_design_2','base_design_3','base_design_4','base_design_5','base_design_6','mode1_kA.txt']:
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
comp_p = {'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6}
conn_p = {'5_T': 520, '6_T': 480, '6_p': 50, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}}

solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.initialize_modes()

for m in range(1,7):
    exists = os.path.exists(f'base_design_{m}')
    print(f'Mode {m} design: {"OK" if exists else "MISSING"}')

if os.path.exists('mode1_kA.txt'):
    with open('mode1_kA.txt') as f:
        print(f'kA file: {float(f.read()):.0f}')
print(f'Solver kA: {getattr(solver, "charge_hx_kA", "NONE")}')
print('Done')
