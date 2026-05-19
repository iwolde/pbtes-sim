from coreV3_5 import SolarThermalSystem, Solver, Reporting 
import pandas as pd

tes_params = {
    'Initial temperature': 550, #C
    'Tank lenght': 8, # m
    'Particle diameter': 40e-3,  # m  
    'Tank diameter': 7.5, # m
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
    'ptc_A':1100,
    'eta_opt':0.816, 
    'ptc_c_1':0.0622, 
    'ptc_c_2':0.00023, 
    'ptc_E':1000,
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
    '7_p':2,
    '7_f':{HTF:1},
    '16_p':1,
    '16_f':{'Air':1},
    '18_p':1,
    '18_f':{'Air':1}
    }

# 1) Create the system
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params,
                            HTF=HTF 
                            )
#system.create_network()

solver = Solver(system)
solver.solve_network_steady(current_irr=0)
system.network.print_results()


#%%
# Save design network for the 4 TES modes
# Mode 1
tes_params['Initial temperature'] = 430
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params,
                            HTF=HTF 
                            )
solver = Solver(system)
solver.solve_network_steady(current_irr=1000)
# Mode 2
tes_params['Initial temperature'] = 480
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params,
                            HTF=HTF 
                            )
solver = Solver(system)
solver.solve_network_steady(current_irr=1100)
# Mode 3
tes_params['Initial temperature'] = 550
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params,
                            HTF=HTF 
                            )
solver = Solver(system)
solver.solve_network_steady(current_irr=0)
# Mode 4
tes_params['Initial temperature'] = 420
system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params,
                            HTF=HTF 
                            )
solver = Solver(system)
solver.solve_network_steady(current_irr=0)

# # Mode 5
# tes_params['Initial temperature'] = 470
# system = SolarThermalSystem(rows=1, 
#                             tes_params=tes_params,
#                             component_params = component_params,
#                             conexion_params = conexion_params,
#                             HTF=HTF 
#                             )

# system.tes.profile[10] = 420
# solver = Solver(system)
# solver.solve_network_steady(current_irr=0)


#%%
days_to_simulate = 5
# Solve once in design mode:
tes_params['Initial temperature'] = 480

system = SolarThermalSystem(rows=1, 
                            tes_params=tes_params,
                            component_params = component_params,
                            conexion_params = conexion_params,
                            HTF=HTF 
                            )
#conexion_params['7_f'] = {HTF:1}

solver = Solver(system,
                system_mode = 'Full', #'Full' 'No TES' 'No solar'
                            )

# Pass the TMY to the simulation,
# specifying which columns contain DNI and Tamb:
results = solver.run_quasi_steady_simulation(
    days_to_simulate = days_to_simulate,
    csv = 'TMY.csv',
)

# Convert to DataFrame
df_results = pd.DataFrame(results)

# Compute some performance metrics
performance_metrics = solver.compute_performance_metrics()  
#%%

# 6) Plot using the new Reporting class
report = Reporting()
report.plot_results(df_results)
report.plot_TES_profile_colormap(df_results)