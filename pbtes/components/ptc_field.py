from tespy.components.heat_exchangers.parabolic_trough import ParabolicTrough
from tespy.components import SimpleHeatExchanger


class PTCFieldParabolicTrough(ParabolicTrough):
    """
    The original ParabolicTrough-based PTCField subclass.
    """
    def __init__(self, label, rows=1, modules=1, **kwargs):
        super().__init__(label, **kwargs)
        self.rows = rows
        self.modules = modules
        self.pr_module = None

    def calc_parameters(self):
        """Override the parent's calculation to handle parallel rows cleanly."""
        i = self.inl[0]
        o = self.outl[0]

        # Calculate the total heat transfer rate
        self.Q.val = i.m.val_SI * (o.h.val_SI - i.h.val_SI)
        self.pr.val = o.p.val_SI / i.p.val_SI
        
        # Scale flow for pressure loss calculations
        import numpy as np
        m_row = i.m.val_SI / self.rows
        self.zeta.val = max(0.0, (
            (i.p.val_SI - o.p.val_SI) * np.pi ** 2
            / (4 * (m_row) ** 2 * (i.vol.val_SI + o.vol.val_SI))
        ))
        
        if self.energy_group.is_set:
            self.Q_loss.val = - self.E.val * self.A.val + self.Q.val
            self.Q_loss.is_result = True
        else:
            self.Q_loss.is_result = False


class PTCFieldSimpleHeatExchanger(SimpleHeatExchanger):
    """
    A SimpleHeatExchanger-based PTCField subclass.
    Bypasses internal non-linear parabolic trough calculation, allowing the
    in-house PTC model to prescribe outlet temperature and mass flow rate.
    """
    def __init__(self, label, rows=1, modules=1, **kwargs):
        super().__init__(label, **kwargs)
        self.rows = rows
        self.modules = modules
        self.inhouse_params = {}

    def set_attr(self, **kwargs):
        # Intercept parabolic trough specific parameters so they do not crash SimpleHeatExchanger
        custom_attrs = ['aoi', 'doc', 'Tamb', 'A', 'eta_opt', 'c_1', 'c_2', 'E', 'iam_1', 'iam_2']
        for attr in custom_attrs:
            if attr in kwargs:
                self.inhouse_params[attr] = kwargs.pop(attr)
        super().set_attr(**kwargs)


class PTCField:
    """
    Factory class that returns either the ParabolicTrough-based component
    or the SimpleHeatExchanger-based component depending on configuration.
    """
    def __new__(cls, label, rows=1, modules=1, use_inhouse_ptc=False, **kwargs):
        if use_inhouse_ptc:
            return PTCFieldSimpleHeatExchanger(label, rows=rows, modules=modules, **kwargs)
        else:
            # Pop use_inhouse_ptc so it doesn't crash the ParabolicTrough constructor
            kwargs.pop('use_inhouse_ptc', None)
            return PTCFieldParabolicTrough(label, rows=rows, modules=modules, **kwargs)
