@echo off
setlocal
cd /d %~dp0..

for /f %%i in ('".\.pyembed\python.exe" scripts\start_backend_detached.py') do set BACKEND_PID=%%i
echo Backend PID: %BACKEND_PID%
echo Frontend URL: http://127.0.0.1:8000/
echo Running backend HTTP check...
".\.pyembed\python.exe" scripts\check_backend_http.py
if errorlevel 1 (
  echo Backend check failed. Terminating PID %BACKEND_PID%...
  taskkill /PID %BACKEND_PID% /F /T >nul 2>nul
  exit /b 1
)
echo Backend strict startup check passed.
