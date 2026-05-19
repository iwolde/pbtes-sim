from coreV3_2 import SolarThermalSystem, Solver, Reporting 
import pandas as pd

tes_params = {
    'Initial temperature': 450, #C
    'Tank lenght': 4, # m
    'Particle diameter': 40e-3,  # m  
    'Tank diameter': 4, # m
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
    'comp_eta_s': 0.85,
    'ptc_pr': 0.9,
    'ptc_aoi':20,
    'ptc_doc':1,
    'ptc_tamb':20,
    'ptc_A':900,
    'eta_opt':0.816, 
    'ptc_c_1':0.0622, 
    'ptc_c_2':0.00023, 
    'ptc_E':1000,
    'ptc_iam_1':-1.59e-3, 
    'ptc_iam_2':9.77e-5,
    'PR_pr':0.99,
    'PR_Q':-1000000,
    'PH_pr':0.99,
    }

#print(component_params['comp_eta_s'])
conexion_params = {
    '5_T':550,
    '6_T':430,
    '6_p':50,
    '6_f':{'Air':1},
    '15_p':1,
    '15_f':{'Air':1},
    '17_p':1,
    '17_f':{'Air':1},
    'T_set_tes':455
    }

# 1) Create the system
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params
                            )
#system.create_network()

solver = Solver(system)
solver.solve_network_steady(TESmode='1')
solver.gen_latex()
system.network.print_results()


#%%
# Save design network for the 4 TES modes
tes_params['Initial temperature'] = 450
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params
                            )
solver = Solver(system)
solver.solve_network_steady(TESmode='1')
tes_params['Initial temperature'] = 450
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params
                            )
solver = Solver(system)
solver.solve_network_steady(TESmode='2')
tes_params['Initial temperature'] = 470
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params
                            )
solver = Solver(system)
solver.solve_network_steady(TESmode='3')
tes_params['Initial temperature'] = 450
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params
                            )
solver = Solver(system)
solver.solve_network_steady(TESmode='4')

#%%
# 1) Choose how many days you want to simulate:
days_to_simulate = 5

# 2) Read TMY
tmy_data = pd.read_csv('TMY.csv', parse_dates=['Fecha/Hora'])
tmy_data.rename(columns={'Fecha/Hora': 'time'}, inplace=True)

# Filter out data for 'days_to_simulate' from the start
start_date = tmy_data['time'].min()
end_date   = start_date + pd.Timedelta(days=days_to_simulate)
filtered_data = tmy_data[(tmy_data['time'] >= start_date) & (tmy_data['time'] < end_date)]

# Solve once in design mode:
tes_params['Initial temperature'] = 386

system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params
                            )
solver = Solver(system)

# Pass the TMY to the simulation,
# specifying which columns contain DNI and Tamb:
results = solver.run_quasi_steady_simulation(
    data_frame=filtered_data,
    time_col='time',
    E_col='dni',
    Tamb_col='temp',  # or the actual name in your CSV
)

# Convert to DataFrame
df_results = pd.DataFrame(results)

# 5) (Optional) Compute some performance metrics
performance_metrics = solver.compute_performance_metrics()  
#%%

# 6) Plot using the new Reporting class
report = Reporting()
report.plot_results(df_results)
report.plot_TES_profile_colormap(df_results)