#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>

int main(void) {
    HANDLE token=NULL; DWORD ac=0,got=0;
    if(OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token)) {
        GetTokenInformation(token,TokenIsAppContainer,&ac,sizeof(ac),&got);CloseHandle(token);
    }
    wchar_t path[2048];
    GetEnvironmentVariableW(L"TEXTLIGHT_OUTSIDE",path,2048);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);
    DWORD read_error=file==INVALID_HANDLE_VALUE?GetLastError():0;
    if(file!=INVALID_HANDLE_VALUE) CloseHandle(file);
    file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);
    DWORD write_error=file==INVALID_HANDLE_VALUE?GetLastError():0;
    if(file!=INVALID_HANDLE_VALUE) CloseHandle(file);
    GetEnvironmentVariableW(L"TEXTLIGHT_OUTPUT",path,2000);
    lstrcatW(path,L"\\allowed-write.txt");
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
    DWORD allowed=file!=INVALID_HANDLE_VALUE;
    if(allowed) { DWORD n;WriteFile(file,"test",4,&n,NULL);CloseHandle(file); }
    WSADATA ws;WSAStartup(MAKEWORD(2,2),&ws);SOCKET s=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);
    u_long nonblock=1;ioctlsocket(s,FIONBIO,&nonblock);
    struct sockaddr_in addr={0};addr.sin_family=AF_INET;addr.sin_port=htons(443);addr.sin_addr.s_addr=inet_addr("1.1.1.1");
    int result=connect(s,(struct sockaddr*)&addr,sizeof(addr));int network=result==SOCKET_ERROR?WSAGetLastError():0;
    if(network==WSAEWOULDBLOCK) {
        fd_set error,write;FD_ZERO(&error);FD_ZERO(&write);FD_SET(s,&error);FD_SET(s,&write);
        struct timeval timeout={3,0};select(0,NULL,&write,&error,&timeout);int size=sizeof(network);
        getsockopt(s,SOL_SOCKET,SO_ERROR,(char*)&network,&size);
    }
    closesocket(s);WSACleanup();
    printf("APPCONTAINER=%lu READ_OUTSIDE=%lu WRITE_OUTSIDE=%lu WRITE_OUTPUT=%lu NETWORK=%d\n",ac,read_error,write_error,allowed,network);
    return (ac==1 && read_error==ERROR_ACCESS_DENIED && write_error==ERROR_ACCESS_DENIED && allowed && network==WSAEACCES)?0:7;
}
