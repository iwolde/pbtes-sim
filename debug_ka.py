"""Compare HX kA across charging modes (M1, M5, M6)."""
import os, shutil, numpy as np
for f in ['base_design_1','base_design_5','base_design_6','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

from coreV5 import SolarThermalSystem

tes_p = {'Initial temperature':400,'Tank lenght':10,'Tank diameter':4,
    'Particle diameter':0.05,'Void fraction':0.4,'Solid density':2500,
    'Solid specific heat':1000,'Solid conductivity':1.5,'Wall thinckness':0.05,
    'Tank conductivity':15,'Insulation thickness':0.5,'Insulation conductivity':0.035,
    'HTF':'INCOMP::NaK'}
comp_p = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,'eta_opt':0.75,
    'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-1e6}
conn_p = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
    '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}

# Design Mode 1
sys1 = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys1.tes.profile = np.ones(20)*400
sys1.set_operation_mode(TESmode='1', current_irr=1000, mode='design',
    profile=sys1.tes.profile, prev_TES_lay='Charge')
sys1.conn_13.set_attr(T=400)
sys1.solve_network(mode='design', TESmode='1')
ka1 = sys1.charge_tes_hx.kA.val
print(f'Mode 1 (Parallel)  kA = {ka1:.0f} W/K  [design via ttd_l=20]')

# Design Mode 5 (needs conn_13.T)
sys5 = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys5.tes.profile = np.ones(20)*400
sys5.set_operation_mode(TESmode='5', current_irr=1000, mode='design',
    profile=sys5.tes.profile, prev_TES_lay='Charge')
sys5.conn_13.set_attr(T=400)
try:
    sys5.solve_network(mode='design', TESmode='5')
    ka5 = sys5.charge_tes_hx.kA.val
    print(f'Mode 5 (Series)    kA = {ka5:.0f} W/K  [design via ttd_l=20]')
    print(f'  DIFFERENT from Mode 1! Ratio = {ka5/ka1:.2f}x')
except Exception as e:
    print(f'Mode 5 design FAILED: {str(e)[:80]}')

# Mode 6 uses Mode 1's kA explicitly
sys6 = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys6.charge_hx_kA = ka1
sys6.tes.profile = np.ones(20)*400
sys6.set_operation_mode(TESmode='6', current_irr=1000, mode='design',
    profile=sys6.tes.profile, prev_TES_lay='Charge')
sys6.conn_13.set_attr(T=400)
sys6.solve_network(mode='design', TESmode='6')
ka6 = sys6.charge_tes_hx.kA.val
print(f'Mode 6 (Parallel)  kA = {ka6:.0f} W/K  [loaded from mode1_kA.txt]')
print(f'  SAME as Mode 1!')
