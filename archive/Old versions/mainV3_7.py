from coreV3_7 import Solver, Reporting 
import pandas as pd
import numpy as np

tes_params = {
    'Initial temperature': 435, #C
    'Tank lenght': 4, # m
    'Particle diameter': 40e-3,  # m  
    'Tank diameter': 6, # m
    'Void fraction': 0.4,  # -
    'Solid density': 3500,  # kg/m3 
    'Solid specific heat': 968,  # J/kg K 
    'Solid conductivity': 1.6,  # W/m K 
    'Wall thinckness': 7e-3,  # m 
    'Tank conductivity': 45,  # W/m K 
    'Insulation thickness': 25e-3,  # m 
    'Insulatuin conductivity': 0.03,  # W/m K 
              }
component_params = {
    'pump_eta_s': 0.85,
    'ptc_pr': 0.9,
    'ptc_aoi':20,
    'ptc_doc':1,
    'ptc_tamb':20,
    'ptc_A':950,
    'eta_opt':0.816, 
    'ptc_c_1':0.0622, 
    'ptc_c_2':0.00023, 
    'ptc_E':900,
    'ptc_iam_1':-1.59e-3, 
    'ptc_iam_2':9.77e-5,
    'PR_pr':0.99,
    'PR_Q':-450000,
    'PH_pr':0.99,
    }
HTF = 'INCOMP::NaK'#'INCOMP::NaK''Water''CO2'

conexion_params = {
    '6_T':550,
    '7_T':450,
    '7_p':50,
    '7_f':{HTF:1},
    '16_p':1,
    '16_f':{'Air':1},
    '18_p':1,
    '18_f':{'Air':1}
    }

solver = Solver(
    tes_params=tes_params,
    component_params = component_params,
    conexion_params = conexion_params,
    HTF=HTF,
    system_mode= 'No TES')
solver.init_steady(irr=1000)
#%%
# system.network.print_results()


# Save design network for the 5 TES modes
#solver.initialize_modes()

#%%
days_to_simulate = 5
solver = Solver(
    tes_params=tes_params,
    component_params = component_params,
    conexion_params = conexion_params,
    HTF=HTF,
    system_mode = 'Full' , #'Full' 'No TES' 'No solar'
    )
    
solver.initialize_modes()
solver.tes_params['Initial temperature'] = 470

result = solver.run_quasi_steady_simulation(
    days_to_simulate = days_to_simulate,
    csv = 'TMY.csv',
)        
# Compute some performance metrics
results = solver.compute_performance_metrics() 

df_results = pd.DataFrame(result)

# 6) Plot using the new Reporting class
report = Reporting()
report.plot_results(df_results)
report.plot_TES_profile_colormap(df_results)

#%%

HTFs =['Water', 'CO2', 'INCOMP::NaK']
Ps = np.linspace(5,70,3)
TES_lengths = np.linspace(1.5,4,6)

results = np.zeros((len(HTFs), len(Ps), len(TES_lengths)+1))

days_to_simulate = 365

# Solve once in design mode:
initial_temp = 440


for i, HTF in enumerate(HTFs):
    conexion_params['7_f'] = {HTF:1}
    for j, p in enumerate(Ps):
        conexion_params['7_p'] = p
        solver = Solver(
            tes_params=tes_params,
            component_params = component_params,
            conexion_params = conexion_params,
            HTF=HTF,
            system_mode = 'No TES' , #'Full' 'No TES' 'No solar'
            )
            
        solver.initialize_modes()
        solver.tes_params['Initial temperature'] = initial_temp
        result = solver.run_quasi_steady_simulation(
            days_to_simulate = days_to_simulate,
            csv = 'TMY.csv',
        )        
        # Compute some performance metrics
        results[i,j,0] = solver.compute_performance_metrics()  
        for k, l in enumerate(TES_lengths):
                        
            tes_params['Tank lenght'] = l
            tes_params['Tank diameter'] = l*1.5
            
            solver = Solver(
                tes_params=tes_params,
                component_params = component_params,
                conexion_params = conexion_params,
                HTF=HTF,
                system_mode = 'Full' , #'Full' 'No TES' 'No solar'
                )
            
            solver.initialize_modes()
            solver.tes_params['Initial temperature'] = initial_temp
            result = solver.run_quasi_steady_simulation(
                days_to_simulate = days_to_simulate,
                csv = 'TMY.csv',
            )        
            # Compute some performance metrics
            results[i,j,k+1] = solver.compute_performance_metrics() 
            

# #%%
# df_results = pd.DataFrame(result)

# # 6) Plot using the new Reporting class
# report = Reporting()
# report.plot_results(df_results)
# report.plot_TES_profile_colormap(df_results)