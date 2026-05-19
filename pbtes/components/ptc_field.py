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
        """Override the parent's calculation to handle parallel rows."""
        # Find inlet connection
        if not hasattr(self, 'in_conn'):
            for _ in range(5):
                for obj in gc.get_objects():
                    if type(obj).__name__ == 'Connection' and getattr(obj, 'target', None) == self:
                        self.in_conn = obj
                        break
                if hasattr(self, 'in_conn'):
                    break
        total_m_in = self.in_conn.m.val_SI

        # Scale flow for a single-row calculation
        if self.rows > 1:
            self.in_conn.m.val_SI = total_m_in / self.rows

        # Run parent calculation
        super().calc_parameters()

        # Scale results back up
        if self.rows > 1:
            self.Q.val_SI *= self.rows
            if hasattr(self, 'Q_loss'):
                self.Q_loss.val_SI *= self.rows

        # Find outlet connection and restore total flow
        if not hasattr(self, 'out_conn'):
            for _ in range(5):
                for obj in gc.get_objects():
                    if type(obj).__name__ == 'Connection' and getattr(obj, 'source', None) == self:
                        self.out_conn = obj
                        break
                if hasattr(self, 'out_conn'):
                    break
        self.out_conn.m.val_SI = total_m_in
