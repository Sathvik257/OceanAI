"""Temporary execution settings for long local inference runs."""
import sys
from contextlib import contextmanager


@contextmanager
def keep_awake():
    """Prevent automatic Windows system sleep only for this process's active work."""
    kernel = None
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetThreadExecutionState.argtypes = [wintypes.DWORD]
        kernel.SetThreadExecutionState.restype = wintypes.DWORD
        if not kernel.SetThreadExecutionState(0x80000001):
            print('Could not request temporary sleep prevention; keep the PC awake manually.', file=sys.stderr)
    try:
        yield
    finally:
        if kernel:
            kernel.SetThreadExecutionState(0x80000000)
