import unittest
from laptop_full_controller import validate_response


class Packets(unittest.TestCase):
    def packet(self):return dict(seq=7,observed_ns=100,entered_ns=110,inferred_ns=120,sent_ns=130,residual=.04)
    def test_only_matching_original_request_accepted(self):
        validate_response(self.packet(),(7,100),140)
        for pending in (None,(6,100),(7,101)):
            with self.assertRaises(RuntimeError):validate_response(self.packet(),pending,140)
    def test_future_or_unordered_clock_values_rejected(self):
        for key,value in (('entered_ns',99),('sent_ns',141),('inferred_ns',109),('entered_ns',float('nan'))):
            p=self.packet();p[key]=value
            with self.assertRaises(RuntimeError):validate_response(p,(7,100),140)
    def test_nonfinite_or_unbounded_residual_rejected(self):
        for value in (float('nan'),float('inf'),-.081,.081):
            p=self.packet();p['residual']=value
            with self.assertRaises(RuntimeError):validate_response(p,(7,100),140)
    def test_malformed_response_rejected(self):
        for key in self.packet():
            p=self.packet();del p[key]
            with self.assertRaises(RuntimeError):validate_response(p,(7,100),140)
    def test_late_delivery_retained_for_gate_freshness_rejection(self):
        # Delivery is a valid event even when too old to authorize an action.
        validate_response(self.packet(),(7,100),1000000100)


if __name__=='__main__':unittest.main()
