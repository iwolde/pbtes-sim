"""Mode 1 offdesign debug - capture actual error."""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem, Solver

for f in ['base_design_1','base_design_4','mode1_kA.txt']:
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

solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.initialize_modes()
print('Design OK. CHX kA =', solver.charge_hx_kA)
print('Design PTC A =', solver.solar_system.ptc_field.A.val)

solver.current_irr = 0

# Test offdesign at E=1000
sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys.tes.profile = np.ones(20)*450
sys.set_operation_mode(TESmode='1', current_irr=1000, mode='offdesign',
    profile=sys.tes.profile, prev_TES_lay='Charge')
sys.conn_13.set_attr(T=450)

# Inspect what's set on the CHX
print('\nCHX state before solve:')
print(f'  ttd_l is_set={sys.charge_tes_hx.ttd_l.is_set}, val={sys.charge_tes_hx.ttd_l.val}')
print(f'  kA is_set={sys.charge_tes_hx.kA.is_set}, val={sys.charge_tes_hx.kA.val}')
print(f'  Q is_set={sys.charge_tes_hx.Q.is_set}')

print('\nTrying direct offdesign solve:')
try:
    sys.solve_network(mode='offdesign', design_path='base_design_1', TESmode='1')
    print(f'OK! T02={sys.conn_02.T.val:.0f}')
except Exception as e:
    print(f'FAILED: {str(e)[:200]}')
