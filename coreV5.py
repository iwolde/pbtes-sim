"""
core.py

This module contains:
1) The SolarThermalSystem class, which builds and solves a TESPy network
   with supercritical CO2 as the working fluid, a pump, a parabolic
   trough collector, and a simple process heat exchanger.

2) The Reporting class, which handles plotting of results from a parametric
   analysis or time-step simulation.

All methods are commented with details on their purpose and functionality.
"""
import tespy.networks as tpn
import tespy.connections as tpcn
import tespy.components as tpc
from tespy.components.heat_exchangers.parabolic_trough import ParabolicTrough
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from tqdm import tqdm
import time
import pandas as pd
import numpy as np
import json, os
from copy import deepcopy
import CoolProp.CoolProp as cp
from scipy.optimize import brentq
from scipy.interpolate import interp1d

from pbtes.components import PTCField
from pbtes.storage import ThermalEnergyStorage


from pbtes.storage import ZincPool
from pbtes.network.system import SolarThermalSystem

from pbtes.simulation.solver import Solver
from pbtes.reporting.plots import Reporting
