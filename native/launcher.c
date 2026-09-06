/* SPDX-License-Identifier: MIT. Renamable GUI-subsystem Python launcher. */
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
#include <stdlib.h>
#define CAP 32768
static void error(const wchar_t *s){wchar_t b[2048];swprintf(b,2048,L"%ls\nWindows error: %lu",s,GetLastError());MessageBoxW(NULL,b,L"DipTraceSchPluginAdapter",MB_OK|MB_ICONERROR);}
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
 int argc=0;wchar_t **argv=CommandLineToArgvW(GetCommandLineW(),&argc);
 if(!argv||argc!=2){MessageBoxW(NULL,L"Run from DipTrace, or pass one exchange XML path.",L"DipTraceSchPluginAdapter",MB_OK|MB_ICONERROR);if(argv)LocalFree(argv);return 2;}
 wchar_t *dir=calloc(CAP,sizeof(wchar_t)),*config=calloc(CAP,sizeof(wchar_t)),*host=calloc(CAP,sizeof(wchar_t)),*exe=calloc(CAP,sizeof(wchar_t)),*cmd=calloc(CAP,sizeof(wchar_t));
 if(!dir||!config||!host||!exe||!cmd)return 2;
 DWORD len=GetModuleFileNameW(NULL,dir,CAP);if(!len||len>=CAP-64){error(L"Executable path too long");return 2;}
 wchar_t *slash=wcsrchr(dir,L'\\');if(!slash)return 2;*slash=0;
 swprintf(config,CAP,L"%ls\\adapter.ini",dir);swprintf(host,CAP,L"%ls\\.adapter\\host.py",dir);
 if(GetFileAttributesW(config)==INVALID_FILE_ATTRIBUTES||GetFileAttributesW(host)==INVALID_FILE_ATTRIBUTES){error(L"Missing adapter.ini or .adapter\\host.py");return 2;}
 interpreter(config,exe);wchar_t *base=wcsrchr(exe,L'\\');base=base?base+1:exe;
 size_t used=0;int ok=quote(cmd,&used,exe);
 if(!_wcsicmp(base,L"pyw.exe")||!_wcsicmp(base,L"py.exe"))ok=ok&&quote(cmd,&used,L"-3");
 const wchar_t *args[]={host,L"--config",config,L"--exchange",argv[1]};
 for(int n=0;n<5;n++)ok=ok&&quote(cmd,&used,args[n]);
 if(!ok){error(L"Command line too long");return 2;}
 STARTUPINFOW si={0};si.cb=sizeof(si);si.dwFlags=STARTF_USESHOWWINDOW;si.wShowWindow=SW_HIDE;PROCESS_INFORMATION pi={0};
 if(!CreateProcessW(exe,cmd,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,dir,&si,&pi)){error(L"Could not start Python 3.11+. Set [python] executable in adapter.ini to pythonw.exe.");return 2;}
 CloseHandle(pi.hThread);WaitForSingleObject(pi.hProcess,INFINITE);DWORD code=1;GetExitCodeProcess(pi.hProcess,&code);CloseHandle(pi.hProcess);
 LocalFree(argv);free(dir);free(config);free(host);free(exe);free(cmd);return (int)code;
}
