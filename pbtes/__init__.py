# PBTES Simulation Package
#
# Solar thermal plant simulation with Packed Bed Thermal Energy Storage (PBTES)
# for industrial process heat (zinc galvanizing). Uses the TESPy library for
# thermodynamic network solving.
#
# Main entry point:
#   from pbtes import Solver, Reporting
#
# Architecture (bottom-up):
#   components/    — PTCField (TESPy component extensions)
#   storage/       — ThermalEnergyStorage, ZincPool (physics models)
#   network/       — SolarThermalSystem (TESPy network construction)
#   simulation/    — Solver (orchestration, coupling, weather)
#   reporting/     — Reporting (plots, CSV I/O, monthly breakdown)
#   analysis/      — convergence analysis, economics (standalone tools)

from pbtes.components import PTCField
from pbtes.storage import ThermalEnergyStorage, ZincPool
from pbtes.network.system import SolarThermalSystem
from pbtes.simulation.solver import Solver
from pbtes.reporting.plots import Reporting

__version__ = '1.0.0'
__all__ = [
    'PTCField',
    'ThermalEnergyStorage',
    'ZincPool',
    'SolarThermalSystem',
    'Solver',
    'Reporting',
]
