#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdarg.h>
#include <wchar.h>
#include <string.h>

static HANDLE (WINAPI *vopen)(LPCSTR,DWORD,DWORD,LPSECURITY_ATTRIBUTES,DWORD,DWORD,HANDLE);
static DWORD (WINAPI *vsize)(HANDLE,LPDWORD);
static BOOL (WINAPI *vread)(HANDLE,LPVOID,DWORD,LPDWORD,LPOVERLAPPED);
static BOOL (WINAPI *vclose)(HANDLE);
static HINSTANCE self_module;



static wchar_t output_base[1200]=L"Z:\\output";
static void logline(const char *fmt, ...) {
    wchar_t path[1500];swprintf(path,1500,L"%ls\\probe.log",output_base);
    FILE *file = _wfopen(path,L"ab");
    if (!file) return;
    va_list args; va_start(args, fmt); vfprintf(file, fmt, args); va_end(args);
    fputc('\n', file); fclose(file);
}

static int copy_data(const wchar_t *source, const wchar_t *target) {
    if (GetFileAttributesW(target) != INVALID_FILE_ATTRIBUTES) return 1;
    char source_a[1024];
    WideCharToMultiByte(CP_ACP,0,source,-1,source_a,sizeof(source_a),NULL,NULL);
    HANDLE in = vopen(source_a, GENERIC_READ, FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                           NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (in == INVALID_HANDLE_VALUE) {static int errors=0;if(errors++<20) logline("Input open failed %s error=%lu",source_a,GetLastError());return 0;}
    LARGE_INTEGER size;
    DWORD high=0; SetLastError(0); DWORD low=vsize(in,&high);
    size.QuadPart=((LONGLONG)high<<32)|low;
    if ((low==INVALID_FILE_SIZE && GetLastError()!=0) || size.QuadPart < 1 || size.QuadPart > 512LL*1024*1024) {
        vclose(in); return 0;
    }
    HANDLE out = CreateFileW(target, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_NEW, 0, NULL);
    if (out == INVALID_HANDLE_VALUE) { vclose(in); return 0; }
    char buffer[65536]; DWORD got, wrote; LONGLONG total=0; int ok=1;
    while (vread(in, buffer, sizeof(buffer), &got, NULL) && got) {
        if (!WriteFile(out, buffer, got, &wrote, NULL) || wrote != got) { ok=0; break; }
        total += got;
    }
    CloseHandle(out); vclose(in);
    if (!ok || total != size.QuadPart) { DeleteFileW(target); return 0; }
    logline("Copied %ls: %lld bytes", source, total);
    return 1;
}

static DWORD WINAPI worker(void *unused) {
    (void)unused;Sleep(6000);
    wchar_t folder[1500];
    GetEnvironmentVariableW(L"TEXTLIGHT_OUTPUT",output_base,1200);
    if(!output_base[0]) lstrcpyW(output_base,L"Z:\\output");
    swprintf(folder,1500,L"%ls\\dump",output_base);CreateDirectoryW(folder, NULL);
    swprintf(folder,1500,L"%ls\\dump\\Data",output_base);CreateDirectoryW(folder, NULL);
    logline("Compatibility reader attached");
    char cwd[1024];GetCurrentDirectoryA(sizeof(cwd),cwd);logline("Current directory=%s",cwd);
    HMODULE kernel=GetModuleHandleA("kernel32.dll");
    vopen=(void*)GetProcAddress(kernel,"CreateFileA");vsize=(void*)GetProcAddress(kernel,"GetFileSize");
    vread=(void*)GetProcAddress(kernel,"ReadFile");vclose=(void*)GetProcAddress(kernel,"CloseHandle");
    logline("Resolved input APIs open=%p size=%p read=%p close=%p",vopen,vsize,vread,vclose);
    const wchar_t *tables[] = {L"System",L"MapInfos",L"CommonEvents",L"Actors",L"Animations",
        L"Armors",L"Classes",L"Enemies",L"Items",L"Skills",L"States",L"Tilesets",L"Troops",L"Weapons",L"Scripts"};
    int found=0;
    for (int attempt=0; attempt<30; attempt++) {
        wchar_t src[260], dst[1500];
        for (int i=0; i<15; i++) {
            swprintf(src,260,L"Data\\%ls.rvdata2",tables[i]);
            swprintf(dst,1500,L"%ls\\dump\\Data\\%ls.rvdata2",output_base,tables[i]);
            found += copy_data(src,dst);
        }
        const wchar_t *archives[]={L"Game.rgss3a",L"Game.rgss2a",L"Game.rgssad"};
        for(int i=0;i<3;i++) {
            swprintf(dst,1500,L"%ls\\dump\\%ls",output_base,archives[i]);
            found += copy_data(archives[i],dst);
        }
        if(found) {
            int maps=0;
            for(int i=1;i<=999;i++) {
                swprintf(src,260,L"Data\\Map%03d.rvdata2",i);
                swprintf(dst,1500,L"%ls\\dump\\Data\\Map%03d.rvdata2",output_base,i);
                maps += copy_data(src,dst);
            }
            logline("Finished known-path pass: %d database/archive files, %d maps",found,maps);
            break;
        }
        if(attempt%5==0) logline("Waiting for virtual data, attempt=%d",attempt);
        Sleep(2000);
    }
    logline("Reader complete, found=%d",found);
    swprintf(folder,1500,L"%ls\\probe.done",output_base);
    HANDLE done=CreateFileW(folder,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
    if(done!=INVALID_HANDLE_VALUE) CloseHandle(done);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if(reason==DLL_PROCESS_ATTACH) {
        self_module=module;DisableThreadLibraryCalls(module);
        wchar_t process_path[2048];GetModuleFileNameW(NULL,process_path,2048);
        wchar_t *base=wcsrchr(process_path,L'\\');base=base?base+1:process_path;
        if(lstrcmpiW(base,L"Game.exe"))return TRUE;
        HANDLE thread=CreateThread(NULL,0,worker,NULL,0,NULL);
        if(thread) CloseHandle(thread);
    }
    return TRUE;
}

static FARPROC version_function(const char *name) {
 static HMODULE real=NULL;
 if(!real){wchar_t path[2048];GetSystemDirectoryW(path,2000);lstrcatW(path,L"\x5cversion.dll");real=LoadLibraryW(path);if(real==self_module)real=NULL;}
 return real?GetProcAddress(real,name):NULL;
}
BOOL WINAPI tl_info_a(LPCSTR f,DWORD h,DWORD n,LPVOID p){BOOL(WINAPI *fn)(LPCSTR,DWORD,DWORD,LPVOID)=(void*)version_function("GetFileVersionInfoA");return fn?fn(f,h,n,p):FALSE;}
BOOL WINAPI tl_info_w(LPCWSTR f,DWORD h,DWORD n,LPVOID p){BOOL(WINAPI *fn)(LPCWSTR,DWORD,DWORD,LPVOID)=(void*)version_function("GetFileVersionInfoW");return fn?fn(f,h,n,p):FALSE;}
DWORD WINAPI tl_size_a(LPCSTR f,LPDWORD h){DWORD(WINAPI *fn)(LPCSTR,LPDWORD)=(void*)version_function("GetFileVersionInfoSizeA");return fn?fn(f,h):0;}
DWORD WINAPI tl_size_w(LPCWSTR f,LPDWORD h){DWORD(WINAPI *fn)(LPCWSTR,LPDWORD)=(void*)version_function("GetFileVersionInfoSizeW");return fn?fn(f,h):0;}
BOOL WINAPI tl_query_a(LPCVOID b,LPCSTR s,LPVOID *p,PUINT n){BOOL(WINAPI *fn)(LPCVOID,LPCSTR,LPVOID*,PUINT)=(void*)version_function("VerQueryValueA");return fn?fn(b,s,p,n):FALSE;}
BOOL WINAPI tl_query_w(LPCVOID b,LPCWSTR s,LPVOID *p,PUINT n){BOOL(WINAPI *fn)(LPCVOID,LPCWSTR,LPVOID*,PUINT)=(void*)version_function("VerQueryValueW");return fn?fn(b,s,p,n):FALSE;}
