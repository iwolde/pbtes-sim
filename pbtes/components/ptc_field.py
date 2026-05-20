import gc
from tespy.components.heat_exchangers.parabolic_trough import ParabolicTrough


class PTCField(ParabolicTrough):
    """
    A parabolic trough collector field composed of several parallel rows.

    This subclass internally divides the inlet mass flow among the rows,
    calculates as if there's only one row, and then scales Q, Qloss, etc.
    by the number of rows.
    """

    def __init__(self, label, rows=1, modules=1, **kwargs):
        super().__init__(label, **kwargs)
        self.rows = rows
        self.modules = modules
        self.pr_module = None

    def calc_parameters(self):
        """Override the parent's calculation to handle parallel rows cleanly."""
        # Find inlet and outlet connections natively using self.inl[0] and self.outl[0]
        i = self.inl[0]
        o = self.outl[0]

        # Calculate the total heat transfer rate (which is identical for the whole field or a single row scaled up)
        self.Q.val = i.m.val_SI * (o.h.val_SI - i.h.val_SI)
        self.pr.val = o.p.val_SI / i.p.val_SI
        
        # Scale flow for pressure loss calculations (zeta represents pressure drop coefficient of a single row)
        import numpy as np
        m_row = i.m.val_SI / self.rows
        self.zeta.val = (
            (i.p.val_SI - o.p.val_SI) * np.pi ** 2
            / (4 * (m_row) ** 2 * (i.vol.val_SI + o.vol.val_SI))
        )
        
        if self.energy_group.is_set:
            # Q_loss represents the total heat loss of the field
            self.Q_loss.val = - self.E.val * self.A.val + self.Q.val
            self.Q_loss.is_result = True
        else:
            self.Q_loss.is_result = False
