/* SPDX-License-Identifier: MIT. Renamable GUI-subsystem Python launcher. */
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
#include <stdlib.h>
#include "version.h"
#define CAP 32768
static HANDLE launch_log=INVALID_HANDLE_VALUE;
static wchar_t log_path[CAP];
static void log_text(const wchar_t *text){
 if(launch_log==INVALID_HANDLE_VALUE)return;
 int size=WideCharToMultiByte(CP_UTF8,0,text,-1,NULL,0,NULL,NULL);
 if(size<=0)return;char *bytes=malloc(size);if(!bytes)return;
 if(WideCharToMultiByte(CP_UTF8,0,text,-1,bytes,size,NULL,NULL)){
  DWORD written;WriteFile(launch_log,bytes,(DWORD)size-1,&written,NULL);
 }
 free(bytes);
}
static void log_value(const wchar_t *name,const wchar_t *value){
 log_text(name);log_text(L": ");log_text(value);log_text(L"\r\n");
}
static void open_log(void){
 wchar_t temp[CAP];DWORD length=GetTempPathW(CAP,temp);
 if(!length||length>=CAP-128)return;
 wcscat(temp,L"DipTraceSchPluginAdapter");
 if(!CreateDirectoryW(temp,NULL)&&GetLastError()!=ERROR_ALREADY_EXISTS)return;
 SYSTEMTIME now;GetLocalTime(&now);
 swprintf(log_path,CAP,L"%ls\\launch-%04u%02u%02u-%02u%02u%02u-%03u-%lu.log",
          temp,now.wYear,now.wMonth,now.wDay,now.wHour,now.wMinute,now.wSecond,
          now.wMilliseconds,GetCurrentProcessId());
 launch_log=CreateFileW(log_path,FILE_APPEND_DATA|SYNCHRONIZE,
                       FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
 if(launch_log==INVALID_HANDLE_VALUE){log_path[0]=0;return;}
 log_text(ADAPTER_TITLE_W L"; API " ADAPTER_API_W L"; native launcher\r\n");
 log_value(L"Native command",GetCommandLineW());
 if(GetCurrentDirectoryW(CAP,temp))log_value(L"Inherited working directory",temp);
}
static void failure(const wchar_t *message,DWORD code,const wchar_t *kind){
 wchar_t number[64];swprintf(number,64,L"%lu",code);
 log_value(L"Error",message);log_value(kind,number);
 wchar_t *display=calloc(CAP+4096,sizeof(wchar_t));
 if(display){
  swprintf(display,CAP+4096,L"%ls\n%ls: %lu\n\nLaunch log: %ls",message,kind,code,
           *log_path?log_path:L"unavailable (could not create a file in TEMP)");
  MessageBoxW(NULL,display,ADAPTER_TITLE_W,MB_OK|MB_ICONERROR);free(display);
 }
}
static void error(const wchar_t *s){DWORD code=GetLastError();failure(s,code,L"Windows error");}
/* Read bootstrap executable from UTF-8/UTF-16LE INI; Python validates all keys. */
static void interpreter(const wchar_t *file,wchar_t *out){
 wcscpy(out,L"pyw.exe");
 HANDLE h=CreateFileW(file,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);
 if(h==INVALID_HANDLE_VALUE)return;
 DWORD size=GetFileSize(h,NULL),read=0;if(size>65536){CloseHandle(h);return;}
 char *b=calloc(size+4,1);wchar_t *text=calloc(size+4,sizeof(wchar_t));
 if(!b||!text){free(b);free(text);CloseHandle(h);return;}
 BOOL ok=ReadFile(h,b,size,&read,NULL);CloseHandle(h);if(!ok)goto done;
 if(size>=2&&(unsigned char)b[0]==255&&(unsigned char)b[1]==254)memcpy(text,b+2,size-2);
 else{int skip=size>=3&&(unsigned char)b[0]==239&&(unsigned char)b[1]==187&&(unsigned char)b[2]==191?3:0;
 if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,b+skip,(int)size-skip,text,size+1))goto done;}
 int section=0;wchar_t *state=NULL;
 for(wchar_t *line=wcstok(text,L"\r\n",&state);line;line=wcstok(NULL,L"\r\n",&state)){
  while(*line==L' '||*line==L'\t')line++;wchar_t *end=line+wcslen(line);
  while(end>line&&(end[-1]==L' '||end[-1]==L'\t'))*--end=0;
  if(*line==L'['){section=_wcsicmp(line,L"[python]")==0;continue;}
  if(!section||*line==L';'||*line==L'#')continue;
  wchar_t *eq=wcschr(line,L'=');if(!eq)continue;*eq=0;end=eq;
  while(end>line&&(end[-1]==L' '||end[-1]==L'\t'))*--end=0;
  if(_wcsicmp(line,L"executable"))continue;
  wchar_t *v=eq+1;while(*v==L' '||*v==L'\t')v++;
  if(*v&&wcslen(v)<CAP)wcscpy(out,v);
 }
 done:free(b);free(text);
}
/* CreateProcessW does not search PATH when lpApplicationName is supplied.
 * Resolve a bare executable name first, as required for py.exe/python.exe.
 * Explicit paths retain their existing meaning; no shell is involved. */
static int resolve_interpreter(wchar_t *exe){
 if(wcspbrk(exe,L"\\/:"))return 1;
 wchar_t *resolved=calloc(CAP,sizeof(wchar_t));
 if(!resolved){SetLastError(ERROR_NOT_ENOUGH_MEMORY);return 0;}
 DWORD length=SearchPathW(NULL,exe,L".exe",CAP,resolved,NULL);
 if(!length||length>=CAP){
  DWORD code=length>=CAP?ERROR_INSUFFICIENT_BUFFER:GetLastError();
  free(resolved);SetLastError(code);return 0;
 }
 wcscpy(exe,resolved);free(resolved);return 1;
}
/* CRT/CommandLineToArgvW quoting, including trailing slashes. */
static int quote(wchar_t *cmd,size_t *used,const wchar_t *arg){
 if(*used+3>=CAP)return 0;cmd[(*used)++]=L'"';
 while(*arg){size_t slashes=0;while(*arg==L'\\'){slashes++;arg++;}
 size_t count=(*arg==L'"'||!*arg)?slashes*2:slashes;
 if(*used+count+3>=CAP)return 0;while(count--)cmd[(*used)++]=L'\\';
 if(!*arg)break;if(*arg==L'"')cmd[(*used)++]=L'\\';cmd[(*used)++]=*arg++;}
 cmd[(*used)++]=L'"';cmd[(*used)++]=L' ';cmd[*used]=0;return 1;
}
int WINAPI wWinMain(HINSTANCE i,HINSTANCE p,PWSTR u,int s){
 (void)i;(void)p;(void)u;(void)s;
 open_log();
 int argc=0;wchar_t **argv=CommandLineToArgvW(GetCommandLineW(),&argc);
 if(argv&&argc==2&&!wcscmp(argv[1],L"--version")){
  MessageBoxW(NULL,ADAPTER_TITLE_W L"\nAPI " ADAPTER_API_W,
              ADAPTER_TITLE_W,MB_OK|MB_ICONINFORMATION);
  if(launch_log!=INVALID_HANDLE_VALUE)CloseHandle(launch_log);
  LocalFree(argv);return 0;
 }
 if(!argv||argc!=2){MessageBoxW(NULL,L"Run from DipTrace, or pass one exchange XML path.",ADAPTER_TITLE_W,MB_OK|MB_ICONERROR);if(argv)LocalFree(argv);return 2;}
 wchar_t *dir=calloc(CAP,sizeof(wchar_t)),*config=calloc(CAP,sizeof(wchar_t)),*host=calloc(CAP,sizeof(wchar_t)),*exe=calloc(CAP,sizeof(wchar_t)),*cmd=calloc(CAP,sizeof(wchar_t));
 if(!dir||!config||!host||!exe||!cmd)return 2;
 DWORD len=GetModuleFileNameW(NULL,dir,CAP);if(!len||len>=CAP-64){error(L"Executable path too long");return 2;}
 wchar_t *slash=wcsrchr(dir,L'\\');if(!slash)return 2;*slash=0;
 swprintf(config,CAP,L"%ls\\adapter.ini",dir);swprintf(host,CAP,L"%ls\\.adapter\\host.py",dir);
 if(GetFileAttributesW(config)==INVALID_FILE_ATTRIBUTES||GetFileAttributesW(host)==INVALID_FILE_ATTRIBUTES){error(L"Missing adapter.ini or .adapter\\host.py");return 2;}
 interpreter(config,exe);
 log_value(L"Configured interpreter",exe);
 if(!resolve_interpreter(exe)){
  DWORD code=GetLastError();wchar_t message[2048];
  swprintf(message,2048,L"Python executable was not found: %.1500ls\nCheck [python] executable in adapter.ini or use an absolute path.",exe);
  SetLastError(code);error(message);return 2;
 }
 log_value(L"Resolved interpreter",exe);
 log_value(L"Plugin directory",dir);
 wchar_t *base=wcsrchr(exe,L'\\');base=base?base+1:exe;
 size_t used=0;int ok=quote(cmd,&used,exe);
 /* The legacy py launcher parses its version selector from the raw command
  * line. Quoting "-3" can forward it to python.exe instead of selecting Python 3.
  * This fixed token needs no escaping; keep paths quoted below. */
 if(!_wcsicmp(base,L"pyw.exe")||!_wcsicmp(base,L"py.exe")){
  if(used+3>=CAP)ok=0;
  else{wcscpy(cmd+used,L"-3 ");used+=3;}
 }
 const wchar_t *args[]={host,L"--config",config,L"--exchange",argv[1]};
 for(int n=0;n<5;n++)ok=ok&&quote(cmd,&used,args[n]);
 if(!ok){error(L"Command line too long");return 2;}
 log_value(L"Python command",cmd);
 STARTUPINFOEXW si={0};si.StartupInfo.cb=sizeof(si);
 si.StartupInfo.dwFlags=STARTF_USESHOWWINDOW;si.StartupInfo.wShowWindow=SW_HIDE;
 PROCESS_INFORMATION pi={0};DWORD flags=CREATE_NO_WINDOW;BOOL inherit=FALSE;
 HANDLE child_log=INVALID_HANDLE_VALUE,input=INVALID_HANDLE_VALUE;
 HANDLE handles[2];
 if(launch_log!=INVALID_HANDLE_VALUE){
  SECURITY_ATTRIBUTES security={sizeof(security),NULL,TRUE};
  input=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,
                    &security,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
  if(input==INVALID_HANDLE_VALUE||!DuplicateHandle(GetCurrentProcess(),launch_log,
       GetCurrentProcess(),&child_log,0,TRUE,DUPLICATE_SAME_ACCESS)){
   error(L"Could not prepare Python diagnostic streams.");return 2;
  }
  SIZE_T size=0;InitializeProcThreadAttributeList(NULL,1,0,&size);
  si.lpAttributeList=malloc(size);
  handles[0]=input;handles[1]=child_log;
  if(!si.lpAttributeList||!InitializeProcThreadAttributeList(si.lpAttributeList,1,0,&size)||
     !UpdateProcThreadAttribute(si.lpAttributeList,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                               handles,sizeof(handles),NULL,NULL)){
   error(L"Could not restrict inherited diagnostic handles.");return 2;
  }
  si.StartupInfo.dwFlags|=STARTF_USESTDHANDLES;
  si.StartupInfo.hStdInput=input;si.StartupInfo.hStdOutput=child_log;si.StartupInfo.hStdError=child_log;
  flags|=EXTENDED_STARTUPINFO_PRESENT;inherit=TRUE;
 }else si.StartupInfo.cb=sizeof(STARTUPINFOW);
 BOOL started=CreateProcessW(exe,cmd,NULL,NULL,inherit,flags,NULL,dir,&si.StartupInfo,&pi);
 DWORD start_error=GetLastError();
 if(si.lpAttributeList){DeleteProcThreadAttributeList(si.lpAttributeList);free(si.lpAttributeList);}
 if(child_log!=INVALID_HANDLE_VALUE)CloseHandle(child_log);
 if(input!=INVALID_HANDLE_VALUE)CloseHandle(input);
 if(!started){SetLastError(start_error);error(L"Could not start the configured Python executable. Check [python] executable in adapter.ini.");return 2;}
 CloseHandle(pi.hThread);
 DWORD waited=WaitForSingleObject(pi.hProcess,INFINITE),code=1;
 if(waited!=WAIT_OBJECT_0||!GetExitCodeProcess(pi.hProcess,&code)){
  error(L"Could not obtain the Python process exit code.");CloseHandle(pi.hProcess);return 2;
 }
 CloseHandle(pi.hProcess);
 wchar_t number[64];swprintf(number,64,L"%lu",code);log_value(L"Python exit code",number);
 if(code)failure(L"The Python host exited with an error. See the launch log for its output.",code,L"Process exit code");
 else log_text(L"Host returned successfully. A job worker may still be running.\r\n");
 if(launch_log!=INVALID_HANDLE_VALUE)CloseHandle(launch_log);
 LocalFree(argv);free(dir);free(config);free(host);free(exe);free(cmd);return (int)code;
}
