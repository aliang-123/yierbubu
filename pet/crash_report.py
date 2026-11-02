"""崩溃诊断：捕获 Python 未捕获异常与 Windows 原生崩溃（含故障模块名），
写入 %TEMP%/yierbubu_crash.log，便于远程定位 0xC0000409 等原生崩溃的根因模块。

用法：在 main() 最开始调用 install_crash_report()。
"""
import os
import sys
import traceback

LOG_PATH = os.path.join(os.environ.get("TEMP") or ".", "yierbubu_crash.log")


def _log(line: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def install():
    # 1) Python 未捕获异常：记录完整 traceback，避免静默丢失
    _orig = sys.excepthook

    def _py_hook(etype, value, tb):
        _log("=== Python uncaught exception ===")
        _log("".join(traceback.format_exception(etype, value, tb)))
        if callable(_orig):
            try:
                _orig(etype, value, tb)
            except Exception:
                pass

    try:
        sys.excepthook = _py_hook
    except Exception:
        pass

    # 2) Windows 原生崩溃：用 SetUnhandledExceptionFilter 抓故障模块
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        psapi = getattr(ctypes.windll, "psapi", None)

        class EXCEPTION_RECORD(ctypes.Structure):
            _fields_ = [
                ("ExceptionCode", wintypes.DWORD),
                ("ExceptionFlags", wintypes.DWORD),
                ("ExceptionRecord", ctypes.c_void_p),
                ("ExceptionAddress", ctypes.c_void_p),
                ("NumberParameters", wintypes.DWORD),
                ("ExceptionInformation", wintypes.ULONG * 15),
            ]

        class EXCEPTION_POINTERS(ctypes.Structure):
            _fields_ = [
                ("ExceptionRecord", ctypes.POINTER(EXCEPTION_RECORD)),
                ("ContextRecord", ctypes.c_void_p),
            ]

        PEP = ctypes.POINTER(EXCEPTION_POINTERS)

        @ctypes.WINFUNCTYPE(ctypes.c_long, PEP)
        def _handler(exc_ptr):
            try:
                rec = exc_ptr.contents.ExceptionRecord.contents
                code = rec.ExceptionCode
                addr = rec.ExceptionAddress
                mod = "unknown"
                if psapi is not None:
                    hmod = wintypes.HANDLE()
                    # GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS = 0x4
                    if kernel32.GetModuleHandleExW(
                            0x4,
                            ctypes.cast(addr, wintypes.LPCWSTR),
                            ctypes.byref(hmod)):
                        buf = ctypes.create_unicode_buffer(520)
                        if psapi.GetModuleFileNameW(hmod, buf, 520):
                            mod = buf.value
                _log("=== Native crash ===")
                _log("ExceptionCode = 0x%08X" % code)
                _log("FaultingModule = %s" % mod)
                _log("FaultingAddress = %s" % addr)
            except Exception as e:  # pragma: no cover
                _log("crash handler internal error: %s" % e)
            return 0  # EXCEPTION_EXECUTE_HANDLER

        kernel32.SetUnhandledExceptionFilter(_handler)
        _log("crash_report: native handler installed; log -> %s" % LOG_PATH)
    except Exception as e:  # pragma: no cover
        _log("crash_report: native install failed: %s" % e)
