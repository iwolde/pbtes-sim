from pbtes.config import baseline_config
from pbtes.network.system import SolarThermalSystem

tes_p, comp_p, conn_p = baseline_config()
# Ensure we have correct keys
tes_p['Initial temperature'] = 400.0
sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p, topology='Parallel')
sys.create_network(mode=1)

print("Attributes of sys.conn_14.T:")
print(dir(sys.conn_14.T))

print("\nValue of T.val:", sys.conn_14.T.val)
print("Type of T:", type(sys.conn_14.T))
