import CoolProp.CoolProp as CP
print(f"Water Tmin: {CP.get_fluid_param_string('Water', 'Tmin')}")
print(f"Water Tmax: {CP.get_fluid_param_string('Water', 'Tmax')}")
print(f"Water Tcrit: {CP.get_fluid_param_string('Water', 'Tcrit')}")

print(f"NaK Tmin: {CP.get_fluid_param_string('INCOMP::NaK', 'Tmin')}")
print(f"NaK Tmax: {CP.get_fluid_param_string('INCOMP::NaK', 'Tmax')}")
