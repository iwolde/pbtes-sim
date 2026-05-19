"""Debug zinc pool step 0 -> step 1."""
import os, shutil, numpy as np, pandas as pd
for f in ['base_design_1','base_design_2','base_design_3','base_design_4',
           'base_design_5','base_design_6','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

from coreV5 import Solver

tes_p = {'Initial temperature':550,'Tank lenght':10,'Tank diameter':4,
    'Particle diameter':0.05,'Void fraction':0.4,'Solid density':3500,
    'Solid specific heat':968,'Solid conductivity':1.5,'Wall thinckness':0.05,
    'Tank conductivity':15,'Insulation thickness':0.5,'Insulation conductivity':0.035,
    'HTF':'INCOMP::NaK'}
comp_p = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,'eta_opt':0.75,
    'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-450000}
conn_p = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
    '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}
zinc_p = {'mass':150e3,'temp_initial':450,'cp_zinc':512,'UA_loss':500,
    'target_temp':450,'ttd_hx':20,'op_start_hour':8,'op_end_hour':20,
    'op_days_per_week':5,'mass_steel_per_hour':5000,'cp_steel':460,'T_steel_inlet':25}

s = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect', zinc_pool_params=zinc_p)
s.initialize_modes()
s.tes_params['Initial temperature'] = 550

tmy = pd.read_csv('TMY.csv')
tmy['Fecha/Hora'] = pd.to_datetime(tmy['Fecha/Hora'])
tmy['Fecha/Hora'] = tmy['Fecha/Hora'].apply(lambda x: x.replace(year=2022))

# Step 0
row = tmy.iloc[0]
E0 = row['dni']; Tamb0 = row['temp']; t0 = row['Fecha/Hora']
s.current_irr = E0
mode0 = s.get_system_mode(E0)
s.solar_system._zinc_pool_T06 = s.zinc_pool.process_outlet_temp()
s.solar_system.set_operation_mode(TESmode=mode0, current_irr=E0,
    profile=s.solar_system.tes.profile, prev_TES_lay=s.TES_lay, mode='offdesign')
s._iterate_tes_coupling(mode='offdesign', system=s.solar_system, TESmode=mode0,
    design_path=f'base_design_{mode0}', Tamb=Tamb0)
signals = s._collect_step_signals(s.solar_system, mode0)
q_kw = signals.get('process_hx_Q_kW', 0)
s.zinc_pool.update(Q_in_kW=q_kw, dt_s=3600, T_amb=Tamb0, timestamp=t0)
print(f'Step 0 ({t0}): E={E0}, mode={mode0}, zinc T={s.zinc_pool.temperature:.1f}C, Q_proc={q_kw:.0f}kW')

# Step 1
row = tmy.iloc[1]
E1 = row['dni']; Tamb1 = row['temp']; t1 = row['Fecha/Hora']
s.current_irr = E1
mode1 = s.get_system_mode(E1)
new_t06 = s.zinc_pool.process_outlet_temp()
s.solar_system._zinc_pool_T06 = new_t06
print(f'Step 1 ({t1}): E={E1}, mode={mode1}, zinc T06={new_t06}C')
s.solar_system.set_operation_mode(TESmode=mode1, current_irr=E1,
    profile=s.solar_system.tes.profile, prev_TES_lay=s.TES_lay, mode='offdesign')
try:
    s._iterate_tes_coupling(mode='offdesign', system=s.solar_system, TESmode=mode1,
        design_path=f'base_design_{mode1}', Tamb=Tamb1)
    print('Step 1 OK')
except Exception as e:
    print(f'Step 1 FAILED: {str(e)[:200]}')
