@echo off
rem The prosumer site on this computer: makes .venv (first time), installs the library and the server,
rem builds the page when npm is there, opens the browser and serves on http://127.0.0.1:8080.
rem Close this window to stop it.
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo Creating .venv ...
  py -3.12 -m venv .venv 2>nul || python -m venv .venv || goto :fail
  .venv\Scripts\python.exe -m pip install --upgrade pip >nul
  .venv\Scripts\python.exe -m pip install -e "..[lightgbm,net,fronius]" -r requirements.txt || goto :fail
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

start "" http://127.0.0.1:8080
.venv\Scripts\python.exe -m uvicorn server.api:app --port 8080
goto :eof

:fail
echo.
echo Something failed above.
pause
exit /b 1
