"""Per-process Windows high-resolution waitable timer, including Python3.10.

No busy spin or system-wide timer-resolution change. Unsupported APIs fail
explicitly; --timer legacy can reproduce the old time.sleep timing baseline.
"""
import ctypes
import sys
import time


class WindowsAPI:
    def __init__(self):
        from ctypes import wintypes
        self.lib=ctypes.WinDLL('kernel32',use_last_error=True)
        self.lib.CreateWaitableTimerExW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD]
        self.lib.CreateWaitableTimerExW.restype=wintypes.HANDLE
        self.lib.SetWaitableTimer.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_longlong),wintypes.LONG,ctypes.c_void_p,ctypes.c_void_p,wintypes.BOOL]
        self.lib.SetWaitableTimer.restype=wintypes.BOOL
        self.lib.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        self.lib.WaitForSingleObject.restype=wintypes.DWORD
        self.lib.CloseHandle.argtypes=[wintypes.HANDLE];self.lib.CloseHandle.restype=wintypes.BOOL
    def create(self):
        handle=self.lib.CreateWaitableTimerExW(None,None,0x2,0x00100002)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        return handle
    def wait(self,handle,relative_100ns):
        due=ctypes.c_longlong(relative_100ns)
        if not self.lib.SetWaitableTimer(handle,ctypes.byref(due),0,None,None,False):
            raise ctypes.WinError(ctypes.get_last_error())
        result=self.lib.WaitForSingleObject(handle,0xffffffff)
        if result==0xffffffff:raise ctypes.WinError(ctypes.get_last_error())
        if result!=0:raise OSError('unexpected timer wait status: '+str(result))
    def close(self,handle):
        if not self.lib.CloseHandle(handle):raise ctypes.WinError(ctypes.get_last_error())


class DeadlineWaiter:
    def __init__(self,mode='auto',platform_name=None,api=None,clock=None,sleeper=None):
        if mode not in ('auto','legacy'):raise ValueError('unknown timer mode')
        self.clock=clock or time.perf_counter_ns;self.sleeper=sleeper or time.sleep
        self.api=None;self.handle=None;self.closed=False
        platform_name=platform_name or sys.platform
        if platform_name=='win32' and mode=='auto':
            self.api=api or WindowsAPI()
            try:self.handle=self.api.create()
            except OSError as error:
                raise OSError('Windows high-resolution timer unavailable. No silent fallback. Use --timer legacy only for the old baseline. '+str(error)) from error
            self.backend='windows_high_resolution_waitable_timer'
        else:self.backend='legacy_time_sleep' if mode=='legacy' else 'platform_time_sleep'
    def wait_until_ns(self,target_ns):
        if self.closed:raise RuntimeError('timer is closed')
        remaining=int(target_ns)-self.clock()
        if remaining<=0:return
        if self.handle is not None:
            self.api.wait(self.handle,-((remaining+99)//100))
        else:self.sleeper(remaining/1e9)
    def close(self):
        if not self.closed:
            self.closed=True
            if self.handle is not None:
                handle=self.handle;self.handle=None;self.api.close(handle)
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
