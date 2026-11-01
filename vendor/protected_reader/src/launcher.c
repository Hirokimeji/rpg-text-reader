#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    STARTUPINFOA startup={0}; startup.cb=sizeof(startup); PROCESS_INFORMATION proc={0};
    char command[]="C:\\game\\Game.exe";
    if(!CreateProcessA(NULL,command,NULL,NULL,FALSE,0,NULL,"C:\\game",&startup,&proc)) {
        printf("CreateProcess failed: %lu\n",GetLastError());return 2;
    }
    printf("Started target pid=%lu\n",proc.dwProcessId);fflush(stdout);Sleep(2000);
    DWORD status;
    if(GetExitCodeProcess(proc.hProcess,&status) && status!=STILL_ACTIVE) {
        printf("Target exited before probe, status=%lu\n",status);return 3;
    }
    for(int i=0;i<180;i++) {
        if(GetFileAttributesA("Z:\\output\\probe.done")!=INVALID_FILE_ATTRIBUTES) break;
        if(GetExitCodeProcess(proc.hProcess,&status) && status!=STILL_ACTIVE) {
            printf("Target exited during probe, status=%lu\n",status);break;
        }
        Sleep(1000);
    }
    printf("Launcher finishing\n");fflush(stdout);
    TerminateProcess(proc.hProcess,0);CloseHandle(proc.hThread);CloseHandle(proc.hProcess);
    return 0;
}
