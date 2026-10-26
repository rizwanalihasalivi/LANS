import unittest
from precision_wait import DeadlineWaiter

class FakeAPI:
    def __init__(self):self.waits=[];self.closes=[]
    def create(self):return 0x1234567812345678
    def wait(self,handle,due):self.waits.append((handle,due))
    def close(self,handle):self.closes.append(handle)

class TimerContracts(unittest.TestCase):
    def test_windows_uses_negative_relative_100ns_and_closes_once(self):
        api=FakeAPI()
        with DeadlineWaiter(platform_name='win32',api=api,clock=lambda:1000) as timer:
            timer.wait_until_ns(1101);timer.wait_until_ns(1000);timer.wait_until_ns(999)
        timer.close()
        self.assertEqual(api.waits,[(0x1234567812345678,-2)])
        self.assertEqual(api.closes,[0x1234567812345678])
        with self.assertRaises(RuntimeError):timer.wait_until_ns(1200)
    def test_wait_error_still_releases_handle(self):
        class Broken(FakeAPI):
            def wait(self,*_):raise OSError('injected wait failure')
        api=Broken()
        with self.assertRaises(OSError):
            with DeadlineWaiter(platform_name='win32',api=api,clock=lambda:0) as timer:timer.wait_until_ns(100)
        self.assertEqual(len(api.closes),1)
    def test_unsupported_highres_never_silently_falls_back(self):
        class Missing(FakeAPI):
            def create(self):raise OSError('unsupported')
        with self.assertRaisesRegex(OSError,'No silent fallback'):
            DeadlineWaiter(platform_name='win32',api=Missing())
    def test_legacy_mode_is_explicit_and_does_not_change_deadline(self):
        sleeps=[]
        with DeadlineWaiter('legacy',platform_name='win32',clock=lambda:200,sleeper=sleeps.append) as timer:
            timer.wait_until_ns(1_000_200)
            self.assertEqual(timer.backend,'legacy_time_sleep')
        self.assertEqual(sleeps,[.001])

if __name__=='__main__':unittest.main()
