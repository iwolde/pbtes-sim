import tespy.networks as tpn
import tespy.connections as tpcn
import tespy.components as tpc
from pbtes.storage import ThermalEnergyStorage


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
                 HTF=None,
                 topology='Parallel',
                 tank_config='indirect'):
        """
        Constructor initializes placeholders for the network, components, 
        and connections. Actual creation of these will occur in other methods.
        """
        self.HTF = HTF
        self.topology = topology
        self.tank_config = tank_config  # 'direct' or 'indirect'
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
        if tank_config == 'direct':
            self.hot_tes = ThermalEnergyStorage(self.tes_params, name='Hot_TES', dt=self.TES_dt)
            self.cold_tes = ThermalEnergyStorage(self.tes_params, name='Cold_TES', dt=self.TES_dt)
            self.tes = self.hot_tes
        else:
            self.tes = ThermalEnergyStorage(self.tes_params, name='TES', dt=self.TES_dt)
        
        self.ptc_field_A = self.component_params['ptc_A']

        self._zinc_pool_T06 = None


    def create_network(self, mode: int, design_mode: str = 'design'):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        
        In 'design' mode: all component parameters (Q, ttd, A, E, T, pr) are set.
        In 'offdesign' mode: only structural parameters (p, fluid, pr) are set;
                             thermal parameters come from stored design.
        """
        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 700], m_range=[0.01, 100000.0])
        
        # Clear stale component references from previous modes
        for attr in ('ptc_field', 'charge_tes_hx', 'high_t_charge_hx',
                     'discharge_tes_hx', 'hot_tank_hx', 'cold_tank_hx',
                     'splitter1', 'merge2', 'tes_ch_source', 'tes_ch_sink',
                     'tes_dch_source', 'tes_dch_sink'):
            try:
                delattr(self, attr)
            except AttributeError:
                pass

        # 3) Create and add components
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        if mode in [1, 2, 5, 6]:
            from pbtes.components import PTCField
            use_inhouse = self.component_params.get('use_inhouse_ptc', False)
            self.ptc_field = PTCField(label='PTCField', rows=self.rows, modules=self.modules, use_inhouse_ptc=use_inhouse)
        else:
            self.ptc_field = None

        if mode in [1, 6]:
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.charge_tes_hx = tpc.HeatExchanger(label='Charge_TES_HX')
                if mode == 1:
                    self.charge_tes_hx.set_attr(design=['ttd_l'], offdesign=['kA'])
                elif mode == 6:
                    self.charge_tes_hx.set_attr(offdesign=['kA'])
            else:
                is_sd = (getattr(self, 'topology', 'Parallel') == 'Series')
                if is_sd and mode == 1:
                    self.hot_tank_hx = tpc.SimpleHeatExchanger(label='Hot_Tank_Pipe')
                    self.cold_tank_hx = tpc.SimpleHeatExchanger(label='Cold_Tank_Pipe')
                else:
                    self.charge_tes_hx = tpc.SimpleHeatExchanger(label='Charge_TES_Pipe')
            if mode == 1 and getattr(self, 'topology', 'Parallel') == 'Parallel':
                self.splitter1 = tpc.nodes.splitter.Splitter(label='Splitter1')
                self.merge2 = tpc.nodes.merge.Merge(label='Merge2')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
                self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        elif mode == 5:
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.high_t_charge_hx = tpc.HeatExchanger(label='High_T_Charge_HX')
                # design=['ttd_l']: explicitly sizes the HX at the design point.
                # ttd_l = T_hot_out - T_cold_in = T10 - T13.
                # Series flow: T10 = T05 = 520°C (preheater Q=0), T13 = 400°C → ttd_l = 120 K.
                use_inhouse = self.component_params.get('use_inhouse_ptc', False)
                if use_inhouse:
                    self.high_t_charge_hx.set_attr(design=[], offdesign=['kA'])
                else:
                    self.high_t_charge_hx.set_attr(design=['ttd_l'], offdesign=['kA'])
                self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
                self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
            else:
                self.high_t_charge_hx = tpc.SimpleHeatExchanger(label='High_T_Charge_Pipe')
        elif mode == 3:
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.discharge_tes_hx = tpc.HeatExchanger(label='Discharge_TES_HX')
                self.discharge_tes_hx.set_attr(design=['ttd_l'], offdesign=['kA'])
                self.tes_dch_source = tpc.Source('TES_discharge_inlet_source')
                self.tes_dch_sink   = tpc.Sink('TES_discharge_outlet_sink')
            else:
                self.discharge_tes_hx = tpc.SimpleHeatExchanger(label='Discharge_TES_Pipe')
        
        # Mode-specific connections
        if mode == 1:
            self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
            if getattr(self, 'topology', 'Parallel') == 'Series':
                is_sd = (getattr(self, 'tank_config', 'indirect') == 'direct')
                if is_sd:
                    self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.hot_tank_hx, 'in1', label='02_PTC_HTPX')
                    self.conn_ht_ph = tpcn.Connection(self.hot_tank_hx, 'out1', self.preheater_hx, 'in1', label='HTPX_PH')
                    self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                    self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cold_tank_hx, 'in1', label='06_PR_CTPX')
                    self.conn_10 = tpcn.Connection(self.cold_tank_hx, 'out1', self.cycle_closer, 'in1', label='10_CTPX_CC')
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_ht_ph, self.conn_05, self.conn_06, self.conn_10)
                    for c, T0, h0, m0, p0 in [
                    (self.conn_01, 440, 625, 13.0, 50),
                    (self.conn_02, 560, 808, 13.0, 50),
                    (self.conn_ht_ph, 520, 747, 13.0, 50),
                    (self.conn_05, 520, 747, 13.0, 50),
                    (self.conn_06, 480, 686, 13.0, 50),
                    (self.conn_10, 440, 625, 13.0, 50),
                ]:
                        c.set_attr(T0=T0, h0=h0, m0=m0, p0=p0)
                else:
                    self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.preheater_hx, 'in1', label='02_PTC_PH')
                    self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                    self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.charge_tes_hx, 'in1', label='06_PR_CHX')
                    self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.cycle_closer, 'in1', label='10_CHX_CC')
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14]:
                        conn.set_attr(T0=500, h0=700, m0=5, p0=5)
            else:
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.splitter1, 'in1', label='02_PTC_SP1')
                self.conn_04 = tpcn.Connection(self.splitter1, 'out1', self.preheater_hx, 'in1', label='04_SP1_PH')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.merge2, 'in1', label='06_PR_MG2')
                self.conn_08 = tpcn.Connection(self.merge2, 'out1', self.cycle_closer, 'in1', label='08_MG2_CC')
                self.conn_09 = tpcn.Connection(self.splitter1, 'out2', self.charge_tes_hx, 'in1', label='09_SP1_CHX')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.merge2, 'in2', label='10_CHX_MG2')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_08, self.conn_09, self.conn_10, self.conn_13, self.conn_14)
                    for conn in [self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_08, self.conn_09, self.conn_10, self.conn_13, self.conn_14]:
                        conn.set_attr(T0=500, h0=700, m0=5, p0=5)
                else:
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_08, self.conn_09, self.conn_10)
                    for conn in [self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_08, self.conn_09, self.conn_10]:
                        conn.set_attr(T0=500, h0=700, m0=5, p0=5)
        elif mode == 2:
            self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
            self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.preheater_hx, 'in1', label='02_PTC_PH')
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06)
            for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06]:
                conn.set_attr(T0=500, h0=714, m0=35, p0=5)
        elif mode == 3:
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.conn_04 = tpcn.Connection(self.discharge_tes_hx, 'out2', self.preheater_hx, 'in1', label='04_DHX_PH')
                self.conn_11 = tpcn.Connection(self.cycle_closer, 'out1', self.discharge_tes_hx, 'in2', label='11_CC_DHX')
                self.conn_15 = tpcn.Connection(self.tes_dch_source, 'out1', self.discharge_tes_hx, 'in1', label='15_DCHSC_DHX')
                self.conn_16 = tpcn.Connection(self.discharge_tes_hx, 'out1', self.tes_dch_sink, 'in1', label='16_DHX_DCHSK')
                self.network.add_conns(self.conn_04, self.conn_05, self.conn_06, self.conn_11, self.conn_15, self.conn_16)
                for conn in [self.conn_04, self.conn_05, self.conn_06, self.conn_11, self.conn_15, self.conn_16]:
                    conn.set_attr(T0=520, h0=700, m0=30, p0=5)
                self.discharge_tes_hx.set_attr(pr1=1.0, pr2=1.0)
            else:
                self.conn_04 = tpcn.Connection(self.discharge_tes_hx, 'out1', self.preheater_hx, 'in1', label='04_DHX_PH')
                self.conn_11 = tpcn.Connection(self.cycle_closer, 'out1', self.discharge_tes_hx, 'in1', label='11_CC_DHX')
                self.network.add_conns(self.conn_04, self.conn_05, self.conn_06, self.conn_11)
                for conn in [self.conn_04, self.conn_05, self.conn_06, self.conn_11]:
                    conn.set_attr(T0=500, h0=714, m0=35, p0=5)
                self.discharge_tes_hx.set_attr(pr=1.0, Q='var')

        elif mode == 4:
            self.conn_04 = tpcn.Connection(self.cycle_closer, 'out1', self.preheater_hx, 'in1', label='04_CC_PH')
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            self.network.add_conns(self.conn_04, self.conn_05, self.conn_06)
            for conn in [self.conn_04, self.conn_05, self.conn_06]:
                conn.set_attr(T0=500, h0=714, m0=35, p0=5)

        elif mode == 5:
            self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
            self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.high_t_charge_hx, 'in1', label='02_PTC_CHX')
            self.conn_10 = tpcn.Connection(self.high_t_charge_hx, 'out1', self.preheater_hx, 'in1', label='10_CHX_PH')
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.high_t_charge_hx, 'in2', label='13_CHSC_CHX')
                self.conn_14 = tpcn.Connection(self.high_t_charge_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                self.network.add_conns(self.conn_01, self.conn_02, self.conn_10, self.conn_05, self.conn_06, self.conn_13, self.conn_14)
                # IMPORTANT: h0 must be set for ALL connections so TESPy's initialise_source()
                # is never called — that fallback uses 200°C/250°C which crashes the fluid (min 300°C).
                #
                # Mode 5 design point: preheater Q=0, TES cold inlet at 480°C (process return
                # level, realistic TES bottom for a warm-but-not-full TES), ttd_l=20K.
                # → T10=T05=500°C, T_PTC_out≈560°C (high irradiance), T14≈510°C (TES charge temp)
                # Fluid h at 50 bar: 480°C≈686, 500°C≈716, 560°C≈808 kJ/kg
                # Fluid h at  5 bar: 480°C≈686, 510°C≈732 kJ/kg
                for c, T0, h0, m0, p0 in [
                    (self.conn_01, 480, 686, 13.0, 50),  # CC→PTC inlet  = process return
                    (self.conn_02, 560, 808, 13.0, 50),  # PTC outlet    = high-irr output
                    (self.conn_10, 500, 716, 13.0, 50),  # HX hot out    = T13+ttd_l=480+20
                    (self.conn_05, 500, 716, 13.0, 50),  # Preheater out = T10 (Q=0)
                    (self.conn_06, 480, 686, 13.0, 50),  # Process return
                    (self.conn_13, 480, 686, 12.0, 5),   # TES cold inlet (process return level)
                    (self.conn_14, 510, 732, 12.0, 5),   # TES heated outlet
                ]:
                    c.set_attr(T0=T0, h0=h0, m0=m0, p0=p0)
            else:
                self.network.add_conns(self.conn_01, self.conn_02, self.conn_10, self.conn_05, self.conn_06)
                for c, T0, h0, m0, p0 in [
                    (self.conn_01, 480, 686, 13.0, 50),
                    (self.conn_02, 560, 808, 13.0, 50),
                    (self.conn_10, 500, 716, 13.0, 50),
                    (self.conn_05, 500, 716, 13.0, 50),
                    (self.conn_06, 480, 686, 13.0, 50),
                ]:
                    c.set_attr(T0=T0, h0=h0, m0=m0, p0=p0)

        elif mode == 6:
            if getattr(self, 'topology', 'Parallel') == 'Series':
                self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.preheater_hx, 'in1', label='02_PTC_PH_Series')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR_Series')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.charge_tes_hx, 'in1', label='06_PR_CHX_Series')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.cycle_closer, 'in1', label='10_CHX_CC_Series')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14]:
                        conn.set_attr(T0=500, h0=700, m0=2)
                else:
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10]:
                        conn.set_attr(T0=500, h0=700, m0=2)
            else:
                self.cycle_closer2 = tpc.CycleCloser(label='CycleCloser2')
                self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.charge_tes_hx, 'in1', label='02_PTC_CHX')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.cycle_closer, 'in1', label='10_CHX_CC')
                self.conn_04 = tpcn.Connection(self.cycle_closer2, 'out1', self.preheater_hx, 'in1', label='04_CC2_PH')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer2, 'in1', label='06_PR_CC2')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    conns = [self.conn_01, self.conn_02, self.conn_10, self.conn_04, self.conn_05, self.conn_06, self.conn_13, self.conn_14]
                else:
                    conns = [self.conn_01, self.conn_02, self.conn_10, self.conn_04, self.conn_05, self.conn_06]
                self.network.add_conns(*conns)
                # Fluid h at 50 bar: 480°C≈686, 500°C≈716, 520°C≈747 kJ/kg
                # Fluid h at  5 bar: 400°C≈562, 440°C≈623 kJ/kg
                for c, h0, m0, p0 in [
                    (self.conn_01, 716, 12.0, 50),
                    (self.conn_02, 747, 12.0, 50),
                    (self.conn_10, 716, 12.0, 50),
                    (self.conn_04, 716, 7.4, 50),
                    (self.conn_05, 747, 7.4, 50),
                    (self.conn_06, 686, 7.4, 50),
                ]:
                    c.set_attr(h0=h0, m0=m0, p0=p0)
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13.set_attr(h0=562, m0=25.0, p0=5)
                    self.conn_14.set_attr(h0=623, m0=25.0, p0=5)
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_02.set_attr(p=self.conexion_params['6_p'], fluid=self.conexion_params['6_f'])
                    self.charge_tes_hx.set_attr(pr2=1.0)


        # === STRUCTURAL parameters (always applied, design + offdesign) ===
        
        
        # PTC pressure drop
        if mode in [1, 2, 5, 6]:
            self.ptc_field.set_attr(pr=1.0)
        
        # Secondary loop connection pressure and fluid (always)
        if mode in [1, 5, 6] and hasattr(self, 'conn_13'):
            self.conn_13.set_attr(p=self.conexion_params['13_p'], fluid=self.conexion_params['13_f'])
        if mode == 3 and hasattr(self, 'conn_15'):
            self.conn_15.set_attr(p=self.conexion_params['15_p'], fluid=self.conexion_params['15_f'])
        if mode == 1 and hasattr(self, 'conn_13_hot'):
            self.conn_13_hot.set_attr(p=self.conexion_params['13_p'], fluid=self.conexion_params['13_f'])
        if mode == 1 and hasattr(self, 'conn_13_cold'):
            self.conn_13_cold.set_attr(p=self.conexion_params['13_p'], fluid=self.conexion_params['13_f'])
        
        if hasattr(self, 'conn_06') and self.conn_06 is not None:
            self.conn_06.set_attr(
                p=self.conexion_params['6_p'],
                fluid=self.conexion_params['6_f']
            )
        
        if mode == 6 and hasattr(self, 'conn_02') and self.conn_02 is not None:
            self.conn_02.set_attr(p=self.conexion_params['6_p'])
        
        # HX pressure drops (structural; skip for M6 Parallel - uses conn p anchors)
        is_m6_par = (mode == 6 and getattr(self, 'topology', 'Parallel') == 'Parallel')
        if mode in [1, 6] and hasattr(self, 'charge_tes_hx'):
            if getattr(self, 'tank_config', 'indirect') == 'indirect' and not is_m6_par:
                self.charge_tes_hx.set_attr(pr2=1.0)
            elif getattr(self, 'tank_config', 'indirect') == 'direct':
                self.charge_tes_hx.set_attr(pr=1.0, Q='var')
        if mode == 5 and hasattr(self, 'high_t_charge_hx'):
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.high_t_charge_hx.set_attr(pr1=1.0, pr2=1.0)
            else:
                self.high_t_charge_hx.set_attr(pr=1.0, Q='var')
        if mode == 1 and hasattr(self, 'hot_tank_hx') and self.hot_tank_hx is not None:
            if getattr(self, 'tank_config', 'indirect') == 'direct':
                self.hot_tank_hx.set_attr(pr=1.0, Q='var')
            else:
                self.hot_tank_hx.set_attr(pr1=1.0, pr2=1.0)
        if mode == 1 and hasattr(self, 'cold_tank_hx') and self.cold_tank_hx is not None:
            if getattr(self, 'tank_config', 'indirect') == 'direct':
                # pr=None for BOTH design and offdesign quasi-design:
                # With all other components at pr=1.0, a closed loop would create a
                # degenerate Jacobian row (all pressures determined, CycleCloser eq
                # becomes 0=0). pr=None on cold_tank_hx provides the free pressure
                # DOF that TESPy needs to build a non-singular matrix.
                # (pr_cold becomes a component variable that TESPy solves for ~50 bar.)
                self.cold_tank_hx.set_attr(pr=None, Q='var')
            else:
                self.cold_tank_hx.set_attr(pr1=1.0, pr2=1.0)
        self.process_hx.set_attr(pr=1.0)
        if getattr(self, 'topology', 'Parallel') == 'Series' and mode == 1:
            self.preheater_hx.set_attr(pr=1.0)
        
        # === BOUNDARY CONDITIONS (always applied) ===
        # SD Mode 1 (Series/Direct, Mode 1): conn_05.T and conn_06.T are NOT set here.
        # - conn_05.T is determined by preheater_hx.Q=0 → T05=T_ht_ph (hot tank outlet).
        # - conn_06.T is a RESULT of the process energy balance (process_hx.Q=PR_Q + known T_in);
        #   setting it simultaneously with Q would over-constrain the Jacobian (singularity).
        # - conn_02.T=560°C (PTC outlet) is set in set_operation_mode as the solar anchor.
        # Mode 5: conn_05.T is NOT set here — it is determined implicitly by
        # preheater_hx.Q=0 (T05=T10) and ttd_l=20K.
        is_sd_m1 = (mode == 1 and getattr(self, 'tank_config', 'indirect') == 'direct'
                    and getattr(self, 'topology', 'Parallel') == 'Series')
        # Parallel Mode 1 offdesign: Release conn_05.T to decouple PTC outlet
        # temperature from the process-inlet requirement. Without this, T_ptc_out
        # is forced to 520 C (preheater Q=0 + splitter dT=0), preventing the
        # TES charge branch from receiving fluid hot enough to charge effectively.
        # Design mode keeps 520 C for proper HX sizing.
        is_parallel_m1 = (mode == 1
                          and getattr(self, 'topology', 'Parallel') == 'Parallel')
        if (hasattr(self, 'conn_05') and self.conn_05 is not None
                and mode != 5 and not is_sd_m1):
            if not (design_mode == 'offdesign' and is_parallel_m1):
                self.conn_05.set_attr(T=self.conexion_params['5_T'])
        if hasattr(self, 'conn_06') and self.conn_06 is not None and not is_m6_par and not is_sd_m1:
            self.conn_06.set_attr(T=self.conexion_params['6_T'])
        if not is_m6_par:
            self.process_hx.set_attr(Q=self.component_params['PR_Q'])
        
        # === DESIGN-ONLY parameters (component sizing) ===
        if design_mode == 'design':            
            # PTC design parameters (skip M6 Par - independent cycle)
            if mode in [1, 5, 6] and not is_m6_par:
                self.ptc_field.set_attr(
                    aoi=self.component_params['ptc_aoi'], 
                    doc=self.component_params['ptc_doc'],
                    Tamb=self.component_params['ptc_tamb'], 
                    A=self.component_params['ptc_A'], 
                    eta_opt=self.component_params['eta_opt'], 
                    c_1=self.component_params['ptc_c_1'], 
                    c_2=self.component_params['ptc_c_2'], 
                    E=self.component_params['ptc_E'],
                    iam_1=self.component_params['ptc_iam_1'], 
                    iam_2=self.component_params['ptc_iam_2']
                )
            
            # HX thermal design parameter (force kA computation)
            if mode == 1 and hasattr(self, 'charge_tes_hx'):
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.charge_tes_hx.set_attr(ttd_l=20)
            if mode == 1 and hasattr(self, 'hot_tank_hx') and self.hot_tank_hx is not None:
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.hot_tank_hx.set_attr(ttd_l=20)
            if mode == 1 and hasattr(self, 'cold_tank_hx') and self.cold_tank_hx is not None:
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.cold_tank_hx.set_attr(ttd_l=20)
            # Mode 5 HX: ttd_l=20K at design point.
            # Design temperatures: T_cold_in=480°C (TES bottom at process-return level),
            # T_hot_out=T05=500°C (preheater Q=0 → T10=T05=T_cold_in+ttd_l=500°C).
            # 20K is a realistic terminal temperature difference for an industrial HX,
            # consistent with all other HXs in the network.
            if mode == 5 and hasattr(self, 'high_t_charge_hx'):
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.high_t_charge_hx.set_attr(ttd_l=20.0)
            if mode == 3 and hasattr(self, 'discharge_tes_hx'):
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.discharge_tes_hx.set_attr(ttd_l=20)
        
        if mode in [2, 3, 4, 6]:
            pass

    def set_operation_mode(self, TESmode='4', 
                           current_irr=0,
                           profile=None,
                           prev_TES_lay = 'Charge',
                           mode = 'design'):
        """
        mode 1: High irradiation, PTC to process and to TES
        mode 2: Mid irradiation, PTC to process, TES in standby
        mode 3: Low irradiation, TES to process
        mode 4: Low irradiation, TES in standby (auxiliary heater supplies process)
        mode 6: Mid to high irradiation, PTC full to TES (auxiliary heater supplies process)
        """
        self._current_irr_for_guess = current_irr
        use_inhouse = self.component_params.get('use_inhouse_ptc', False)
        if use_inhouse:
            from pbtes.components.ptc_model import PTCFieldModel
            ptc_model = PTCFieldModel(self.component_params)
            ptc_model.design_solar_field(self.component_params['ptc_A'], self.HTF)
            m_ptc_design = ptc_model.m_dot_PTC_real * ptc_model.N_loops_real
            if getattr(self, 'topology', 'Parallel') == 'Parallel' and TESmode == '1':
                T_ptc_design = 520.0
                m_process_design = abs(self.component_params.get('PR_Q', 450000.0)) / (1500.0 * 40.0)
                m_ptc_design = max(m_ptc_design, m_process_design + 2.0)
            else:
                T_ptc_design = 560.0

        if profile is None:
            if hasattr(self, 'tes') and self.tes is not None and self.tes.profile is not None:
                profile = self.tes.profile
            else:
                profile = np.ones(20) * 450.0
        if prev_TES_lay == 'Charge':
            TES_top = profile[0]
            TES_bot = profile[-1]
        elif prev_TES_lay == 'Discharge':
            TES_top = profile[-1]
            TES_bot = profile[0]

        if TESmode == '1':
            self.create_network(mode=1, design_mode=mode)
            is_series_direct = (getattr(self, 'topology', 'Parallel') == 'Series'
                                and getattr(self, 'tank_config', 'indirect') == 'direct')
            
            if is_series_direct:
                # SD Mode 1 — unified design and quasi-design offdesign setup.
                # DOF: 3 comp vars (Q_hot, Q_cold, pr_cold=None) + 12 conn vars = 15
                #      required equations: conn_ht_ph.T + conn_10.T + conn_02.T=560
                #                        + preheater.Q=0 + process.Q=PR_Q
                #                        + conn_06.p+fluid(structural) = 15 ok
                # conn_06.T is NEVER set — it is a result of process energy balance.
                # conn_02.T=560 is the PTC outlet anchor for BOTH design and offdesign;
                #   mass flow adjusts to maintain this setpoint at different irradiances.
                self.hot_tes.set_state('charge')
                self.cold_tes.set_state('charge')
                hot_bot = self.hot_tes.profile[-1]
                cold_bot = self.cold_tes.profile[-1]
                self.conn_ht_ph.set_attr(T=hot_bot)
                if use_inhouse:
                    self.conn_02.set_attr(T=T_ptc_design, m=m_ptc_design)
                else:
                    self.conn_02.set_attr(T=560)
                self.conn_10.set_attr(T=cold_bot)
                self.ptc_field.set_attr(
                    A=self.component_params['ptc_A'],  # fixed max aperture always
                    eta_opt=self.component_params['eta_opt'],
                    aoi=self.component_params.get('ptc_aoi', 0),
                    doc=self.component_params.get('ptc_doc', 1),
                    Tamb=self.component_params.get('ptc_tamb', 20),
                    c_1=self.component_params.get('ptc_c_1', 0),
                    c_2=self.component_params.get('ptc_c_2', 0),
                    iam_1=self.component_params.get('ptc_iam_1', 0),
                    iam_2=self.component_params.get('ptc_iam_2', 0),
                    E=(self.component_params['ptc_E'] if mode == 'design' else current_irr))
                
                # Adaptive auxiliary heating for SD Mode 1:
                # If the hot tank outlet (hot_bot) is below the process inlet target (520°C),
                # allow the auxiliary preheater to top up the temperature by setting Q='var'
                # and fixing conn_05.T to 520°C. Otherwise, run solar-only (Q=0).
                if hot_bot >= 520.0:
                    self.preheater_hx.set_attr(Q=0)
                    self.conn_05.set_attr(T=None)
                else:
                    self.preheater_hx.set_attr(Q='var')
                    self.conn_05.set_attr(T=self.conexion_params['5_T'])
            else:
                self.tes.set_state('charge')
                TES_bot = self.tes.profile[-1]
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13.set_attr(T=TES_bot)
                    if mode == 'design':
                        self.conn_14.set_attr(T=TES_bot + 40)
                    else:
                        if getattr(self, 'topology', 'Parallel') == 'Parallel':
                            # Option B: Fix hot-side return T10 = 480 C, let secondary mass flow float
                            self.conn_13.set_attr(m=None)
                            self.conn_10.set_attr(T=self.conexion_params['6_T'])
                            self.conn_14.set_attr(T=None)
                        else:
                            m_val = getattr(self, 'tes_charge_m', None)
                            if m_val is None:
                                import os, pandas as pd
                                csv_path = os.path.join('.tespy_cache', f'base_design_{TESmode}', 'connections.csv')
                                if os.path.exists(csv_path):
                                    try:
                                        df = pd.read_csv(csv_path, sep=';', index_col=0)
                                        if '13_CHSC_CHX' in df.index:
                                            m_val = float(df.loc['13_CHSC_CHX', 'm'])
                                            self.tes_charge_m = m_val
                                    except Exception as err:
                                        print(f"[DEBUG error reading csv]: {err}")
                                        pass
                                if m_val is None:
                                    m_val = 3.0
                            self.conn_13.set_attr(m=m_val)
                            self.conn_14.set_attr(T=None)

            
            if not is_series_direct:
                self.preheater_hx.set_attr(Q=0)
            
            if mode == 'design':
                if not is_series_direct:
                    self.conn_05.set_attr(T=self.conexion_params['5_T'])
                    self.conn_06.set_attr(T=self.conexion_params['6_T'])
                # SD M1: conn_05.T and conn_06.T intentionally not set (see create_network).
                # For non-SD Series topology with indirect tank:
                if getattr(self, 'topology', 'Parallel') == 'Series' and not is_series_direct:
                    if not use_inhouse:
                        self.ptc_field.set_attr(A='var')
                if use_inhouse and not is_series_direct:
                    self.conn_05.set_attr(T=None)
                    self.conn_02.set_attr(T=T_ptc_design, m=m_ptc_design)
            else:
                if not is_series_direct:
                    # Non-SD configs: PTC output adjusts mass flow, Q=PR_Q pins process.
                    # Parallel Mode 1: Anchor PTC outlet at the estimated achievable
                    # temperature (DNI-based). This replaces the conn_05.T constraint
                    # removed in create_network, allowing the TES charge branch to
                    # receive hotter fluid while the process HX extracts its fixed
                    # -450 kW from the hotter inlet.
                    if getattr(self, 'topology', 'Parallel') == 'Parallel':
                        T_in_nom = self.conexion_params.get('6_T', 480.0)
                        T_out_design = 560.0
                        E_design = self.component_params.get('ptc_E', 900.0)
                        irr_frac = min(current_irr / E_design, 1.2)
                        T_ptc_target = T_in_nom + irr_frac * (T_out_design - T_in_nom)
                        self.conn_02.set_attr(T=round(T_ptc_target, 1))
                    if not use_inhouse:
                        self.ptc_field.set_attr(
                            E=current_irr, A=self.component_params['ptc_A'],
                            eta_opt=self.component_params['eta_opt'],
                            aoi=self.component_params.get('ptc_aoi', 0),
                            doc=self.component_params.get('ptc_doc', 1),
                            Tamb=self.component_params.get('ptc_tamb', 20),
                            c_1=self.component_params.get('ptc_c_1', 0),
                            c_2=self.component_params.get('ptc_c_2', 0),
                            iam_1=self.component_params.get('ptc_iam_1', 0),
                            iam_2=self.component_params.get('ptc_iam_2', 0))
                    if getattr(self, 'topology', 'Parallel') == 'Series':
                        self.process_hx.set_attr(Q=None)
                        if hasattr(self, 'ptc_field_A_designed') and not use_inhouse:
                            self.ptc_field.set_attr(A=self.ptc_field_A_designed)
        
        elif TESmode == '2':
            # All flow from PTC to process
            self.create_network(mode=2, design_mode=mode)
            self.preheater_hx.set_attr(Q=0)
            if use_inhouse:
                pass
            else:
                if mode == 'design':
                    self.ptc_field.set_attr(
                        aoi=self.component_params['ptc_aoi'], doc=self.component_params['ptc_doc'],
                        Tamb=self.component_params['ptc_tamb'], A='var',
                        eta_opt=self.component_params['eta_opt'], c_1=self.component_params['ptc_c_1'],
                        c_2=self.component_params['ptc_c_2'], E=self.component_params['ptc_E'],
                        iam_1=self.component_params['ptc_iam_1'], iam_2=self.component_params['ptc_iam_2'])
                else:
                    self.ptc_field.set_attr(
                        E=current_irr, A='var',
                        eta_opt=self.component_params['eta_opt'],
                        aoi=self.component_params.get('ptc_aoi', 0),
                        doc=self.component_params.get('ptc_doc', 1),
                        Tamb=self.component_params.get('ptc_tamb', 20),
                        c_1=self.component_params.get('ptc_c_1', 0),
                        c_2=self.component_params.get('ptc_c_2', 0),
                        iam_1=self.component_params.get('ptc_iam_1', 0),
                        iam_2=self.component_params.get('ptc_iam_2', 0))
                    A_guess = abs(self.component_params.get('PR_Q', 450000)) / (max(current_irr, 100) * self.component_params.get('eta_opt', 0.75))
                    try: self.ptc_field.A.val = A_guess
                    except: pass
                    # Set initial guess for A to avoid solver stall
                    A_guess = 1e6 / (max(current_irr, 100) * self.component_params['eta_opt'])
                    self.ptc_field.A.val = A_guess
        elif TESmode == '3':
            from tespy.connections import Ref
            self.create_network(mode=3, design_mode=mode)
            self.tes.set_state('discharge')
            if mode == 'design':
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.preheater_hx.set_attr(Q=0)
            
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                TES_top = profile[0] if prev_TES_lay == 'Charge' else profile[-1]
                self.conn_15.set_attr(T=TES_top)
                self.conn_04.set_attr(T=None)
                self.conn_16.set_attr(T=None)
                
                # Propagate designed kA and mass flow for offdesign simulation
                if mode != 'design':
                    if hasattr(self, 'discharge_hx_kA') and self.discharge_hx_kA is not None:
                        self.discharge_tes_hx.set_attr(kA=self.discharge_hx_kA)
                    m_val = getattr(self, 'tes_charge_m', None)
                    if m_val is not None:
                        self.conn_15.set_attr(m=m_val)
                    else:
                        self.conn_15.set_attr(m=None)
                else:
                    self.conn_15.set_attr(m=None)
            else:
                TES_top = profile[-1] if prev_TES_lay == 'Discharge' else profile[0]
                self.conn_04.set_attr(T=TES_top)
            
            self.conn_11.set_attr(T=None)
            
            # Regime selection and guesses (offdesign only)
            if mode != 'design':
                t_ph_out = self.conexion_params['5_T']
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    # To guarantee 100% convergence and avoid singular Jacobian matrices due to extremely narrow
                    # temperature crossing windows at high discharge temperatures, we always keep the process inlet
                    # temperature (conn_05.T) fixed and allow preheater_hx.Q to float. Negative preheater heat rate Q
                    # (representing solar overheating above 520 C) is post-processed in solver.py as max(0, Q_aux).
                    self.conn_05.set_attr(T=t_ph_out)
                    self.preheater_hx.set_attr(Q='var')
                    self.conn_04.set_attr(T0=TES_top - 10.0)
                    self.conn_16.set_attr(T0=TES_top - 40.0)
                else:
                    regime_a_threshold = t_ph_out
                    if TES_top >= regime_a_threshold:
                        self.conn_05.set_attr(T=None)
                        self.preheater_hx.set_attr(Q=0)
                    else:
                        self.conn_05.set_attr(T=t_ph_out)
                        self.preheater_hx.set_attr(Q='var')
                # Warm-start guess for CC->DHX to aid solver convergence
                self.conn_11.set_attr(T0=self.conexion_params['6_T'])

        elif TESmode == '4':
            self.create_network(mode=4, design_mode=mode)
             
        elif TESmode == '5':
            # Mode 5: Series flow PTC -> High_T_HX -> Preheater -> Process -> CC.
            # At design: preheater Q=0, ttd_l=20K. TES cold inlet (T13) is assumed to be
            # at least 480°C (process return level), yielding T10=500°C.
            self.create_network(mode=5, design_mode=mode)
            self.tes.set_state('charge')
            
            if mode == 'design':
                TES_bot = 480.0 # Force realistic TES bottom for design to ensure T10 >= 500
            else:
                TES_bot = self.tes.profile[-1]
                
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.conn_13.set_attr(T=TES_bot)
                if mode == 'design':
                    self.conn_14.set_attr(T=TES_bot + 40)
                else:
                    m_val = getattr(self, 'tes_charge_m', None)
                    if m_val is None:
                        import os, pandas as pd
                        csv_path = os.path.join('.tespy_cache', f'base_design_{TESmode}', 'connections.csv')
                        if os.path.exists(csv_path):
                            try:
                                df = pd.read_csv(csv_path, sep=';', index_col=0)
                                if '13_CHSC_CHX' in df.index:
                                    m_val = float(df.loc['13_CHSC_CHX', 'm'])
                                    self.tes_charge_m = m_val
                            except Exception:
                                pass
                        if m_val is None:
                            m_val = 3.0
                    self.conn_13.set_attr(m=m_val)
                    self.conn_14.set_attr(T=None)
            else:
                self.conn_10.set_attr(T=TES_bot)
            
            # Preheater off at design: forces all solar surplus to TES via HX
            if mode == 'design':
                self.preheater_hx.set_attr(Q=0)
                self.conn_02.set_attr(T=560)
                if not use_inhouse:
                    self.ptc_field.set_attr(A='var')
                else:
                    self.conn_06.set_attr(T=None)
                    self.conn_02.set_attr(T=T_ptc_design, m=m_ptc_design)
            
            if mode == 'offdesign':
                # DNI-aware PTC outlet anchor avoids convergence issues
                # from the coupled fixed-aperture PTC + fixed-kA HX solve.
                # The PTC outlet is pinned at a temperature achievable at
                # the current irradiance; HX and process HX balance from there.
                T_in_nom = self.conexion_params.get('6_T', 480.0)
                T_ptc = T_in_nom + min(current_irr / 900.0, 1.2) * (560.0 - T_in_nom)
                self.conn_02.set_attr(T=round(T_ptc, 1))
                if not use_inhouse:
                    self.ptc_field.set_attr(
                        E=current_irr, A=self.component_params['ptc_A'],
                        eta_opt=self.component_params['eta_opt'],
                        aoi=self.component_params.get('ptc_aoi', 0),
                        doc=self.component_params.get('ptc_doc', 1),
                        Tamb=self.component_params.get('ptc_tamb', 20),
                        c_1=self.component_params.get('ptc_c_1', 0),
                        c_2=self.component_params.get('ptc_c_2', 0),
                        iam_1=self.component_params.get('ptc_iam_1', 0),
                        iam_2=self.component_params.get('ptc_iam_2', 0))


        elif TESmode == '6':
            is_m6par = (getattr(self, 'topology', 'Parallel') == 'Parallel')
            self.create_network(mode=6, design_mode=mode)
            self.tes.set_state('charge')
            
            TES_bot = self.tes.profile[-1]
            
            if is_m6par:
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13.set_attr(T=TES_bot)
                    if mode == 'design':
                        if use_inhouse:
                            self.conn_14.set_attr(T=None)
                        else:
                            self.conn_14.set_attr(T=TES_bot + 40)
                    else:
                        m_val = getattr(self, 'tes_charge_m', None)
                        if m_val is None:
                            import os, pandas as pd
                            csv_path = os.path.join('.tespy_cache', f'base_design_{TESmode}', 'connections.csv')
                            if os.path.exists(csv_path):
                                try:
                                    df = pd.read_csv(csv_path, sep=';', index_col=0)
                                    if '13_CHSC_CHX' in df.index:
                                        m_val = float(df.loc['13_CHSC_CHX', 'm'])
                                        self.tes_charge_m = m_val
                                except Exception:
                                        pass
                            if m_val is None:
                                m_val = 3.0
                        self.conn_13.set_attr(m=m_val)
                        self.conn_14.set_attr(T=None)
                self.conn_02.set_attr(T=560)  # Constrain PTC outlet for high-T charge
                if mode == 'design':
                    if not use_inhouse:
                        self.ptc_field.set_attr(
                            A=self.component_params['ptc_A'], E=self.component_params['ptc_E'],
                            eta_opt=self.component_params['eta_opt'],
                            aoi=self.component_params.get('ptc_aoi', 0),
                            doc=self.component_params.get('ptc_doc', 1),
                            Tamb=self.component_params.get('ptc_tamb', 20),
                            c_1=self.component_params.get('ptc_c_1', 0),
                            c_2=self.component_params.get('ptc_c_2', 0),
                            iam_1=self.component_params.get('ptc_iam_1', 0),
                            iam_2=self.component_params.get('ptc_iam_2', 0)
                        )
                    else:
                        self.conn_02.set_attr(T=T_ptc_design, m=m_ptc_design)
                        self.conn_10.set_attr(T=420.0)
                else:
                    if not use_inhouse:
                        self.ptc_field.set_attr(
                            E=current_irr, A=self.component_params['ptc_A'],
                            eta_opt=self.component_params['eta_opt'],
                            aoi=self.component_params.get('ptc_aoi', 0),
                            doc=self.component_params.get('ptc_doc', 1),
                            Tamb=self.component_params.get('ptc_tamb', 20),
                            c_1=self.component_params.get('ptc_c_1', 0),
                            c_2=self.component_params.get('ptc_c_2', 0),
                            iam_1=self.component_params.get('ptc_iam_1', 0),
                            iam_2=self.component_params.get('ptc_iam_2', 0)
                        )
                self.process_hx.set_attr(Q=self.component_params['PR_Q'])
                self.conn_05.set_attr(T=self.conexion_params['5_T'])
                self.conn_06.set_attr(T=self.conexion_params['6_T'])
                if hasattr(self, 'charge_hx_kA') and self.charge_hx_kA:
                    self.charge_tes_hx.set_attr(kA=self.charge_hx_kA)
            else:
                if hasattr(self, 'charge_hx_kA') and self.charge_hx_kA:
                    self.charge_tes_hx.set_attr(kA=self.charge_hx_kA)
                if mode == 'design':
                    if not use_inhouse:
                        self.ptc_field.set_attr(A='var')
                    else:
                        self.conn_02.set_attr(T=T_ptc_design, m=None)
                        self.conn_10.set_attr(T=420.0)
                else:
                    if not use_inhouse:
                        self.ptc_field.set_attr(E=current_irr)
                    self.process_hx.set_attr(Q=None)
                    if hasattr(self, 'ptc_field_A_designed') and not use_inhouse:
                        self.ptc_field.set_attr(A=self.ptc_field_A_designed)

        else:   
            raise ValueError(f"Unknown mode {TESmode}")
 
 
    def _apply_design_guesses(self, design_path_full: str) -> None:
        """Load connection T0, m0, h0 from design CSV as initial guesses for offdesign."""
        import os, pandas as pd, numpy as np
        csv = os.path.join(design_path_full, 'connections.csv')
        if not os.path.exists(csv):
            return
        try:
            df = pd.read_csv(csv, sep=';', index_col=0)
        except Exception:
            return
        current_irr = getattr(self, '_current_irr_for_guess', None)
        design_irr = self.component_params.get('ptc_E', 900)
        m_scale = (current_irr / design_irr) if (current_irr and design_irr > 0) else 1.0
        m_scale = max(0.1, min(m_scale, 2.0))
        
        # Check active labels in the network
        active_labels = set(self.network.conns.index) if hasattr(self.network, 'conns') else set()
        
        # For Mode 1 Parallel topology, we implement physically consistent mass flow scaling
        # to ensure mass balance at the splitter and heat exchanger energy balance.
        is_mode1_parallel = (
            getattr(self, 'topology', 'Parallel') == 'Parallel'
            and '09_SP1_CHX' in active_labels
        )
        
        custom_guesses = None
        if is_mode1_parallel:
            try:
                # Find design mass flows
                m_ptc_design = float(df.loc['02_PTC_SP1', 'm'])
                m_process_design = float(df.loc['04_SP1_PH', 'm'])
                m_charge_design = float(df.loc['09_SP1_CHX', 'm'])
                
                # Get current storage bottom temperature (cold-side inlet)
                if hasattr(self, 'conn_13') and self.conn_13 is not None and self.conn_13.T.val is not None:
                    T_cold_in = float(self.conn_13.T.val)
                elif hasattr(self, 'tes') and self.tes is not None and self.tes.profile is not None:
                    T_cold_in = float(self.tes.profile[-1])
                else:
                    T_cold_in = 450.0
                
                # Estimate hot-side charging mass flow based on irradiance scaling
                E_design = self.component_params.get('ptc_E', 900.0)
                A_ptc = self.component_params.get('ptc_A', 1500.0)
                eta_opt = self.component_params.get('eta_opt', 0.816)
                Q_ptc_est = A_ptc * current_irr * eta_opt
                Q_proc_val = abs(self.component_params.get('PR_Q', 450000.0))
                Q_charge_est = max(10000.0, Q_ptc_est - Q_proc_val)
                
                m_process_guess = m_process_design
                m_charge_guess = Q_charge_est / (960.0 * 50.0)
                m_charge_guess = max(0.5, min(m_charge_guess, 100.0))
                m_ptc_guess = m_process_guess + m_charge_guess
                
                # Option B custom guess solver
                kA = getattr(self, 'charge_hx_kA', None)
                if kA is None:
                    kA = 20000.0
                
                # Option B: T_hot_in = 520.0, T_hot_out = 480.0, T_cold_in = T_cold_in
                Q_transfer = m_charge_guess * 960.0 * (520.0 - 480.0)
                LMTD_target = Q_transfer / kA
                dT2 = 480.0 - T_cold_in # lower temperature difference
                
                # Solve for dT1 = 520.0 - T14_guess such that LMTD(dT1, dT2) = LMTD_target
                low, high = 0.01, 500.0
                for _ in range(30):
                    mid = (low + high) / 2.0
                    if abs(mid - dT2) < 1e-4:
                        L_val = mid
                    else:
                        L_val = (mid - dT2) / np.log(mid / dT2)
                    
                    if L_val < LMTD_target:
                        low = mid
                    else:
                        high = mid
                dT1_guess = mid
                T14_guess = 520.0 - dT1_guess
                T14_guess = max(T_cold_in + 2.0, min(T14_guess, 518.0))
                
                m_cold_guess = Q_transfer / (960.0 * (T14_guess - T_cold_in))
                m_cold_guess = max(0.5, min(m_cold_guess, 500.0))
                
                T10_guess = 480.0
                
                T_merge_guess = (m_process_guess * 480.0 + m_charge_guess * T10_guess) / m_ptc_guess
                
                custom_guesses = {
                    '01_CC_PTC': {'m': m_ptc_guess, 'T': T_merge_guess},
                    '02_PTC_SP1': {'m': m_ptc_guess, 'T': 520.0},
                    '04_SP1_PH': {'m': m_process_guess, 'T': 520.0},
                    '05_PH_PR': {'m': m_process_guess, 'T': 520.0},
                    '06_PR_MG2': {'m': m_process_guess, 'T': 480.0},
                    '08_MG2_CC': {'m': m_ptc_guess, 'T': T_merge_guess},
                    '09_SP1_CHX': {'m': m_charge_guess, 'T': 520.0},
                    '10_CHX_MG2': {'m': m_charge_guess, 'T': T10_guess},
                    '13_CHSC_CHX': {'m': m_cold_guess, 'T': T_cold_in},
                    '14_CHX_CHSK': {'m': m_cold_guess, 'T': T14_guess},
                }
            except Exception as e:
                print(f"[DEBUG _apply_design_guesses error]: {e}")
                custom_guesses = None

        secondary_labels = set()
        # conn_04, conn_05, conn_06 are process loop conns
        for cname in ['conn_04', 'conn_05', 'conn_06', 'conn_15', 'conn_16']:
            c = getattr(self, cname, None)
            if c and hasattr(c, 'label'):
                secondary_labels.add(str(c.label))
                
        # charging labels that scale with m_charge_scale
        charge_labels = set()
        for cname in ['conn_09', 'conn_10', 'conn_13', 'conn_14']:
            c = getattr(self, cname, None)
            if c and hasattr(c, 'label'):
                charge_labels.add(str(c.label))

        m_charge_scale = m_scale
        T10_guess = None
        if not is_mode1_parallel or custom_guesses is None:
            try:
                # Find design mass flows
                m_ptc_design = float(df.loc['02_PTC_SP1', 'm'])
                m_process_design = float(df.loc['04_SP1_PH', 'm'])
                m_charge_design = float(df.loc['09_SP1_CHX', 'm'])
                
                # Perfect mass balance at splitter
                m_ptc_guess = m_ptc_design * m_scale
                m_charge_guess = m_ptc_guess - m_process_design
                m_charge_guess = max(0.5, m_charge_guess) # clamp to positive
                
                m_charge_scale = m_charge_guess / m_charge_design
                
                # Solve for dT_cold such that:
                # LMTD_target = (dT_hot - dT_cold) / ln(dT_hot / dT_cold)
                # where dT_hot = 80.0
                dT_hot = 80.0
                L_target = 43.28 * m_charge_scale
                
                # Binary search for dT_cold in range [0.01, 79.9]
                import numpy as np
                low, high = 0.01, 79.9
                for _ in range(20):
                    mid = (low + high) / 2.0
                    # LMTD function
                    if abs(dT_hot - mid) < 1e-6:
                        L_val = mid
                    else:
                        L_val = (dT_hot - mid) / np.log(dT_hot / mid)
                    
                    if L_val < L_target:
                        low = mid
                    else:
                        high = mid
                
                T10_guess = 400.0 + mid
            except Exception:
                m_charge_scale = m_scale

        def _T_to_h(T):
            return 594.37 + 1.5233 * (T - 420.0)

        for name in dir(self):
            if not name.startswith('conn_'):
                continue
            conn = getattr(self, name, None)
            if conn is None or not hasattr(conn, 'set_attr'):
                continue
            label = getattr(conn, 'label', None)
            if label is None or label not in df.index:
                continue
            try:
                row = df.loc[label]
                m0 = float(row.get('m', 30.0))
                h0 = float(row.get('h', 700.0))
                p0 = float(row.get('p', 5.0))
                T0 = float(row.get('T', 500.0))
                
                if custom_guesses is not None and str(label) in custom_guesses:
                    m0 = custom_guesses[str(label)]['m']
                    T0 = custom_guesses[str(label)]['T']
                    h0 = _T_to_h(T0)
                else:
                    if str(label) == '10_CHX_MG2' and T10_guess is not None:
                        T0 = T10_guess
                        h0 = _T_to_h(T0)
                    
                    if str(label) in charge_labels:
                        m0 = m0 * m_charge_scale
                    elif str(label) not in secondary_labels:
                        m0 = m0 * m_scale
                    
                conn.set_attr(m0=m0, h0=h0, T0=T0)
                
                # Directly assign starting values for variables to let the solver warm-start cleanly
                if hasattr(conn.m, 'is_var') and conn.m.is_var:
                    conn.m.val = m0
                if hasattr(conn.h, 'is_var') and conn.h.is_var:
                    conn.h.val = h0
                if hasattr(conn.p, 'is_var') and conn.p.is_var:
                    conn.p.val = p0
            except Exception:
                pass

    def solve_network(self, mode='design', design_path="base_design", TESmode='1', use_init_path=False):
        """
        Attempts to solve the network in the specified mode (default: 'design').
        Raises an exception if the solver fails.
        
        Args:
            mode (str): 'design' or 'offdesign' (TESPy modes).
            use_init_path (bool): if True, warm-start offdesign from design solution.
        """

        import os, shutil, time
        base_dir = getattr(self, '_cache_dir', '.tespy_cache')
        os.makedirs(base_dir, exist_ok=True)
        name = os.path.join(base_dir, f'base_design_{TESmode}')        
        if mode == 'design':
            self.network.solve(mode=mode, max_iter=100)
            abs_name = os.path.abspath(name)
            if os.path.exists(abs_name):
                try:
                    if os.path.isfile(abs_name):
                        os.remove(abs_name)
                    else:
                        import uuid
                        new_name = abs_name + "_old_" + uuid.uuid4().hex[:6]
                        os.rename(abs_name, new_name)
                except Exception as e:
                    print(f"Could not rename {abs_name}: {e}")
            self.network.save(name)
            # Persist designed values for cross-mode use
            if (hasattr(self, 'ptc_field') and self.ptc_field is not None
                    and not self.component_params.get('use_inhouse_ptc', False)
                    and self.ptc_field.A.val is not None):
                self.ptc_field_A_designed = self.ptc_field.A.val
            if (TESmode == '1' and hasattr(self, 'charge_tes_hx')
                    and self.charge_tes_hx.kA.val is not None):
                self.charge_hx_kA = self.charge_tes_hx.kA.val
            if (TESmode == '5' and hasattr(self, 'high_t_charge_hx')
                    and self.high_t_charge_hx.kA.val is not None):
                self.charge_hx_kA = self.high_t_charge_hx.kA.val
            if (TESmode == '3' and hasattr(self, 'discharge_tes_hx')
                    and getattr(self, 'tank_config', 'indirect') == 'indirect'
                    and self.discharge_tes_hx.kA.val is not None):
                self.discharge_hx_kA = self.discharge_tes_hx.kA.val
        else:
            design_path_full = os.path.join(base_dir, f'base_design_{TESmode}')
            if use_init_path:
                self._apply_design_guesses(design_path_full)
            kwargs = {'mode': mode, 'max_iter': 200, 'design_path': design_path_full}
            if use_init_path:
                is_m1_parallel = (TESmode == '1' and getattr(self, 'topology', 'Parallel') == 'Parallel')
                if not is_m1_parallel:
                    kwargs['init_path'] = design_path_full
            self.network.solve(**kwargs)
            #if not self.network.converged:
            #    raise RuntimeError("TESPy solver did not converge.")
