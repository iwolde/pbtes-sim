from coreV3_0 import SolarThermalSystem, Solver, Reporting 
import pandas as pd

tes_params = {
    'Initial temperature': 500, #C
    'Tank lenght': 10, # m
    'Particle diameter': 40e-3,  # m  
    'Tank diameter': 10, # m
    'Void fraction': 0.4,  # -
    'Solid density': 3500,  # kg/m3 
    'Solid specific heat': 968,  # J/kg K 
    'Solid conductivity': 1.6,  # W/m K 
    'Wall thinckness': 7e-3,  # m 
    'Tank conductivity': 45,  # W/m K 
    'Insulation thickness': 25e-3,  # m 
    'Insulatuin conductivity': 0.03,  # W/m K 
              }


# 1) Create the system
system = SolarThermalSystem(rows=1, tes_params=tes_params, T_set_tes = 470)
system.create_network()

# 2) Define the HTF and boundary conditions in main, not in set_base_parameters().
#    For example, set compressor attributes:
system.comp.set_attr(eta_s=0.85)

#    Set collector parameters pero row (area, pr, DNI, design, etc.)
system.ptc_field.set_attr(pr=0.9, aoi=20, doc=1,
            Tamb=20, A=1000, eta_opt=0.816, c_1=0.0622, c_2=0.00023, E=0,
            iam_1=-1.59e-3, iam_2=9.77e-5)

# Outflow of process HX
system.conn_6.set_attr(T=430, p=50, fluid={'water': 1})
system.process_hx.set_attr(pr=0.99, Q=-1000000)

# TES HTF
system.conn_15.set_attr(p=1, fluid={'Air':1})
system.conn_17.set_attr(p=1, fluid={'Air':1})

# Preheater HX
#system.preheater_hx.set_attr(pr1=0.99, pr2=0.99)
system.preheater_hx.set_attr(pr=0.99)
system.conn_5.set_attr(T=550)

# Process connections
# system.conn_hx1.set_attr(T=420, p=1.1, m=50, fluid={'water': 1})
# system.conn_hx2.set_attr(T=470)

#Combustion connections
# system.conn_comb1.set_attr(m=3, p=2, T=25, fluid={'Ar': 0.0129, 'N2': 0.7553,
# 'CO2': 0.0004, 'O2': 0.2314})
# system.conn_comb2.set_attr(T=25, fluid={'CO2': 0.03, 'H2': 0.01, 'CH4': 0.96})

# # Flue gases outflow
# system.conn_preh1.set_attr(T=450)

#system.set_operation_mode(TESmode='discharge')
#system.gen_latex()
solver = Solver(system)
solver.solve_network_steady(TESmode='3')
solver.gen_latex()
system.network.print_results()


#%%
# 1) Choose how many days you want to simulate:
days_to_simulate = 2

# 2) Read TMY
tmy_data = pd.read_csv('TMY.csv', parse_dates=['Fecha/Hora'])
tmy_data.rename(columns={'Fecha/Hora': 'time'}, inplace=True)

# Filter out data for 'days_to_simulate' from the start
start_date = tmy_data['time'].min()
end_date   = start_date + pd.Timedelta(days=days_to_simulate)
filtered_data = tmy_data[(tmy_data['time'] >= start_date) & (tmy_data['time'] < end_date)]

# Solve once in design mode:
system.solve_network(mode='design')

# Pass the TMY to the simulation,
# specifying which columns contain DNI and Tamb:
results = solver.run_quasi_steady_simulation(
    data_frame=filtered_data,
    time_col='time',
    E_col='dni',
    Tamb_col='temp'  # or the actual name in your CSV
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