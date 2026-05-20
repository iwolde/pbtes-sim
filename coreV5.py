"""
coreV5.py — Backward Compatibility Shim
=========================================
Re-exports all public classes from the pbtes/ package so that any legacy
scripts using `from coreV5 import ...` continue to work without modification.

Do NOT add new logic here. All new code goes in pbtes/.
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
