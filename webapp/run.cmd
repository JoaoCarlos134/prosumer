@echo off
rem The prosumer site on this computer: makes .venv (first time), installs the library and the server,
rem builds the page when npm is there, serves on http://127.0.0.1:8080 (or the next free port) and opens
rem the browser. Delete .venv\installed.txt to reinstall (after a pull that changed the dependencies).
rem Close this window to stop it.
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo Creating .venv ...
  py -3.12 -m venv .venv 2>nul || python -m venv .venv || goto :fail
)
rem installed only when it last finished (a failed install is tried again next time)
if not exist .venv\installed.txt (
  .venv\Scripts\python.exe -m pip install --upgrade pip >nul
  .venv\Scripts\python.exe -m pip install -e "..[lightgbm,net,fronius]" -r requirements.txt || goto :fail
  echo %date% %time% > .venv\installed.txt
)

where npm >nul 2>nul
if %errorlevel%==0 (
  pushd web
  if not exist node_modules call npm install || (popd & goto :fail)
  call npm run build || (popd & goto :fail)
  popd
) else (
  if not exist web\dist\index.html (
    echo npm not found and the page is not built: install Node.js 20+ ^(https://nodejs.org^) and run again.
    goto :fail
  )
  echo npm not found: serving the page built before.
)

rem the first free port from 8080; the browser opens when the server answers
.venv\Scripts\python.exe -m server.launch
goto :eof

:fail
echo.
echo Something failed above.
pause
exit /b 1
