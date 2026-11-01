"""Windows isolation for the optional compatibility reader.

No network capabilities, private desktop, one-process job, bounded memory,
whitelisted inherited handles. Only task copies are accessible to the child.
"""
from __future__ import annotations
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import time
import uuid

K=c.WinDLL('kernel32',use_last_error=True)
A=c.WinDLL('advapi32',use_last_error=True)
U=c.WinDLL('userenv',use_last_error=True)
G=c.WinDLL('user32',use_last_error=True)

class SA(c.Structure):
    _fields_=[('nLength',w.DWORD),('lpSecurityDescriptor',c.c_void_p),('bInheritHandle',w.BOOL)]
class SI(c.Structure):
    _fields_=[('cb',w.DWORD),('lpReserved',w.LPWSTR),('lpDesktop',w.LPWSTR),('lpTitle',w.LPWSTR),
              ('dwX',w.DWORD),('dwY',w.DWORD),('dwXSize',w.DWORD),('dwYSize',w.DWORD),
              ('dwXCountChars',w.DWORD),('dwYCountChars',w.DWORD),('dwFillAttribute',w.DWORD),('dwFlags',w.DWORD),
              ('wShowWindow',w.WORD),('cbReserved2',w.WORD),('lpReserved2',c.c_void_p),
              ('hStdInput',w.HANDLE),('hStdOutput',w.HANDLE),('hStdError',w.HANDLE)]
class SIX(c.Structure):_fields_=[('StartupInfo',SI),('lpAttributeList',c.c_void_p)]
class PI(c.Structure):_fields_=[('hProcess',w.HANDLE),('hThread',w.HANDLE),('dwProcessId',w.DWORD),('dwThreadId',w.DWORD)]
class CAPS(c.Structure):_fields_=[('AppContainerSid',c.c_void_p),('Capabilities',c.c_void_p),('CapabilityCount',w.DWORD),('Reserved',w.DWORD)]
class BASIC(c.Structure):
    _fields_=[('PerProcessUserTimeLimit',c.c_longlong),('PerJobUserTimeLimit',c.c_longlong),('LimitFlags',w.DWORD),
              ('MinimumWorkingSetSize',c.c_size_t),('MaximumWorkingSetSize',c.c_size_t),('ActiveProcessLimit',w.DWORD),
              ('Affinity',c.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
class IO(c.Structure):_fields_=[(x,c.c_ulonglong) for x in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class LIMITS(c.Structure):_fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO),('ProcessMemoryLimit',c.c_size_t),('JobMemoryLimit',c.c_size_t),('PeakProcessMemoryUsed',c.c_size_t),('PeakJobMemoryUsed',c.c_size_t)]

def api(lib,name,args,ret=w.BOOL):
    f=getattr(lib,name);f.argtypes=args;f.restype=ret;return f
close=api(K,'CloseHandle',[w.HANDLE])
localfree=api(K,'LocalFree',[c.c_void_p],c.c_void_p)
create_profile=api(U,'CreateAppContainerProfile',[w.LPCWSTR,w.LPCWSTR,w.LPCWSTR,c.c_void_p,w.DWORD,c.POINTER(c.c_void_p)],c.c_long)
delete_profile=api(U,'DeleteAppContainerProfile',[w.LPCWSTR],c.c_long)
sid_string=api(A,'ConvertSidToStringSidW',[c.c_void_p,c.POINTER(w.LPWSTR)])
free_sid=api(A,'FreeSid',[c.c_void_p],c.c_void_p)
sd_convert=api(A,'ConvertStringSecurityDescriptorToSecurityDescriptorW',[w.LPCWSTR,w.DWORD,c.POINTER(c.c_void_p),c.POINTER(w.DWORD)])
open_token=api(A,'OpenProcessToken',[w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)])
token_info=api(A,'GetTokenInformation',[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)])
current=api(K,'GetCurrentProcess',[],w.HANDLE)
create_desktop=api(G,'CreateDesktopW',[w.LPCWSTR,w.LPCWSTR,c.c_void_p,w.DWORD,w.DWORD,c.POINTER(SA)],w.HANDLE)
close_desktop=api(G,'CloseDesktop',[w.HANDLE])
init_attrs=api(K,'InitializeProcThreadAttributeList',[c.c_void_p,w.DWORD,w.DWORD,c.POINTER(c.c_size_t)])
set_attr=api(K,'UpdateProcThreadAttribute',[c.c_void_p,w.DWORD,c.c_size_t,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p])
del_attrs=api(K,'DeleteProcThreadAttributeList',[c.c_void_p],None)
create_process=api(K,'CreateProcessW',[w.LPCWSTR,w.LPWSTR,c.c_void_p,c.c_void_p,w.BOOL,w.DWORD,c.c_void_p,w.LPCWSTR,c.POINTER(SIX),c.POINTER(PI)])
create_file=api(K,'CreateFileW',[w.LPCWSTR,w.DWORD,w.DWORD,c.POINTER(SA),w.DWORD,w.DWORD,w.HANDLE],w.HANDLE)
create_job=api(K,'CreateJobObjectW',[c.c_void_p,w.LPCWSTR],w.HANDLE)
set_job=api(K,'SetInformationJobObject',[w.HANDLE,c.c_int,c.c_void_p,w.DWORD])
assign_job=api(K,'AssignProcessToJobObject',[w.HANDLE,w.HANDLE])
terminate_job=api(K,'TerminateJobObject',[w.HANDLE,w.UINT])
terminate=api(K,'TerminateProcess',[w.HANDLE,w.UINT])
resume=api(K,'ResumeThread',[w.HANDLE],w.DWORD)
wait=api(K,'WaitForSingleObject',[w.HANDLE,w.DWORD],w.DWORD)
exit_code=api(K,'GetExitCodeProcess',[w.HANDLE,c.POINTER(w.DWORD)])

def check(ok,label):
    if not ok:raise OSError(c.get_last_error(),label+': '+c.FormatError(c.get_last_error()))
def sid_text(sid):
    out=w.LPWSTR();check(sid_string(sid,c.byref(out)),'SID string');s=out.value;localfree(out);return s
def user_sid():
    token=w.HANDLE();check(open_token(current(),8,c.byref(token)),'token')
    try:
        n=w.DWORD();token_info(token,1,None,0,c.byref(n));buf=c.create_string_buffer(n.value)
        check(token_info(token,1,buf,n,c.byref(n)),'token user')
        return sid_text(c.cast(buf,c.POINTER(c.c_void_p))[0])
    finally:close(token)


def acl(arguments):
    result = subprocess.run(['icacls.exe', *map(str, arguments)], capture_output=True,
                            creationflags=0x08000000)
    if result.returncode:
        raise OSError(f'无法设置读取副本的访问权限（{result.returncode}）。')


def run_reader(root: Path, alias: Path, progress, cancelled, timeout=240):
    """Run only the packaged emulator, after a mandatory isolation self-test."""
    inp, out = root / 'input', root / 'output'
    native_in, native_out = alias / 'input', alias / 'output'
    marker = root / 'outside-check.txt'
    marker.write_text('isolation check', encoding='ascii')
    profile = 'Textlight.Reader.' + uuid.uuid4().hex
    sid = c.c_void_p()
    job = desktop = descriptor = None
    handles = []
    profile_created = False
    processes = []

    def stop_if_cancelled():
        if cancelled and cancelled():
            raise InterruptedError('已取消提取。')

    try:
        hr = create_profile(profile, 'Textlight reader', 'Temporary compatibility reader',
                            None, 0, c.byref(sid))
        if hr:
            raise OSError(f'无法创建隔离环境（{hr & 0xffffffff:08x}）。')
        profile_created = True
        identity, owner = sid_text(sid), user_sid()
        acl([root, '/grant', f'*{owner}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F', '/T', '/Q'])
        # Keep normal per-user temp-directory traversal while protecting the sentinel.
        acl([marker, '/inheritance:r', '/Q'])
        for folder in (inp, out):
            acl([folder, '/grant', f'*{identity}:(OI)(CI)M', '/T', '/Q'])
            acl([folder, '/setintegritylevel', '(OI)(CI)L', '/T', '/Q'])
        sddl = f'D:(A;;GA;;;{owner})(A;;GA;;;SY)(A;;GA;;;{identity})S:(ML;;NW;;;LW)'
        descriptor = c.c_void_p()
        check(sd_convert(sddl, 1, c.byref(descriptor), None), 'desktop security')
        security = SA(c.sizeof(SA), descriptor, False)
        desktop_name = 'Textlight.' + uuid.uuid4().hex
        desktop = create_desktop(desktop_name, None, None, 0, 0x000f01ff, c.byref(security))
        check(desktop, 'private desktop')
        job = create_job(None, None)
        check(job, 'reader job')
        limits = LIMITS()
        limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x8 | 0x100 | 0x200
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        limits.ProcessMemoryLimit = limits.JobMemoryLimit = 3 * 1024**3
        check(set_job(job, 9, c.byref(limits), c.sizeof(limits)), 'reader limits')
        ui_limits = w.DWORD(0xff)
        check(set_job(job, 4, c.byref(ui_limits), c.sizeof(ui_limits)), 'reader UI limits')
        caps = CAPS(sid, None, 0, 0)
        env = {'SystemRoot': os.environ['SystemRoot'], 'WINDIR': os.environ['SystemRoot'],
               'PATH': str(Path(os.environ['SystemRoot']) / 'System32'),
               'TEMP': str(native_out / 'tmp'), 'TMP': str(native_out / 'tmp'),
               'USERPROFILE': str(native_out / 'profile'), 'APPDATA': str(native_out / 'profile'),
               'LOCALAPPDATA': str(native_out / 'profile'), 'TEXTLIGHT_OUTPUT': str(native_out),
               'TEXTLIGHT_OUTSIDE': str(alias / marker.name)}
        envbuf = c.create_unicode_buffer('\0'.join(k+'='+v for k, v in sorted(env.items()))+'\0')

        def spawn(args, log_name):
            inheritance = SA(c.sizeof(SA), None, True)
            log = create_file(str(out / log_name), 0x40000000, 1, c.byref(inheritance), 2, 0, None)
            check(log and log != c.c_void_p(-1).value, 'reader log')
            handles.append(log)
            stdin = create_file('NUL', 0x80000000, 3, c.byref(inheritance), 3, 0, None)
            check(stdin and stdin != c.c_void_p(-1).value, 'reader stdin')
            handles.append(stdin)
            inherited = (w.HANDLE * 2)(log, stdin)
            size = c.c_size_t()
            init_attrs(None, 2, 0, c.byref(size))
            attrs = c.create_string_buffer(size.value)
            check(init_attrs(attrs, 2, 0, c.byref(size)), 'reader attributes')
            try:
                check(set_attr(attrs, 0, 0x20009, c.byref(caps), c.sizeof(caps), None, None), 'reader capabilities')
                check(set_attr(attrs, 0, 0x20002, inherited, c.sizeof(inherited), None, None), 'reader handles')
                startup = SIX()
                startup.StartupInfo.cb = c.sizeof(SIX)
                startup.StartupInfo.lpDesktop = 'winsta0\\' + desktop_name
                startup.StartupInfo.dwFlags = 0x100
                startup.StartupInfo.hStdInput = stdin
                startup.StartupInfo.hStdOutput = startup.StartupInfo.hStdError = log
                startup.lpAttributeList = c.cast(attrs, c.c_void_p)
                command = c.create_unicode_buffer(subprocess.list2cmdline(list(map(str, args))))
                process = PI()
                check(create_process(str(args[0]), command, None, None, True,
                                     0x80000 | 0x400 | 4 | 0x08000000, envbuf, str(native_in / 'host'),
                                     c.byref(startup), c.byref(process)), 'start isolated reader')
                handles.extend((process.hProcess, process.hThread))
                processes.append(process.hProcess)
                if not assign_job(job, process.hProcess):
                    terminate(process.hProcess, 1)
                    check(False, 'assign reader job')
                check(resume(process.hThread) != 0xffffffff, 'resume reader')
                return process.hProcess
            finally:
                del_attrs(attrs)

        stop_if_cancelled()
        if progress:
            progress('正在准备隔离读取环境…')
        test = spawn([native_in / 'host/isolation_check.exe'], 'isolation.log')
        deadline = time.monotonic() + 15
        while wait(test, 100) != 0:
            stop_if_cancelled()
            if time.monotonic() > deadline:
                raise OSError('隔离环境检查超时，未开始读取游戏。')
        status = w.DWORD()
        check(exit_code(test, c.byref(status)), 'isolation status')
        if status.value:
            raise OSError('系统未通过隔离环境检查，未开始读取游戏。')
        process = spawn([
            native_in / 'host/boxedwine.exe', '-root', native_out / 'root', '-zip', native_in / 'wine.zip',
            '-mount', native_in / 'helpers', '/helpers', '-mount', native_in / 'game', '/home/username/.wine/drive_c/game',
            '-mount', native_out, '/output', '-w', '/home/username/.wine/drive_c/game',
            '-env', 'WINEDEBUG=-all', '-env', r'TEXTLIGHT_OUTPUT=Z:\output',
            '-env', 'WINEDLLOVERRIDES=mscoree,mshtml,winemenubuilder.exe,winevulkan=d;version=n,b',
            '-novideo', '-nosound', '/bin/wine', r'Z:\helpers\launcher.exe',
        ], 'reader.log')
        started = last_size_check = time.monotonic()
        while not (out / 'probe.done').is_file():
            stop_if_cancelled()
            if wait(process, 200) == 0:
                break
            now = time.monotonic()
            if now - started > timeout:
                raise OSError('增强读取超时，未取得可确认的完整数据。')
            if now - last_size_check > 2:
                last_size_check = now
                total, count = 0, 0
                for folder, dirs, files in os.walk(root, followlinks=False):
                    for name in files:
                        count += 1
                        try:
                            total += (Path(folder) / name).stat(follow_symlinks=False).st_size
                        except OSError:
                            pass
                        if total > 2 * 1024**3 or count > 25000:
                            raise OSError('兼容读取超出临时文件限制，已停止。')
                archives = list((out / 'dump').glob('*.rgss3a'))
                size = archives[0].stat().st_size if archives else 0
                if progress:
                    progress(f'正在读取封装数据 · {size / 1024**2:.1f} MB' if size
                             else f'正在读取封装数据 · {int(now-started)} 秒')
        if not (out / 'probe.done').is_file():
            raise OSError('兼容读取组件未取得数据，该封装暂不能自动读取。')
    finally:
        if job:
            terminate_job(job, 0)
            for process in processes:
                wait(process, 5000)
        for handle in reversed(handles):
            close(handle)
        if job:
            close(job)
        if desktop:
            close_desktop(desktop)
        if descriptor:
            localfree(descriptor)
        if profile_created:
            delete_profile(profile)
        if sid:
            free_sid(sid)
