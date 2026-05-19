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
#import tespy.tools.document_models as ttdm
from tespy.components.heat_exchangers.parabolic_trough import ParabolicTrough
import matplotlib.pyplot as plt
from tqdm import tqdm
import time
import pandas as pd
import numpy as np
import CoolProp.CoolProp as cp
from scipy.optimize import brentq
from scipy.interpolate import interp1d

class PTCField(ParabolicTrough):
    """
    A parabolic trough collector field composed of several parallel rows.

    This subclass internally divides the inlet mass flow among the rows,
    calculates as if there's only one row, and then scales Q, Qloss, etc.
    by the number of rows.
    """

    def __init__(self, label, rows=1, modules=1, **kwargs):
        """
        Parameters
        ----------
        label : str
            The label for the collector.
        rows : int
            Number of identical parallel rows in the solar field.
        kwargs :
            Any additional keyword arguments you want to pass to
            the parent ParabolicTrough constructor (e.g. collector geometry).
        """
        super().__init__(label, **kwargs)
        self.rows = rows
        self.modules = modules

        # We'll store the "single module pr" here if the user sets it
        self.pr_module = None

    def calc_parameters(self):
        """
        Override the parent's calculation routine to:
          - Temporarily reduce mass flow to 1/rows,
          - Call parent calculations,
          - Scale the results by rows,
          - Restore total flow at the outlet.
        """
        # 1) Store total inlet mass flow and total area
        total_m_in = self.inl[0].m.val_SI
        
        # 2) Scale both mass flow and area for a single-row
        if self.rows > 1:
            # Inlet flow
            self.inl[0].m.val_SI = total_m_in / self.rows


        # 3) Run the usual collector calculation (for the scaled single-row)
        super().calc_parameters()

        # 4) Scale Q and Q_loss from single-row to total field
        if self.rows > 1:
            # self.Q is a ComponentProperties object
            self.Q.val_SI *= self.rows
            # self.Q_loss may not always be present, so check first
            if hasattr(self, 'Q_loss'):
                self.Q_loss.val_SI *= self.rows

        # 5) Restore the total mass flow and total area on the outlet and component
        self.outl[0].m.val_SI = total_m_in
      
class ThermalEnergyStorage:
    """
    Manages the thermal energy storage with capability to store, release, or maintain energy,
    simulating temperature profiles and managing energy state.
    """

    def __init__(self, tes_params, name, dt):
        """
        

        Parameters
        ----------
        dt : Int
            Time step.
        tes_params : Dict
            DESCRIPTION.
        name : Str
            TES name.

        Returns
        -------
        None.

        """
        """
        Initializes the thermal energy storage unit.
        :param capacity: float, the energy storage capacity in kWh.
        :param initial_temperature: float, the initial temperature of the storage in degrees Celsius.
        :param name: str, name of the TES module.
        """

        self.dt = dt #min

        self.name = name
        self.state = 'charge'  # default state
        self.inlet = 'top'
        self.outlet = 'bottom'
        self.valve_state = 'off'  # Valve controlling the TES flow
    
        self.initial_temperature = tes_params['Initial temperature']
        self.HT = tes_params['Tank lenght']
        self.Dint = tes_params['Tank diameter']
        self.dp = tes_params['Particle diameter']
        self.e = tes_params['Void fraction']
        self.rho_s = tes_params['Solid density']
        self.cp_s = tes_params['Solid specific heat']
        self.k_s = tes_params['Solid conductivity']
        self.wst = tes_params['Wall thinckness']
        self.kst = tes_params['Tank conductivity']
        self.wins = tes_params['Insulation thickness']
        self.kins = tes_params['Insulation conductivity']
        self.HTF = tes_params['HTF']
        self.AT = 0.25 * self.Dint**2 * np.pi  # m2 - Área transversal del estanque
        self.Aphi = 0.25 * (25.4e-3*2)**2* np.pi  # m2 - Área transversal del tubo de descarga
        
        self.HTF_P = 102325
        
        self.xev = np.linspace(0,1,20)
        self.init = np.ones_like(self.xev)*(self.initial_temperature)
        self.profile = self.init
        self.t_max = self.initial_temperature
        self.t_min = self.initial_temperature
        self.tout = self.initial_temperature
        self.mflow = 0
        self.V_in = 0

    def air_params(self):
        # Temperatura media
        Tav = np.average(self.init)+273.15
        # Propiedades del fluido - Calculados a temperatura media
        self.rho_f = cp.PropsSI('D', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.cp_f = cp.PropsSI('C', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.k_f = cp.PropsSI('L', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.mu_f = cp.PropsSI('V', 'T', Tav, 'P', self.HTF_P, self.HTF)
        
        self.rho_out = cp.PropsSI('D', 'T', self.tout+273.15, 'P', self.HTF_P, self.HTF)
        
    def eq_params(self, T_in, mass_flow):
        """
        

        Parameters
        ----------
        T_in : Float
            Inlet Temperature.
        V_in : Float
            Inlet Velocity.

        Returns
        -------
        None.

        """
 
        self.t_in = T_in
        
        self.mflow = mass_flow #kg/min
        #print(self.mflow)
        
        self.air_params()
        
        # Flujo másico por unidad de área al interior del TES
        G = self.mflow / self.AT 
        # Cálculo de alpha y k_eff
        Re = G*self.dp/self.mu_f  # Reynolds
        Pr = self.mu_f * self.cp_f / self.k_f  # Prandtl
        ff = 6*(1-self.e)/self.dp  # m - Factor de forma roca - fluido
        rho_cp_line = (self.e * self.rho_f * self.cp_f + (1-self.e) * self.rho_s * self.cp_s) # Capacitancia equivalente
        self.kappa = self.e * (self.rho_f * self.cp_f) / rho_cp_line  # Factor kappa (adimensional de interés para el modelo)
        u_in = G / (self.rho_f)  # m/s - Velocidad intersticial
        hv = ff * (self.k_f/self.dp) * 1.32 * Re**0.59 * Pr**(1/3)  # W/m3 K - Coef. de transferencia de calor volumétrica (Tesis Daniel Orellana)
        k_line = (self.e *self.k_f + (1-self.e)*self.k_s) # Conductividad promedio
        k_eff = k_line + ((1-self.e) * (self.rho_s*self.cp_s) * (G*self.cp_f/rho_cp_line))**2/hv  # Conductividad efectiva (Ver ec. 7 de Paper 1)
        alpha = k_eff / rho_cp_line  # Cálculo de alpha
        self.Pe = u_in * self.HT / alpha  # Cálculo de Péclet que cambia con el tiempo (adimensional de interés para el modelo)
        self.a = self.kappa * self.Pe / 2
       
        # Resistencia interna
        hint = (self.k_f/self.dp) * (0.203 * Re**(1/3) * Pr**(1/3) + 0.22 * Re**0.8 * Pr**0.4)
        Rint = 1/hint
        # Coeficiente de transferencia de calor
        hw = 1/Rint
        # Stanton
        self.beta = 4/self.Dint
        #self.St = 0.75*hw*self.beta*self.HT/(rho_cp_line*u_in)
        self.St = 0#1e-3
        self.b = -(self.St + self.a**2/self.Pe)
        
        self.tau = u_in*self.dt/self.HT
        

    def _eq(self, ev, a):
        """
        Ecuación trascendental para obtener autovalores

        Parameters
        ----------
        ev : TYPE
            DESCRIPTION.
        a : TYPE
            DESCRIPTION.

        Returns
        -------
        eq : TYPE
            DESCRIPTION.

        """
    
        # solve transcendental eq : ev + a * tan(ev) = 0
        eq1 = ev / a
        eq2 = np.tan(ev)
        eq = eq1 + eq2
    
        return eq    
    
    def solve_eq(self, Nroots, a):
        """
        Algoritmo de búsqueda de raíces

        Parameters
        ----------
        Nroots : Roots number.
        a : Parameter a.

        Returns
        -------
        rts : Roots.

        """
        
        # Allocate space
        rts = np.zeros(Nroots)
        # Margin to stay away from poles
        margin = 1e-5
        # First solution
        left = 0
        right = np.pi / (2)
        _ = brentq(self._eq, left, right - margin, args=(a))
        for i in range(1, Nroots+1):
            left = (2*i - 1)*np.pi/(2)
            right = (2*i + 1)*np.pi/(2)
            rts[i-1] = brentq(self._eq, left + margin, right - margin, args=(a))
    
        return rts    

    def calc_solution(self):
        """
        Función que evalúa la solución dadas las condiciones de un paso de tiempo

        Returns
        -------
        sol : List
            DESCRIPTION.

        """
        theta = (self.t_in-self.t_min)/(self.t_max-self.t_min)
        init = (self.init-self.t_min)/(self.t_max-self.t_min)
        ############# Sol. Estacionaria
        # Definir constantes de la solución estacionaria
        k1 = np.longfloat(0.5 * (self.kappa * self.Pe - np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        k2 = np.longfloat(0.5 * (self.kappa * self.Pe + np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        C2 = theta * k1 * np.exp(k1) / (k1*np.exp(k1) - k2*np.exp(k2))
        C1 = theta - C2
        # Solución estacionaria
        Mx = lambda x : C1*np.exp(k1*x) + C2*np.exp(k2*x)
    
        ############# Sol. Transiente        
        # Calcular autovalores
        lbd = self.solve_eq(200, self.a)
        # Definir la functión Kernel
        fn = np.sqrt(2) * np.sqrt((lbd**2 + self.a**2)/(lbd**2 + self.a**2 + self.a))
        Knx = lambda x : fn[:, None] * np.sin(lbd[:, None]*x)
        # Transformada integral de la solución inicial
        # 1, Interpolar datos de la condición inicial
        xint = np.linspace(0, 1, 200)
        t0_int = interp1d(self.xev, init, bounds_error=False, fill_value='extrapolate')(xint)
        phi0 = (t0_int - Mx(xint)) / np.exp(self.a*xint)
        phi0n = np.trapz(Knx(xint)*phi0, x=xint, axis=1)
        # 2, Solución del problema de autovalores
        phin = phi0n[:, None] * np.exp(-lbd[:, None]**2 * self.tau / self.Pe)
        # 3, Solución del problema transiente
        Nxt = np.exp(self.a*self.xev[:, None] + self.b*self.tau) * (np.sum(phin * Knx(self.xev), axis=0)[:, None])
    
        ############# Sol.
        sol = Mx(self.xev)[:, None] + Nxt
    
        return sol
    
    def update_temperature_profile(self, T_in, mass_flow, initial_profile):
        """
        Updates the temperature profile of the TES for the given time.

        Parameters
        ----------
        dt : TYPE
            Time step.
        mass_flow : Float
            Inlet mass flow [kg/s].
        T_in : Float
            Inlet Temperature [°C].

        Returns
        -------
        None.

        """
        
        self.init = initial_profile
        self.t_max = max(self.profile.max(), T_in)
        self.t_min = min(self.profile.min(), T_in)
        self.eq_params(T_in, mass_flow)
        self.profile = self.calc_solution().reshape((len(self.xev), ))*(self.t_max-self.t_min) + self.t_min
        self.init = self.profile
        self.tout = self.profile[-1]
        return self.profile
    
    def calc_heat_loss(self, profile, dt, T_amb):
        """
        Update the temperature profile of a stratified TES packed bed over a time step dt.
        
        The packed bed consists of a solid matrix and a fluid. Fluid properties (density and cp)
        are calculated using CoolProp at the current layer temperature. The effective thermal capacity 
        (mass*cp) for each layer is computed from the contributions of both the fluid and the solid.

        Returns:
            np.array: Updated temperature profile (in °C) after dt seconds.
            
        Notes:
            - Each layer has a volume V_layer = A_cross * dz, with dz = height / n_layers and 
              A_cross = π*(diameter/2)².
            - The effective thermal capacity of a layer is computed as:
                  C_eff = V_layer * [epsilon * (fluid_density*fluid_cp) + (1-epsilon)*(solid_density*solid_cp)]
              where the fluid properties are computed at the layer temperature (converted to Kelvin).
            - For heat loss, the thermal resistance is given by:
                  R_total = wall_thickness/(wall_k*A) + ins_thickness/(ins_k*A)
              with the effective area A determined as follows:
                  Top layer: A = (top surface area) + (lateral wall area of the layer)
                  Bottom layer: A = (lateral wall area of the layer) [no bottom surface]
                  Interior layers: A = (lateral wall area of the layer)
            - The heat loss Q_loss (in Watts) is computed by:
                  Q_loss = (T_layer - ambient_temp) / R_total
            - Temperature drop dT = Q_loss*dt/C_eff, with T_new = T_old - dT.
        """
        n_layers = len(profile)
        dz = self.HT / n_layers
        A_cross = np.pi * (self.Dint / 2)**2  # Cross-sectional area of the tank
        volume_layer = A_cross * dz          # Volume of each layer
        
        new_T_profile = np.zeros_like(profile)
        
        # Loop over each layer (top to bottom)
        for i, T in enumerate(profile):
            # Convert layer temperature from °C to Kelvin for CoolProp calculations
            T_K = T + 273.15
            fluid_density = cp.PropsSI('D', 'T', T_K, 'P', self.HTF_P, self.HTF)  # kg/m³
            fluid_cp = cp.PropsSI('C', 'T', T_K, 'P', self.HTF_P, self.HTF)         # J/kg·K
            
            # Compute effective thermal capacity (J/K) for the layer:
            # (fluid and solid contributions weighted by their volume fractions)
            effective_capacity = volume_layer * (self.e * fluid_density * fluid_cp +
                                                 (1 - self.e) * self.rho_s * self.cp_s)
            
            # Determine the effective heat loss area for this layer:
            if i == 0:
                # Top layer: loss via top surface + lateral wall area of the layer
                area = A_cross + (np.pi * self.Dint * dz)
            elif i == n_layers - 1:
                # Bottom layer: loss only via lateral wall (no bottom heat loss)
                area = np.pi * self.Dint * dz
            else:
                # Interior layers: lateral wall area only
                area = np.pi * self.Dint * dz
            
            # Compute the thermal resistances (K/W) through the wall and insulation:
            R_wall = np.log((self.Dint+self.wst)/(self.Dint)) / (np.pi*self.HT*self.kst)
            R_ins  = np.log((self.Dint+self.wst+self.wins)/(self.Dint+self.wst)) / (np.pi*self.HT*self.kins)
            h_conv = 4 #W/m2 K
            R_conv = 1/(h_conv * area)
            
            #print(R_wall, R_ins)
            R_total = R_wall + R_ins + R_conv
            
            # Calculate heat loss (W). Positive when layer temperature is above ambient.
            Q_loss = (T - T_amb) / R_total
            
            # Compute temperature change dT (°C) for the time step dt
            dT = (Q_loss * dt) / effective_capacity

            
            new_T_profile[i] = T - dT
            
        return new_T_profile

    
    def set_state(self, new_state):
        """
        Sets the operational state of the TES and switches the inlet and outlet if changing from charge to discharge and vice versa.
        :param new_state: str, the new state of the TES ('charge', 'discharge', 'standby').
        """
        
        if new_state != self.state and (new_state in ['charge', 'discharge']):
            # Switch inlet and outlet when changing between charge and discharge
            self.inlet, self.outlet = self.outlet, self.inlet
            self.profile = np.flip(self.profile)
        self.state = new_state

    def calculate_SoC(self, profile):
        """
        Calculate the energy stored in a TES unit by integrating the temperature profile.
        
        :param tes_temps: List of temperatures from each TES unit
        :return: List of energy stored in each TES unit
        """

        self.air_params()
        
        radius = self.Dint / 2
        volume = np.pi * (radius ** 2) * self.HT

        Cp_pb = self.cp_s * self.e + self.cp_f * (1-self.e)# (kJ/kg°C)
        rho_pb = self.rho_s * self.e + self.rho_out * (1-self.e)  #  (kg/m³)
        
        SoC = 0
        for temp in profile:
            energy = volume * rho_pb * Cp_pb  * temp / len(profile)
            SoC += energy #J
        return SoC/3.6e6 #kWh
         
class SolarThermalSystem:
    """
    The SolarThermalSystem class encapsulates a steady-state TESPy network with:
      - A Pump (for circulating CO2 at high pressure)
      - A ParabolicTrough collector (using TESPy's built-in class)
      - A simple HeatExchanger for process demand

    It is designed for parametric/time-step analyses in which you can vary
    the DNI (irradiance) at each solve. 
    """

    def __init__(self, rows=1, modules=1, 
                 tes_params=None, 
                 component_params = None, 
                 conexion_params=None,
                 HTF=None):
        """
        Constructor initializes placeholders for the network, components, 
        and connections. Actual creation of these will occur in other methods.
        """
        self.HTF = HTF
        self.rows = rows
        self.modules = modules
        
        self.tes_params = tes_params
        self.TES_dt = 3600
        
        self.component_params = component_params 
        self.conexion_params = conexion_params
        self.network = None
        self.pump = None
        self.ptc_field = None
        self.process_hx = None
        self.cycle_closer = None
        self.discharge_hx = None 

        self.conn_pump_to_ptc = None
        self.conn_ptc_to_hx = None
        self.conn_hx_to_cc = None
        self.conn_cc_to_pump = None
        self.conn_pump_to_dhx = None
        self.conn_dhx_to_ph = None

        self.results = {}
        self.tes = ThermalEnergyStorage(self.tes_params, name='TES', dt=self.TES_dt)
        
        self.ptc_field_A = self.component_params['ptc_A']
        
        
    def create_network1(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 600],
                              #m_range=[0, 50]
                              )

        # 3) Create and add components
        self.pump = tpc.Pump(label='pump_main')
        self.pump2 = tpc.Pump(label='pump_second')
        self.comp = tpc.Compressor(label='Compressor')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        #self.cycle_closer2 = tpc.CycleCloser(label='CycleCloser2')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')

        # TES layout
        self.charge_tes_hx = tpc.HeatExchanger(label='Charge_TES_HX')
        
        self.splitter1 = tpc.nodes.splitter.Splitter(label='Splitter1')
        self.merge2 = tpc.nodes.merge.Merge(label='Merge2')
        
        #TES
        self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
        self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        
        # Main Loop
        self.conn_1 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.ptc_field, 'in1',
            label='1_CC_PTC'
            )
        
        self.conn_2 = tpcn.Connection(
            self.ptc_field, 'out1',
            self.splitter1, 'in1',
            label='2_PTC_SP1'
            )
        
        self.conn_4 = tpcn.Connection(
            self.splitter1, 'out1',
            self.preheater_hx, 'in1',
            label='4_SP1_PH'
            )
        
        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='5_PH_PR'
            )
        
        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.pump, 'in1',
            label='6_PR_CP'
            )
        
        self.conn_7 = tpcn.Connection(
            self.pump, 'out1',
            self.merge2, 'in1',
            label='7_CP_MG2'
            )
        
        self.conn_9 = tpcn.Connection(
            self.merge2, 'out1',
            self.cycle_closer, 'in1',
            label='9_MG2_CC'
            )
        
        # Branch 1 (Charge path)
        self.conn_10 = tpcn.Connection(
            self.splitter1, 'out2',
            self.pump2, 'in1',
            label='10_SP1_CP2'
            )

        self.conn_20 = tpcn.Connection(
            self.pump2, 'out1',
            self.charge_tes_hx, 'in1',
            label='20_CP2_CHX'
            )
        
        # self.conn_20 = tpcn.Connection(
        #     self.pump2, 'out1',
        #     self.cycle_closer2, 'in1',
        #     label='20_CP2_CC2'
        #     )
        # self.conn_21 = tpcn.Connection(
        #     self.cycle_closer2, 'out1',
        #     self.charge_tes_hx, 'in1',
        #     label='21_CC2_CHX'
        #     )
        
        self.conn_11 = tpcn.Connection(
            self.charge_tes_hx, 'out1',
            self.merge2, 'in2',
            label='11_CHX_MG2'
            )
        #TES
        self.conn_14 = tpcn.Connection(
            self.tes_ch_source, 'out1',
            self.comp, 'in1',
            label='14_CHSC_CM'
            )

        self.conn_15 = tpcn.Connection(
            self.comp, 'out1',
            self.charge_tes_hx, 'in2',
            label='15_CM_CHX'
            )
        
        self.conn_16   = tpcn.Connection(
            self.charge_tes_hx, 'out2',
            self.tes_ch_sink, 'in1',       
            label='16_CHX_CHSK'
            )
        
        self.network.add_conns(
            self.conn_1,
            self.conn_2,
            self.conn_4,
            self.conn_5,
            self.conn_6,
            self.conn_7,
            self.conn_9,
            self.conn_10,
            self.conn_20,
            #self.conn_21,
            self.conn_11,
            self.conn_14,
            self.conn_15,
            self.conn_16,
           )
        
        self.conn_1.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_2.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_4.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_5.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_6.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_7.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_9.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_10.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_11.set_attr(T0=500, h0=700, m0=5, p0=50)
        self.conn_14.set_attr(T0=500, m0=1, p0=50)
        self.conn_15.set_attr(T0=500, m0=1, p0=50)
        self.conn_16.set_attr(T0=500, m0=1, p0=50)
        self.conn_20.set_attr(T0=500, m0=5, p0=50)
        #self.conn_21.set_attr(T0=500, m0=5)
    
        self.pump.set_attr(eta_s=self.component_params['pump_eta_s'],
                              #design=['eta_s'], offdesign=['eta_s_char']
                              )
        
        self.pump2.set_attr(eta_s=self.component_params['pump_eta_s'],
                              #design=['eta_s'], offdesign=['eta_s_char']
                              )
        
        self.comp.set_attr(eta_s=self.component_params['comp_eta_s'],
                              #design=['eta_s'], offdesign=['eta_s_char']
                              )

        #    Set collector parameters pero row (area, pr, DNI, design, etc.)
        self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
                                aoi=self.component_params['ptc_aoi'], 
                                doc=self.component_params['ptc_doc'],
                                Tamb=self.component_params['ptc_tamb'], 
                                A=self.component_params['ptc_A'], 
                                eta_opt=self.component_params['eta_opt'], 
                                c_1=self.component_params['ptc_c_1'], 
                                c_2=self.component_params['ptc_c_2'], 
                                E=self.component_params['ptc_E'],
                                iam_1=self.component_params['ptc_iam_1'], 
                                iam_2=self.component_params['ptc_iam_2'])


        # Outflow of process HX
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             T0=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'],
                             )
        
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # TES HTF
        self.conn_14.set_attr(p=self.conexion_params['14_p'], 
                              fluid=self.conexion_params['14_f'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        
        self.conn_5.set_attr(T=self.conexion_params['5_T'])
        
        #
        self.charge_tes_hx.set_attr(pr1=0.99,pr2=0.99,
                                   #pr2=1,
                                   #ttd_min=10, 
                                   #eff_max=0.95,
                                   #eff_cold=0.9,
                                   #eff_hot=0.95,
                                   #design=['ttd_min'], 
                                   #design=['eff_max'],
                                   #design=['eff_cold','eff_hot'],
                                   #offdesign=['kA_char','eff_max']
                                   #offdesign=['eff_max']
                                   offdesign=['eff_cold','eff_hot'],
                                   )
                            
        #self.comp.set_attr(pr=1.1)

    def create_network2(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        #self.network.set_attr(T_range=[300, 600])

        # 3) Create and add components
        self.pump = tpc.Pump(label='Pump_main')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')
        
        # Main Loop
        self.conn_1 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.ptc_field, 'in1',
            label='CC_PTC'
            )
        
        self.conn_2 = tpcn.Connection(
            self.ptc_field, 'out1',
            self.preheater_hx, 'in1',
            label='PTC_PH'
            )

        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='PH_PR'
            )
        
        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.pump, 'in1',
            label='PR_CP'
            )
        
        self.conn_7 = tpcn.Connection(
            self.pump, 'out1',
            self.cycle_closer, 'in1',
            label='CP_CC'
            )

        self.network.add_conns(
            self.conn_1,
            self.conn_2,

            self.conn_5,
            self.conn_6,
            self.conn_7,
           )
        
        self.conn_1.set_attr(T0=500, h0=700)
        self.conn_2.set_attr(T0=500, h0=700)
        self.conn_5.set_attr(T0=500, h0=700)
        self.conn_6.set_attr(T0=500, h0=700)
        self.conn_7.set_attr(T0=500, h0=700)
        
        self.pump.set_attr(eta_s=self.component_params['pump_eta_s'])

        #    Set collector parameters pero row (area, pr, DNI, design, etc.)
        self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
                                aoi=self.component_params['ptc_aoi'], 
                                doc=self.component_params['ptc_doc'],
                                Tamb=self.component_params['ptc_tamb'], 
                                A=self.component_params['ptc_A'], 
                                eta_opt=self.component_params['eta_opt'], 
                                c_1=self.component_params['ptc_c_1'], 
                                c_2=self.component_params['ptc_c_2'], 
                                E=self.component_params['ptc_E'],
                                iam_1=self.component_params['ptc_iam_1'], 
                                iam_2=self.component_params['ptc_iam_2'])


        # Outflow of process HX
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_5.set_attr(T=self.conexion_params['5_T'])

    def create_network3(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """
        
        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 600],
                              #m_range=[0, 50]
                              )

        # 3) Create and add components
        self.pump = tpc.Pump(label='Pump_main')
        self.comp = tpc.Compressor(label='Compressor')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
    
        # TES layout
        self.discharge_tes_hx = tpc.HeatExchanger(label='Discharge_TES_HX')
        
        #TES
        self.tes_dch_source = tpc.Source('TES_discharge_inlet_source')
        self.tes_dch_sink   = tpc.Sink('TES_discharge_outlet_sink')
        
        # Main Loop
        self.conn_4 = tpcn.Connection(
            self.discharge_tes_hx, 'out2',
            self.preheater_hx, 'in1',
            label='4_DHX_PH'
            )
        
        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='5_PH_PR'
            )
        
        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.pump, 'in1',
            label='6_PR_CP'
            )

        self.conn_7 = tpcn.Connection(
            self.pump, 'out1',
            self.cycle_closer, 'in1',
            label='7_CP_CC'
            )

        self.conn_12 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.discharge_tes_hx, 'in2',
            label='12_CC_DHX'
            )
        
        #TES        

        self.conn_17= tpcn.Connection(
            self.tes_dch_source, 'out1',       
            self.discharge_tes_hx, 'in1',       
            label='17_DCHSC_DHX'
            )
        
        self.conn_18  = tpcn.Connection(
            self.discharge_tes_hx, 'out1',
            self.comp, 'in1',
            label='18_DHX_CM'
            )
        
        self.conn_19 = tpcn.Connection(
            self.comp, 'out1',
            self.tes_dch_sink, 'in1',
            label='19_CM_DCHSK'
            )
        

        self.network.add_conns(
            self.conn_4,    
            self.conn_5,
            self.conn_6,
            self.conn_7,
            self.conn_12,
            self.conn_17,
            self.conn_18,
            self.conn_19,
           )
        
        self.conn_4.set_attr(T0=500, m0=1)
        self.conn_5.set_attr(T0=500, m0=1)
        self.conn_6.set_attr(T0=500, m0=1)
        self.conn_7.set_attr(T0=500, m0=1)
        self.conn_12.set_attr(T0=500, m0=1)
        self.conn_17.set_attr(T0=500, m0=1)
        self.conn_18.set_attr(T0=500, m0=1)
        self.conn_19.set_attr(T0=500, m0=1)
        

        self.pump.set_attr(eta_s=self.component_params['pump_eta_s'],
                              #design=['eta_s'], offdesign=['eta_s_char']
                              )
        
        self.comp.set_attr(eta_s=self.component_params['comp_eta_s'],
                              #design=['eta_s'], offdesign=['eta_s_char']
                              )

        # Outflow of process HX
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # TES HTF
        self.conn_17.set_attr(p=self.conexion_params['17_p'], 
                              fluid=self.conexion_params['17_f'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_5.set_attr(T=self.conexion_params['5_T'])
        
        self.discharge_tes_hx.set_attr(pr1=0.99, pr2=0.99,# ttd_min=20,
                                    #design=['pr1','pr2','ttd_min'], offdesign=['zeta1','zeta2','kA']
                                    offdesign=['kA']
                                    )
        
    def create_network4(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 600],
                              #m_range=[0, 50]
                              )

        # 3) Create and add components
        self.pump = tpc.Pump(label='Pump_main')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
    

        # Main Loop
        self.conn_4 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.preheater_hx, 'in1',
            label='4_CC_PH'
            )
        
        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='5_PH_PR'
            )
        
        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.pump, 'in1',
            label='6_PR_CP'
            )

        self.conn_7 = tpcn.Connection(
            self.pump, 'out1',
            self.cycle_closer, 'in1',
            label='7_CP_CC'
            )


        self.network.add_conns(
            self.conn_4,    
            self.conn_5,
            self.conn_6,
            self.conn_7,
           )
        
        self.conn_4.set_attr(T0=500, m0=1)
        self.conn_5.set_attr(T0=500, m0=1)
        self.conn_6.set_attr(T0=500)
        self.conn_7.set_attr(T0=500)
        

        self.pump.set_attr(eta_s=self.component_params['pump_eta_s'],
                              design=['eta_s'], offdesign=['eta_s_char'])

        # Outflow of process HX
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_5.set_attr(T=self.conexion_params['5_T'])

    def create_network5(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """
        
        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')

        # 3) Create and add components
        self.pump2 = tpc.Pump(label='Pump_main')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        
        #TES
        self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
        self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        
        # Main Loop

        self.conn_5 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.preheater_hx, 'in1',
            label='DHX_PH'
            )
        
        self.conn_6 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='PH_PR'
            )
        
        self.conn_7 = tpcn.Connection(
            self.process_hx, 'out1',
            self.pump2, 'in1',
            label='PR_CP'
            )

        self.conn_12 = tpcn.Connection(
            self.pump2, 'out1',
            self.cycle_closer, 'in1',
            label='CP_CC'
            )
        
        #TES
        self.conn_18 = tpcn.Connection(
            self.tes_ch_source, 'out1',
            self.tes_ch_sink, 'in1',
            label='CHSC_CHSK'
            )

        self.network.add_conns(
            self.conn_5,
            self.conn_6,
            self.conn_7,
            self.conn_12,
            self.conn_18,
           )

        self.pump2.set_attr(eta_s=self.component_params['pump_eta_s'])

        # Outflow of process HX
        self.conn_7.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])


        # Preheater HX        
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_6.set_attr(T=self.conexion_params['6_T'])
        
        # TES HTF
        self.conn_18.set_attr(p=self.conexion_params['17_p'], 
                              fluid=self.conexion_params['17_f'])
    def create_network6(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(m_range=[0, 100])
        #self.network.set_attr(p_range=[9, 100])

        # 3) Create and add components
        self.pump = tpc.Pump(label='Pump_main')
        self.pump2 = tpc.Pump(label='Pump_Dch_loop')
        self.comp = tpc.Compressor(label='Compressor')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        self.cycle_closer2 = tpc.CycleCloser(label='CycleCloser2')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')

        # TES layout
        self.charge_tes_hx = tpc.HeatExchanger(label='Charge_TES_HX')
        
        #TES
        self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
        self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        
        # Main Loop
        self.conn_1 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.ptc_field, 'in1',
            label='1_CP_PTC'
            )
        
        self.conn_2 = tpcn.Connection(
            self.ptc_field, 'out1',
            self.pump2, 'in1',
            label='2_PTC_CP2'
            )
        
        self.conn_20 = tpcn.Connection(
            self.pump2, 'out1',
            self.charge_tes_hx, 'in1',
            label='20_CP2_CHX'
            )
        
        self.conn_11 = tpcn.Connection(
            self.charge_tes_hx, 'out1',
            self.cycle_closer, 'in1',
            label='11_CHX_CC'
            )
        
        # Process Loop
        self.conn_4 = tpcn.Connection(
            self.cycle_closer2, 'out1',
            self.preheater_hx, 'in1',
            label='4_CC2_PH'
            )
        
        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='5_PH_PR'
            )

        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.pump, 'in1',
            label='6_PR_CP'
            )
        
        self.conn_7 = tpcn.Connection(
            self.pump, 'out1',
            self.cycle_closer2, 'in1',
            label='4_CP_CC2'
            )
        
        #TES
        self.conn_14 = tpcn.Connection(
            self.tes_ch_source, 'out1',
            self.comp, 'in1',
            label='14_CHSC_CM'
            )

        self.conn_15 = tpcn.Connection(
            self.comp, 'out1',
            self.charge_tes_hx, 'in2',
            label='15_CM_CHX'
            )
        
        self.conn_16   = tpcn.Connection(
            self.charge_tes_hx, 'out2',
            self.tes_ch_sink, 'in1',       
            label='16_CHX_CHSK'
            )
        
        self.network.add_conns(
            self.conn_1,
            self.conn_2,
            self.conn_20,
            self.conn_11,
            self.conn_4,
            self.conn_5,
            self.conn_6,
            self.conn_7,
            self.conn_14,
            self.conn_15,
            self.conn_16,
           )
    
        self.conn_1.set_attr(T0=500, h0=700, m0=2)
        self.conn_2.set_attr(T0=500, h0=700, m0=2)
        self.conn_20.set_attr(T0=500, h0=700, m0=2)
        self.conn_11.set_attr(T0=500, h0=700, m0=2)
        self.conn_4.set_attr(T0=500, h0=700, m0=2)
        self.conn_5.set_attr(T0=500, h0=700, m0=2)
        self.conn_6.set_attr(T0=500, h0=700, m0=2)
        self.conn_7.set_attr(T0=500, h0=700, m0=2)
        self.conn_14.set_attr(T0=500, m0=2)
        self.conn_15.set_attr(T0=500, m0=2)
        self.conn_16.set_attr(T0=500, m0=2)
        
        self.pump.set_attr(eta_s=self.component_params['pump_eta_s'],
                              #design=['eta_s'], offdesign=['eta_s_char']
                              )
        
        self.pump2.set_attr(eta_s=self.component_params['pump_eta_s'],
                              #design=['eta_s'], offdesign=['eta_s_char']
                              )
        
        self.comp.set_attr(eta_s=self.component_params['comp_eta_s'],
                              #design=['eta_s'], offdesign=['eta_s_char']
                              )

        #    Set collector parameters pero row (area, pr, DNI, design, etc.)
        self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
                                aoi=self.component_params['ptc_aoi'], 
                                doc=self.component_params['ptc_doc'],
                                Tamb=self.component_params['ptc_tamb'], 
                                A=self.component_params['ptc_A'], 
                                eta_opt=self.component_params['eta_opt'], 
                                c_1=self.component_params['ptc_c_1'], 
                                c_2=self.component_params['ptc_c_2'], 
                                E=self.component_params['ptc_E'],
                                iam_1=self.component_params['ptc_iam_1'], 
                                iam_2=self.component_params['ptc_iam_2'])


        # Outflow of process HX
        
        self.conn_5.set_attr(T=self.conexion_params['5_T'],
                             )
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'],
                             fluid=self.conexion_params['6_f']
                             )
        
        self.conn_2.set_attr(p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f']
                             )

        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # TES HTF
        self.conn_14.set_attr(p=self.conexion_params['14_p'], 
                              fluid=self.conexion_params['14_f']
                              )

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        
        self.charge_tes_hx.set_attr(pr1=0.99, pr2=0.99, kA=2.97e+03,
                                    #design=['pr1','pr2','ttd_min'], offdesign=['zeta1','zeta2','kA']
                                    #offdesign=['kA']
                                    )
        
    def set_operation_mode(self, TESmode='4', 
                           current_irr=0,
                           profile=None,
                           prev_TES_lay = 'Charge',
                           mode = 'design'):
        """
        mode 1: High irradiation, PTC to process and to TES
        mode 2: Mid irradiation, PTC to process, TES in standby
        mode 3: Low irradiation, TES to process
        mode 4: Low irradiation, TES in standby
        mode 5: Low irradiation, TES re-stratification
        mode 6: Mid to high irradiation, PTC full to TES
        """
        if prev_TES_lay == 'Charge':
            TES_top = profile[0]
            TES_bot = profile[-1]
        elif prev_TES_lay == 'Discharge':
            TES_top = profile[-1]
            TES_bot = profile[0]

        if TESmode == '1':
            self.create_network1()
            self.tes.set_state('charge')

            TES_target = self.conexion_params['6_T']
 
            self.conn_11.set_attr(T=TES_target)#, m=tpcn.Ref(self.conn_4, 0.3, 0))
            #self.conn_10.set_attr(p=tpcn.Ref(self.conn_4, 1.0, 0.0))
            self.conn_16.set_attr(T=TES_bot+40, p=tpcn.Ref(self.conn_14, 1.01, 0.0))

            if mode == 'offdesign':
                #pass
                self.conn_11.set_attr(T=None)#, m=tpcn.Ref(self.conn_4, 0.5, 0))
                #self.conn_10.set_attr(p=tpcn.Ref(self.conn_4, 1.0, 1.0))
                self.conn_16.set_attr(T=None)
                #self.conn_11.set_attr(T=tpcn.Ref(self.conn_7, 1.0, 0.0)) 
 
            self.preheater_hx.set_attr(Q=0)
        elif TESmode == '2':
            # All flow from PTC to process
            self.create_network2()
            #self.preheater_hx.set_attr(Q=0)
            if current_irr > 500:
                self.ptc_field.set_attr(A='var')
                self.preheater_hx.set_attr(Q=0)
                
        elif TESmode == '3':
            # All flow from TES, none in PTC and charge loop
            self.create_network3()
            self.tes.set_state('discharge')
            #if TES_top > self.conexion_params['7_T']: 
            TES_target = TES_top - 10 
            TES_toutlet = TES_top - 35 
            #print(TES_toutlet)
                #print('o1')
            #else: 
            #    TES_target = self.conexion_params['7_T']
            #    TES_toutlet = self.conexion_params['7_T'] + 10
                #print('o2')
            #print(self.conn_17.get_attr('T').val)
            self.conn_17.set_attr(p=tpcn.Ref(self.conn_19, 1.01, 0))
            #self.conn_5.set_attr(T=TES_target, m=None)
            #self.discharge_tes_hx.set_attr(Q=None, pr1=0.99, pr2=0.99)
            #self.conn_18.set_attr(m=tpcn.Ref(self.conn_5, 1, 0))
            #print('T TES outlet', TES_toutlet)
            self.conn_18.set_attr(T=TES_toutlet)
            self.conn_4.set_attr(T=TES_target)
            if mode == 'offdesign':
                #pass
                self.conn_4.set_attr(T=None)

        elif TESmode == '4':
            self.create_network4()
            #self.tes.set_state('discharge')
            
        elif TESmode == '5':
            self.create_network5()
            self.conn_18.set_attr(m=tpcn.Ref(self.conn_5, 2, 0))
            #self.conn_18.set_attr(m=1)
            
            self.tes.set_state('discharge')
            
        elif TESmode == '6':
            self.create_network6()
            self.tes.set_state('charge')
            TES_target = self.conexion_params['6_T']
 
            self.conn_2.set_attr(T=530)
            self.conn_16.set_attr(T=TES_bot+30, p=tpcn.Ref(self.conn_14, 1.01, 0))

        else:   
            raise ValueError(f"Unknown mode {TESmode}")

            
    def solve_network(self, mode='design', design_path="base_design", TESmode='1'):
        """
        Attempts to solve the network in the specified mode (default: 'design').
        Raises an exception if the solver fails.
        
        Args:
            mode (str): 'design' or 'offdesign' (TESPy modes).
        """

        name = f'base_design_{TESmode}'        
        if mode == 'design':
            #self.network.check_network()
            # self.conn_4.set_attr(T=500)
            # self.conn_5.set_attr(T=500)
            # self.conn_6.set_attr(T=500)
            # self.conn_7.set_attr(T=500)
            # self.conn_12.set_attr(T=500)
            # self.conn_17.set_attr(T=500)
            # self.conn_18.set_attr(T=500)
            # self.conn_19.set_attr(T=500)
            # print(self.conn_4.get_attr('T').val)
            # print(self.conn_5.get_attr('T').val)
            # print(self.conn_6.get_attr('T').val)
            # print(self.conn_7.get_attr('T').val)
            # print(self.conn_12.get_attr('T').val)
            # print(self.conn_17.get_attr('T').val)
            # print(self.conn_18.get_attr('T').val)
            # print(self.conn_19.get_attr('T').val)
            
            # print(">>> Checking every network.conns before solve():")
            # for i, conn in enumerate(self.network.conns.object):
            #     print(conn.label)
            #     conn2 = self.network.get_conn(conn.label)
            #     print(conn2.get_attr('T').val)
            #     conn2.set_attr(T=500)
            #     print(conn2.get_attr('T').val)

            self.network.solve(mode=mode)
            self.network.save(name)
        else:
            self.network.solve(mode=mode, design_path = f'base_design_{TESmode}')
            #if not self.network.converged:
            #    raise RuntimeError("TESPy solver did not converge.")

class Solver:
    """
    Runs a quasi-steady simulation of the SolarThermalSystem over time-series data.
    """
    def __init__(self, 
                 tes_params,
                 component_params,
                 conexion_params,
                 HTF,
                 system_mode='Full', 
                 file_path=None):
        self.tes_params= tes_params
        self.component_params = component_params
        self.conexion_params = conexion_params
        self.HTF= HTF 
        self.system_mode = system_mode
        self.results = []
        self.current_mode = '4' 
        self.file_path = file_path
        self.mode_alert = False

    def load_data(self, csv, start_date, days_to_simulate):
        """
        Loads external data from a CSV file and fixes the year for all timestamps.
        :return: DataFrame, data loaded and adjusted.
        """
        fixed_year = 2022        

        # 2) Read TMY
        tmy_data = pd.read_csv('TMY.csv')#, parse_dates=['Fecha/Hora'])
        
        # Fix the year for all timestamps
        tmy_data['Fecha/Hora'] = pd.to_datetime(tmy_data['Fecha/Hora'])
        tmy_data['Fecha/Hora'] = tmy_data['Fecha/Hora'].apply(lambda x: x.replace(year=fixed_year))
        start_date = tmy_data['Fecha/Hora'].min()
        end_date   = start_date + pd.Timedelta(days=days_to_simulate)
        print(start_date, end_date)
       
        #filtered_data = filtered_data[filtered_data['Fecha/Hora'] >= start_date]
        filtered_data = tmy_data[(tmy_data['Fecha/Hora'] >= start_date) & (tmy_data['Fecha/Hora'] < end_date)]
        return filtered_data

    #def gen_latex(self, path='report', filename='report.tex'):
    #    ttdm.document_model(self.solar_system.network)

    def get_mode(self, irr, TES_profile, prev_TES_lay):
        
        if prev_TES_lay == 'Charge':
            TES_top = TES_profile[0]
            TES_bot = TES_profile[-1]
        elif prev_TES_lay == 'Discharge':
            TES_top = TES_profile[-1]
            TES_bot = TES_profile[0]
            
        #if self.prev_TESmode == '6' and 460 > TES_top and irr > 600:
        if self.prev_TESmode == '6' and 400 > TES_bot and irr > 600:
            return '6'
        
        elif self.prev_TESmode == '5' and 400 > TES_bot and irr < 600:
            return '5'

        if 370 > TES_bot:
            #print(np.average(TES_profile))
            if irr > 600:
                return '6'
            else:
                return '5'
        if irr > 750:
            if self.solar_system.conexion_params['6_T'] > TES_bot - 20:
                if np.average(TES_profile) > 500:
                    return '2'
                else:
                    return '1'
            else: 
                return '2'
        elif irr > 300:
            return '2'
            
        else:
            if TES_top - 10 > self.solar_system.conexion_params['6_T']-40:
                return '3'
                # if TES_top > TES_profile[10] or TES_top > TES_profile[5] or TES_top > TES_profile[15]:
                #     return '4'#'5'
                # else:
                #     return '4'
            else:
                return '4'

    def get_system_mode(self, irr):
        if self.system_mode == 'Full':
            new_TESmode = self.get_mode(irr, self.solar_system.tes.profile, self.TES_lay)
            self.prev_TESmode = new_TESmode
        elif self.system_mode == 'No TES':
            if irr > 300:
                new_TESmode = '2'
            else:
                new_TESmode = '4'
        elif self.system_mode == 'No solar':
            new_TESmode = '4'
        return new_TESmode
    def init_steady(self, irr, mode='design'):
        self.system_mode == 'Full'
        self.TES_lay = 'Charge'
        self.irr = irr
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        print(f"Mode: {mode}")
        self.solve_network_steady(mode=mode)
        self.solar_system.network.print_results()
        
    def initialize_modes(self):
        # Mode 1
        self.system_mode == 'Full'
        self.TES_lay = 'Charge'
        self.irr = 1000
        self.tes_params['Initial temperature'] = 420
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        # Mode 2
        self.irr = 1000
        self.tes_params['Initial temperature'] = 520
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        # Mode 3
        self.irr = 0
        self.tes_params['Initial temperature'] = 520
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        # Mode 4
        self.irr = 0
        self.tes_params['Initial temperature'] = 420
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        
        # # Mode 5
        # self.irr = 0
        # self.tes_params['Initial temperature'] = 330
        # self.solar_system = SolarThermalSystem(rows=1, 
        #                             tes_params=self.tes_params,
        #                             component_params = self.component_params,
        #                             conexion_params = self.conexion_params,
        #                             HTF=self.HTF 
        #                             )
        # self.solve_network_steady()

        # Mode 6
        self.irr = 1000
        self.tes_params['Initial temperature'] = 330
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        
        # 
    # -------------------------------------------------------------------------
    # 1) Convergence Checking
    # -------------------------------------------------------------------------
    def _check_tes_convergence(self, T_out_history, conv_factors):
        """
        Checks for two criteria:
          1) Convergence if last 3 changes in T_out are < 5%.
          2) Divergence if the convergence factor has increased >10% 
             over the last 5 iterations.

        Returns
        -------
        str:
            'converged', 'diverged', or 'continue'
        """
        # (1) If we have at least 3 T_out values, check for <5% changes
        if len(T_out_history) >= 3:
            Tn   = T_out_history[-1]
            Tn_1 = T_out_history[-2]
            Tn_2 = T_out_history[-3]

            diff1 = abs(Tn   - Tn_1) / max(abs(Tn_1), 1e-6)
            diff2 = abs(Tn_1 - Tn_2) / max(abs(Tn_2), 1e-6)
            if diff1 < 0.05 and diff2 < 0.05:
                return 'converged'

        # (2) If we have at least 5 convergence factors, check for divergence
        if len(conv_factors) >= 5:
            earliest = conv_factors[-5]
            latest   = conv_factors[-1]
            if earliest > 0 and (latest - earliest)/earliest > 1:
                return 'diverged'

        return 'continue'
    
    def iteration_check(self, TESmode, system):
        if TESmode == '1':
            T_tes_out = system.conn_14.T.val
            if T_tes_out > self.conexion_params['5_T']:
                check = False
                mode = '2'
                #print('T TES out: ', T_tes_out)
            else:
                check = True
                mode = '1'
        elif TESmode == '3':   
            T_tes_out = system.conn_17.T.val
            if T_tes_out < self.conexion_params['6_T'] + 10:
                check = False
                mode = '4'
            else:
                check = True
                mode = '3'
        else:
            check = True
            mode = TESmode
        return check, mode
    # -------------------------------------------------------------------------
    # 2) Coupling Iteration Between TES and Main Loop (steady or single time-step)
    # -------------------------------------------------------------------------
    def _iterate_tes_coupling(self, system,
                              mode='design', TESmode='2', 
                              design_path='base_design',
                              Tamb=25):
        """
        Performs the inner iteration between the TES 1D model and
        the TESPy network for one 'steady' scenario (or one time-step).

        - Sets initial guess for TES-HX side from the top/bottom of the TES 
          depending on 'charge' or 'discharge'.
        - Iterates until we pass the convergence or divergence check, 
          or until hitting max_iter.
        """

        max_iter = 20
        T_out_history = []
        conv_factors  = []
        self.TES_profiles = []
        # 2) Initialize the TES_HX source temperature from top/bottom
        if TESmode in ['1', '6']:
            T_in_bot = system.tes.profile[-1]  # top node for charging
            system.conn_14.set_attr(T=T_in_bot)
        elif TESmode in ['3','5']: # discharging: use bottom node to extract heat from the hottest (bottom) region
            T_in_top = system.tes.profile[-1]
            system.conn_17.set_attr(T=T_in_top)
        
        #system.tes.t_min = Tamb
        #system.tes.t_max = 600
        
        old_profile = system.tes.profile
        # 3) Iteration loop
        for iteration in range(max_iter):
            # a) Solve the main TESPy network
            print('Mode: ', mode)
            if mode == 'offdesign':
                #system.network.set_attr(iterinfo=False)
                print(f'TES mode: {TESmode}')
                
            # try:
            #     m20_prev = np.abs(self.conn_20.get_attr.m.val)  # network units
            #     print('mprev20 ',m20_prev)
            #     if m20_prev is not None and m20_prev > 0.0:
            #         self.conn_20.set_attr(m0=m20_prev)  # starting guess only
            # except Exception:
            #     pass
            system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode)
            system.network.print_results()
            if not system.network.converged:
                if TESmode in ['1','6']:
                    print('System did not converge\n',TESmode, ' passing to 2')
                    TESmode = '2'
                    self.current_mode = TESmode
                    system.set_operation_mode(TESmode=TESmode, 
                                              current_irr=self.current_irr,
                                              profile=system.tes.profile,
                                              prev_TES_lay = self.TES_lay)
                    system.network.set_attr(iterinfo=False)
                    system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode)
                    system.network.print_results()
                elif TESmode in ['3','5']:
                    print('System did not converge\n',TESmode, 'passing to 4')
                    TESmode = '4'
                    self.current_mode = TESmode
                    system.set_operation_mode(TESmode=TESmode, 
                                              current_irr=self.current_irr,
                                              profile=system.tes.profile,
                                              prev_TES_lay = self.TES_lay)
                    system.network.set_attr(iterinfo=False)
                    system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode)
                    system.network.print_results()
                else:
                    print(f"[WARNING] TESPy solver did not converge at iteration {iteration+1}.")
                    break
            if TESmode in ['2', '4']:
                status = 'converged'
                profile = system.tes.profile
                old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                system.tes.profile = old_profile
                self.TES_profiles.append(old_profile)

                break
            # b) Read new TES inlet conditions from TES_HX outlet
            if TESmode in ['1', '6']:
                T_tes_in = system.conn_16.T.val
                m_tes_in = system.conn_16.m.val_SI
            elif TESmode in ['5']:
                T_tes_in = T_in_top
                m_tes_in = -system.conn_18.m.val_SI
            elif TESmode == '3':  # discharging: use bottom node to extract heat from the hottest (bottom) region
                T_tes_in = system.conn_19.T.val
                m_tes_in = system.conn_19.m.val_SI
                
            if m_tes_in < 0.01:
                self.mode_alert == True
                profile = system.tes.profile
                old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                system.tes.profile = old_profile
                self.TES_profiles.append(old_profile)
                break

            system.tes.update_temperature_profile(
                T_in=T_tes_in,
                mass_flow=m_tes_in,
                initial_profile=old_profile
            )
            T_tes_out = system.tes.tout
            #print(f'T_tes_out: {T_tes_out}')
            
            

            # d) Set the new outlet temperature to the HX inlet for next iteration
            if TESmode in ['1', '6']:
                system.conn_14.set_attr(T=T_tes_out)
                self.TES_lay = 'Charge'
            elif TESmode in ['3','5']:
                system.conn_17.set_attr(T=T_tes_out)
                self.TES_lay = 'Discharge'

            # e) Track T_out for our multi-step convergence logic
            T_out_history.append(T_tes_out)
            if len(T_out_history) > 1:
                prev_T = T_out_history[-2]
                if abs(prev_T) > 1e-6:
                    cf = abs(T_tes_out - prev_T) / abs(prev_T)
                else:
                    cf = 0.0
                conv_factors.append(cf)

            # f) Evaluate our custom convergence criteria
            status = self._check_tes_convergence(T_out_history, conv_factors)
            #status = 'converged'
            if mode == 'design':
                print(f'outlet TES temperature: {T_tes_out}')   
            if status == 'converged':
                check, checkmode = self.iteration_check(TESmode, system)
                if not check:                
                    TESmode = checkmode
                    self.current_mode = TESmode
                    print('Iteration check failed, new mode: ', checkmode)
                    system.set_operation_mode(TESmode=TESmode, 
                                              current_irr=self.current_irr,
                                              profile=system.tes.profile,
                                              prev_TES_lay = self.TES_lay)
                    system.network.set_attr(iterinfo=False)
                    system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode)
                    if not system.network.converged:
                        print(f"[WARNING] TESPy solver did not converge at iteration {iteration+1}.")
                        break
                profile = system.tes.profile
                old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                #old_profile = profile
                system.tes.profile = old_profile
                self.TES_profiles.append(old_profile)
                break
            elif status == 'diverged':
                print(f"[WARNING] TES iteration diverging at iteration {iteration+1}!")
                break
        else:
            # If we never hit a 'break', we didn't converge within max_iter
            print("[WARNING] Reached max iteration count without TES convergence.")

    # -------------------------------------------------------------------------
    # 3) Steady-State Solver
    # -------------------------------------------------------------------------
    def solve_network_steady(self, mode='design', TESmode='2'):
        """
        Public method to solve the system in a stationary (steady) mode,
        including iteration with the TES if present.

        Args:
            operation_mode (str): 'charge' or 'discharge'.
            design_path (str): path to the saved design data (for offdesign mode).
        """
        # Simply call our coupling iteration for one single "steady" step
        system = self.solar_system
        #self.TES_lay = 'Charge'
        self.prev_TESmode = '4'
        self.current_irr = self.irr
        TESmode = self.get_mode(self.irr, system.tes.profile, self.TES_lay)
        print(f'TES mode {TESmode}')
        design_path = f'base_design_{TESmode}'
        system.set_operation_mode(TESmode=TESmode, 
                                             current_irr=self.irr, 
                                             profile=system.tes.profile,
                                             prev_TES_lay = self.TES_lay,
                                             mode=mode)

        self._iterate_tes_coupling(mode=mode, system = system,
                                   TESmode=TESmode, design_path=design_path,
                                   Tamb = 25)

    def run_quasi_steady_simulation(self, days_to_simulate = 10,
                                    csv = 'TMY.csv', time_col='Fecha/Hora',
                                    E_col='dni', Tamb_col='temp'):
        """
        Existing method: only the snippet showing how to call _iterate_tes_coupling now.
        """
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solar_system.create_network4()
        self.results = []
        
        self.TES_lay = 'Charge'
        self.prev_TESmode = '4'
        self.current_irr = 0
        data_frame = self.load_data(csv, '2022-01-01', days_to_simulate=days_to_simulate)
        # Track total runtime
        print("\n=== Starting transient simulation ===")
        start_time = time.time()

        self.solar_system.tes.t_max = 600        

        for idx, row in tqdm(data_frame.iterrows(), total=len(data_frame), desc="Simulating"):
            self.mode_alert = False
            current_irr = row[E_col]
            self.current_irr = current_irr
            current_Tamb = row[Tamb_col]
            
            # Decide TES mode
            new_TESmode = self.get_system_mode(current_irr)

            self.solar_system.set_operation_mode(TESmode=new_TESmode, 
                                                 current_irr=current_irr,
                                                 profile=self.solar_system.tes.profile,
                                                 prev_TES_lay = self.TES_lay,
                                                 mode='offdesign')
            self.current_mode = new_TESmode

            if self.current_mode in ['1','2','6']:
                self.solar_system.ptc_field.set_attr(E=current_irr, Tamb=current_Tamb)

            design_path = f'base_design_{self.current_mode}'
            
            # For each time step, do the same iteration
            self._iterate_tes_coupling(mode='offdesign', system =self.solar_system,
                                       TESmode=self.current_mode, design_path=design_path,
                                       Tamb=current_Tamb) 
            if self.mode_alert:
                self.current_mode == '4'
                self.solar_system.set_operation_mode(TESmode=new_TESmode, 
                                                     current_irr=current_irr,
                                                     profile=self.solar_system.tes.profile,
                                                     prev_TES_lay = self.TES_lay)
                self._iterate_tes_coupling(mode='offdesign', system =self.solar_system,
                                               TESmode=self.current_mode, design_path=design_path,
                                               Tamb=current_Tamb) 
            #print(new_TESmode)
            #self.solar_system.network.print_results()

            # After final iteration for this time-step:
            if self.current_mode in ['1','6']:
                Q_ptc_kJ   = self.solar_system.ptc_field.Q.val * 3600.0
                pump_power = self.solar_system.pump.P.val + self.solar_system.pump2.P.val + self.solar_system.comp.P.val
            elif self.current_mode in ['2']:
                Q_ptc_kJ   = self.solar_system.ptc_field.Q.val * 3600.0
                pump_power = self.solar_system.pump.P.val 
            elif self.current_mode in ['3']:
                Q_ptc_kJ   = 0
                pump_power = self.solar_system.pump.P.val + self.solar_system.comp.P.val
            elif self.current_mode in ['4']:
                Q_ptc_kJ   = 0
                pump_power = self.solar_system.pump.P.val 
            else:
                Q_ptc_kJ   = self.solar_system.ptc_field.Q.val * 3600.0
                pump_power = self.solar_system.pump.P.val + self.solar_system.pump2.P.val
            Q_ph_kJ = self.solar_system.preheater_hx.Q.val * 3600.0
            #if Q_ph_kJ > 0:
            #    Q_ph_kJ = self.solar_system.preheater_hx.Q.val * 3600.0
            #else:
            #    Q_ph_kJ = 0
                
            self.results.append({
                'time': row[time_col],
                'E': current_irr,
                'Tamb': current_Tamb,
                'ptc_energy_kJ': Q_ptc_kJ,
                'ph_energy_kJ':  Q_ph_kJ,
                'pump_power_W':  pump_power,
                'TES_profiles': self.TES_profiles,
                'TES_layout': self.solar_system.tes.state,
                'TESmode': self.current_mode,
            })
            
            self.prev_TESmode = self.current_mode

        # End of simulation: print total elapsed time
        end_time = time.time()
        total_runtime = end_time - start_time
        print(f"\nTransient simulation completed in {total_runtime:.2f} seconds.")

        return self.results

    def compute_performance_metrics(self):
        """
        Process self.results to compute plant factor, comp energy consumption, etc.

        Args:
            process_demand_kJ (float, optional): 
                Total heat demanded by the process (in kJ) 
                over the entire simulation horizon, if known.

        Returns:
            dict: A dictionary of computed metrics.
        """
        self.dt_hours = 1.0
        df = pd.DataFrame(self.results)
        total_ptc_energy_kJ = df['ptc_energy_kJ'].sum()
        total_ph_energy_kJ  = df['ph_energy_kJ'].sum()#.loc[df['ph_energy_kJ'] > 0].sum()
        # pump power (W) * 3600 s for each step (assuming dt=1h)
        total_pump_energy_kJ = (df['pump_power_W'] * 3600.0 * self.dt_hours).sum() / 1000
        
        # Convert kJ to MWh (1 MWh = 3.6e6 kJ)
        ptc_energy_GWh   = total_ptc_energy_kJ / 3.6e9
        ph_energy_GWh    = total_ph_energy_kJ  / 3.6e9
        pump_energy_MWh  = total_pump_energy_kJ / 3.6e6
        
        # Optional "solar plant factor" if user provided a process demand
        spf = total_ptc_energy_kJ / (total_ptc_energy_kJ + total_ph_energy_kJ + total_pump_energy_kJ*1000) # fraction

        # Print performance summary line by line
        print("\n=== Performance Summary ===")
        print(f"Total PTC Energy:       {ptc_energy_GWh:6.2f} GWh")
        print(f"Total Preheater Energy:{ph_energy_GWh:6.2f} GWh")
        print(f"Total Pump Energy:      {pump_energy_MWh:6.2f} MWh")
        if spf is not None:
            print(f"Solar Plant Factor:     {spf * 100:6.2f}%")
        print("================================\n")

        return spf
class Reporting:
    """
    A class responsible for plotting and reporting simulation results.
    """
    
    def plot_results(self, df_results):
        """
        Plots the main simulation results over time.

        Parameters
        ----------
        df_results : pd.DataFrame
            A DataFrame that must have 'time', 'ptc_energy_kJ', and 'gb_energy_kJ' columns
            (or whichever columns you need for plotting).
        """
        df2 = df_results#.iloc[len(df_results)//2:]
        plt.figure(figsize=(8, 5))
        plt.plot(df2['time'], df2['ptc_energy_kJ'], label='PTC Energy [kJ]')
        plt.plot(df2['time'], df2['ph_energy_kJ'],  label='Preheater Energy [kJ]')
        plt.xlabel('Time')
        plt.ylabel('Energy [kJ]')
        plt.title('PTC and Preheater Energy vs. Time')
        plt.legend()
        plt.tight_layout()
        plt.show()
        
    def plot_results_mode(self, df_results):
        """
        Plots the main simulation results over time.

        Parameters
        ----------
        df_results : pd.DataFrame
            A DataFrame that must have 'time', 'ptc_energy_kJ', and 'gb_energy_kJ' columns
            (or whichever columns you need for plotting).
        """
        df2 = df_results#.iloc[len(df_results)//2:]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(df2['time'], df2['ptc_energy_kJ'], label='PTC Energy [kJ]')
        ax.plot(df2['time'], df2['ph_energy_kJ'],  label='Preheater Energy [kJ]')
        ax2 = plt.twinx(ax)
        ax2.scatter(df2['time'], df2['TESmode'], c='k')
        ax.set_xlabel('Time')
        ax.set_ylabel('Energy [kJ]')
        plt.title('PTC and Preheater Energy vs. Time')
        plt.legend()
        plt.tight_layout()
        plt.show()
        
        
    def plot_TES_profile_colormap(self, df_results):
        """
        Plots a 2D colormap of the TES temperature profiles over time.
    
        Parameters
        ----------
        df_results : pd.DataFrame
            Must have:
            - 'time': (numeric or datetime) time or time-step index
            - 'TES_profiles': each entry is the 1D temperature array (or something convertible to 1D)
                              for that time-step in the TES.
        """
        # 1) Extract the list of TES profiles
        df2 = df_results#.iloc[len(df_results)//2:].reset_index(drop=True)
        profiles_list = df2['TES_profiles'].values  # an array/list of arrays
        N = len(profiles_list)  # number of time steps
    
        # 2) Convert each profile to a 1D numpy array (flatten if needed),
        first_profile = np.array(profiles_list[0]).ravel()
        M = len(first_profile)
    
        # 3) Build the 2D array Z with shape (M, N)
        Z = np.zeros((M, N))
        for i in range(N):
            # Convert to numpy array and flatten in case it's 2D (e.g. shape (N,1))
            list_element = profiles_list[i]
            list_element2 = list_element[0][::-1]
            if df2['TES_layout'][i] =='discharge':
                temp_profile = np.array(list_element).ravel()
            elif df2['TES_layout'][i] == 'charge':
                temp_profile = np.array(list_element2).ravel()

            # Optional: sanity check that all profiles have same length
            if len(temp_profile) != M:
                raise ValueError(
                    f"Row {i} in TES_profiles has length {len(temp_profile)}, "
                    f"but expected {M}."
                )
            Z[:,i] = temp_profile
    
        # 4) Create an x-axis for TES dimension. 
        #    If you have actual tank length in meters, use e.g. np.linspace(0, L, N)
        y = np.linspace(0, 1, M)  # normalized from 0..1
    
        # 5) Convert 'time' to numeric axis
        times_raw = df2['time'].values
        # If 'time' is datetime, convert to hours from the first timestamp
        if isinstance(times_raw[0], pd.Timestamp):
            t0 = df2['time'].iloc[0]
            x_vals = (df2['time'] - t0).dt.total_seconds() / 3600.0
            x_label = 'Time [h]'
        else:
            # Use raw numeric values or indices
            x_vals = times_raw
            x_label = 'Time'
    
        # 6) Make grids for pcolormesh
        X, Y = np.meshgrid(x_vals, y)
    
        # 7) Plot with pcolormesh
        fig, ax = plt.subplots(figsize=(8, 5))
        # shading='auto' is recommended (avoids some edge alignment issues)
        cs = ax.pcolormesh(X, Y, Z, cmap='coolwarm', shading='auto')
        
        # 8) Add a colorbar
        cbar = plt.colorbar(cs, ax=ax)
        cbar.set_label('Temperature [°C]', rotation=90)
    
        # 9) Labels, title, etc.
        ax.set_ylabel('Normalized TES Height [-]')
        ax.set_xlabel(x_label)
        ax.set_title('TES Temperature Distribution vs. Time')
    
        plt.tight_layout()
        plt.show()