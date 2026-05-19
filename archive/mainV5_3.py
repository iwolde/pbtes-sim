from coreV5_3 import Solver, Reporting 
import pandas as pd
import numpy as np

HTF = 'INCOMP::NaK'#'INCOMP::NaK'#'Water''CO2'
HTF_TES = 'Air'

tes_params = {
    'HTF': HTF_TES, 
    'Initial temperature': 470, #C
    'Tank lenght': 5, # m
    'Particle diameter': 50e-3,  # m  
    'Tank diameter': 5, # m
    'Void fraction': 0.4,  # -
    'Solid density': 3500,  # kg/m3 
    'Solid specific heat': 968,  # J/kg K 
    'Solid conductivity': 1.6,  # W/m K 
    'Wall thinckness': 10e-3,  # m 
    'Tank conductivity': 45,  # W/m K 
    'Insulation thickness': 500e-3,  # m 
    'Insulation conductivity': 0.03,  # W/m K 
              }
component_params = {
    'pump_eta_s': 0.85,
    'comp_eta_s': 0.8,
    'ptc_pr': 1,
    'ptc_aoi':20,
    'ptc_doc':1,
    'ptc_tamb':20,
    'ptc_A':1000,
    'eta_opt':0.816, 
    'ptc_c_1':0.0622, 
    'ptc_c_2':0.00023, 
    'ptc_E':900,
    'ptc_iam_1':-1.59e-3, 
    'ptc_iam_2':9.77e-5,
    'PR_pr':1,
    'PR_Q':-450000,
    'PH_pr':1,
    }

conexion_params = {
    '5_T':520,
    '6_T':480,
    '6_p':50,
    '6_f':{HTF:1},
    '13_p':5,
    '13_f':{HTF_TES:1},
    '15_p':5,
    '15_f':{HTF_TES:1}
     }

print('\nSolving design')
solver = Solver(
    tes_params=tes_params,
    component_params = component_params,
    conexion_params = conexion_params,
    HTF=HTF,
    system_mode= 'Full')
solver.init_steady(irr=920, mode='design')

tes_params['Initial temperature'] = 470
                 
print('\nSolving offdesign\n')
solver = Solver(
    tes_params=tes_params,
    component_params = component_params,
    conexion_params = conexion_params,
    HTF=HTF,
    system_mode= 'Full')
solver.init_steady(irr=720, mode='offdesign')

#%%
days_to_simulate = 3
solver = Solver(
tes_params=tes_params,
component_params=component_params,
conexion_params=conexion_params,
HTF=HTF,
system_mode='Full', # 'Full' | 'No TES' | 'No solar'
)

# 1) Inicializar diseños base por modo (recomendado antes del anual)
solver.initialize_modes()


# 2) Temperatura inicial del TES (ajusta si corresponde)
solver.tes_params['Initial temperature'] = 490


# 3) Correr la simulación anual (usa el logging integrado en run_quasi_steady_simulation)
result = solver.run_quasi_steady_simulation(
days_to_simulate=days_to_simulate,
csv='TMY.csv',
)

# 4) DataFrame con TODOS los campos (incluye columnas nuevas: mode_initial, mode_final,
# iter_status, attempt_count, attempted_modes, attempts_json, network_converged, etc.)
df_results = pd.DataFrame(result)


# 5) (Opcional) Métricas agregadas de desempeño
results_summary = solver.compute_performance_metrics()


# 6) Guardar CSV con metadatos de simulación (usa tu clase Reporting)
report = Reporting()

report.plot_results(df_results)
report.plot_results_mode(df_results)
report.plot_TES_profile_colormap(df_results)

report.save_simulation_to_csv(
df_results,
filepath="results_annual.csv", # cambia el nombre si quieres
solver=solver,
tes_params=tes_params,
component_params=component_params,
conexion_params=conexion_params,
sim_args={"days_to_simulate": days_to_simulate, "csv": "TMY.csv"}
)
#%%
report.plot_daily_powers_temps_massflows("results_annual.csv", power_unit="kW", 
                                         soc_unit="MWh", day="2022-01-02")
#%%
report = Reporting()
# Acumulado anual (elige unidad de salida)
report.plot_annual_cumulative_energy("test2.csv", out_unit="GWh")
report.plot_TES_profile_colormap_week("test2.csv", week=1)
report.plot_daily_powers_temps_massflows("test2.csv", power_unit="kW", 
                                         soc_unit="MWh", day="2022-01-14")

#%%

HTFs =['Water']#['Water', 'CO2', 'INCOMP::NaK']
#TES_diam = np.linspace(1.5,8,14)
TES_lengths = np.linspace(1,8,15)
#TES_diam = np.linspace(1,8,15)
TES_diam = np.linspace(5.5,8,6)
results = np.zeros((len(TES_diam), len(TES_lengths)))

days_to_simulate = 365

# Solve once in design mode:
initial_temp = 500

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

result_noTES = solver.compute_performance_metrics()

for j, d in enumerate(TES_diam):
    tes_params['Tank diameter'] = d
    for k, l in enumerate(TES_lengths):
                    
        tes_params['Tank lenght'] = l
        #tes_params['Tank diameter'] = l*2
        try:
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
            results[j,k] = solver.compute_performance_metrics() 
        except Exception:
            # Compute some performance metrics
            results[j,k] = result_noTES 
            

#%%

HTFs =['Water', 'CO2', 'INCOMP::NaK']
P = [50,50,5]
#TES_diam = np.linspace(1.5,8,14)
TES_diam = np.linspace(2,8,13)
results = np.zeros((len(HTFs),len(TES_diam)))

days_to_simulate = 365

# Solve once in design mode:
initial_temp = 500

result_noTES = 0

for j, h in enumerate(HTFs):
    conexion_params['6_f'] = {h:1}
    conexion_params['6_p'] = P[j]
    for k, d in enumerate(TES_diam):
        tes_params['Tank diameter'] = d
        tes_params['Tank lenght'] = 16/d
        name = 'Result_HTF['+str(h)+']_diam['+str(d)+'].csv'
        try:
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
            results[j,k] = solver.compute_performance_metrics() 
            report.save_simulation_to_csv(
                df_results,
                filepath=name,
                solver=solver,
                tes_params=tes_params,
                component_params=component_params,
                conexion_params=conexion_params,
                sim_args={"days_to_simulate": days_to_simulate, "csv": "TMY.csv"}
            )
        except Exception:
        # Compute some performance metrics
            results[j,k] = result_noTES 