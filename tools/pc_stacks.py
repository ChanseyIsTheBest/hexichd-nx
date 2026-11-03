#!/usr/bin/env python3
"""hexichd-nx (2026-11-04): every thread's stack of a running renut.exe, through Windows' dbghelp and the build's PDB: what a hang is waiting on,
when a hung process writes no log and no crash file. Suspends each thread only while it is read.

  python tools/pc_stacks.py [--pid N] [--depth 14] [--skip-idle]
Without --pid it takes the only renut.exe running.
"""
import argparse
import ctypes
import ctypes.wintypes as w
import subprocess
import sys

k = ctypes.WinDLL('kernel32', use_last_error=True)
d = ctypes.WinDLL('dbghelp', use_last_error=True)
ALL = 0x1FFFFF
AMD64 = 0x8664
CONTEXT_FULL = 0x10000B
for name, restype in (('OpenProcess', w.HANDLE), ('OpenThread', w.HANDLE), ('CreateToolhelp32Snapshot', w.HANDLE)):
    getattr(k, name).restype = restype
d.SymFunctionTableAccess64.restype = ctypes.c_void_p
d.SymFunctionTableAccess64.argtypes = [w.HANDLE, ctypes.c_uint64]
d.SymGetModuleBase64.restype = ctypes.c_uint64
d.SymGetModuleBase64.argtypes = [w.HANDLE, ctypes.c_uint64]


class ThreadEntry(ctypes.Structure):
    _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD), ('th32ThreadID', w.DWORD), ('th32OwnerProcessID', w.DWORD),
                ('tpBasePri', w.LONG), ('tpDeltaPri', w.LONG), ('dwFlags', w.DWORD)]


class Address64(ctypes.Structure):
    _fields_ = [('Offset', ctypes.c_uint64), ('Segment', w.WORD), ('Mode', w.DWORD)]


class StackFrame64(ctypes.Structure):
    _fields_ = [('AddrPC', Address64), ('AddrReturn', Address64), ('AddrFrame', Address64), ('AddrStack', Address64),
                ('AddrBStore', Address64), ('FuncTableEntry', ctypes.c_void_p), ('Params', ctypes.c_uint64 * 4), ('Far', w.BOOL),
                ('Virtual', w.BOOL), ('Reserved', ctypes.c_uint64 * 3), ('KdHelp', ctypes.c_byte * 120)]


class SymbolInfo(ctypes.Structure):
    _fields_ = [('SizeOfStruct', w.ULONG), ('TypeIndex', w.ULONG), ('Reserved', ctypes.c_uint64 * 2), ('Index', w.ULONG), ('Size', w.ULONG),
                ('ModBase', ctypes.c_uint64), ('Flags', w.ULONG), ('Value', ctypes.c_uint64), ('Address', ctypes.c_uint64), ('Register', w.ULONG),
                ('Scope', w.ULONG), ('Tag', w.ULONG), ('NameLen', w.ULONG), ('MaxNameLen', w.ULONG), ('Name', ctypes.c_char * 512)]


def find_pid():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq renut.exe', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
    pids = [int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"renut.exe"')]
    if len(pids) != 1:
        sys.exit(f'pc_stacks: {len(pids)} renut.exe running: give --pid')
    return pids[0]


def threads(pid):
    snap = k.CreateToolhelp32Snapshot(4, 0)
    e = ThreadEntry()
    e.dwSize = ctypes.sizeof(e)
    out = []
    ok = k.Thread32First(w.HANDLE(snap), ctypes.byref(e))
    while ok:
        if e.th32OwnerProcessID == pid:
            out.append(e.th32ThreadID)
        ok = k.Thread32Next(w.HANDLE(snap), ctypes.byref(e))
    k.CloseHandle(w.HANDLE(snap))
    return out


def symbol(process, address):
    s = SymbolInfo()
    s.SizeOfStruct = 88  # the fixed part, as dbghelp means it
    s.MaxNameLen = 511
    disp = ctypes.c_uint64()
    if d.SymFromAddr(process, ctypes.c_uint64(address), ctypes.byref(disp), ctypes.byref(s)):
        return f'{s.Name.decode("latin-1")}+{disp.value:#x}'
    return f'{address:#x}'


def stack(process, tid, depth):
    thread = k.OpenThread(ALL, False, tid)
    if not thread:
        return [f'(could not open: {ctypes.get_last_error()})']
    k.SuspendThread(w.HANDLE(thread))
    frames = []
    try:
        raw = ctypes.create_string_buffer(1232 + 16)
        context = ctypes.addressof(raw) + (-ctypes.addressof(raw) & 15)
        ctypes.c_uint32.from_address(context + 0x30).value = CONTEXT_FULL
        if not k.GetThreadContext(w.HANDLE(thread), ctypes.c_void_p(context)):
            return [f'(no context: {ctypes.get_last_error()})']
        f = StackFrame64()
        f.AddrPC.Offset = ctypes.c_uint64.from_address(context + 0xF8).value
        f.AddrFrame.Offset = ctypes.c_uint64.from_address(context + 0xA0).value
        f.AddrStack.Offset = ctypes.c_uint64.from_address(context + 0x98).value
        f.AddrPC.Mode = f.AddrFrame.Mode = f.AddrStack.Mode = 3
        for _ in range(depth):
            if not d.StackWalk64(AMD64, process, w.HANDLE(thread), ctypes.byref(f), ctypes.c_void_p(context), None,
                                 d.SymFunctionTableAccess64, d.SymGetModuleBase64, None):
                break
            if not f.AddrPC.Offset:
                break
            frames.append(symbol(process, f.AddrPC.Offset))
    finally:
        k.ResumeThread(w.HANDLE(thread))
        k.CloseHandle(w.HANDLE(thread))
    return frames


IDLE = ('NtWaitForWorkViaWorkerFactory', 'TppWorkerThread')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int)
    ap.add_argument('--depth', type=int, default=14)
    ap.add_argument('--skip-idle', action='store_true', help='leave out the OS worker pool threads')
    a = ap.parse_args()
    pid = a.pid or find_pid()
    process = k.OpenProcess(ALL, False, pid)
    if not process:
        sys.exit(f'pc_stacks: cannot open {pid}: {ctypes.get_last_error()}')
    process = w.HANDLE(process)
    d.SymSetOptions(0x2 | 0x10 | 0x4)  # undecorated names, line numbers, deferred loads
    if not d.SymInitialize(process, None, True):
        sys.exit(f'pc_stacks: SymInitialize: {ctypes.get_last_error()}')
    ids = threads(pid)
    print(f'pid {pid}: {len(ids)} threads')
    for tid in ids:
        frames = stack(process, tid, a.depth)
        if a.skip_idle and any(x in frames[0] for x in IDLE if frames):
            continue
        print(f'-- thread {tid}')
        for i, frame in enumerate(frames):
            print(f'   #{i:02d} {frame}')
    d.SymCleanup(process)


if __name__ == '__main__':
    main()
