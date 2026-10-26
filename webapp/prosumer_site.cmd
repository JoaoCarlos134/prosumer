@echo off
rem The prosumer site: the one launcher (Windows; close this window to stop the site).
rem   prosumer_site.cmd           runs the site; the first time it builds it, then runs it
rem   prosumer_site.cmd rebuild   builds again (after changing the page, the server or the library), then runs it
rem   prosumer_site.cmd dev       development: the API with --reload and the page with hot reload on :5173
rem Other arguments go to the site (--no-browser). The build needs Python 3.12 and Node.js 20+ and makes
rem dist\prosumer\ (prosumer.exe with Python, the library and the page): that folder runs by itself on any
rem Windows computer, nothing to install. The build's environment is .venv; PyInstaller's work files are in build\.
setlocal
cd /d "%~dp0"
set "EXE=dist\prosumer\prosumer.exe"
set "MODE=run"
set "ARGS="

:args
if "%~1"=="" goto :start
if /i "%~1"=="rebuild" (set "MODE=rebuild") else if /i "%~1"=="dev" (set "MODE=dev") else set "ARGS=%ARGS% %1"
shift
goto :args

:start
if "%MODE%"=="dev" goto :dev
if "%MODE%"=="rebuild" goto :build
if exist "%EXE%" goto :run

:build
echo Building the site (a few minutes; later runs start at once) ...
where npm >nul 2>nul || goto :no_node
call :install || goto :fail
pushd web
call npm ci || (popd & goto :fail)
call npm run build || (popd & goto :fail)
popd
.venv\Scripts\python.exe -m PyInstaller --noconfirm prosumer_site.spec || goto :fail_build
echo.
echo Built: %EXE%

:run
"%EXE%"%ARGS%
if errorlevel 1 pause
exit /b %errorlevel%

:dev
if not exist .venv\Scripts\python.exe call :install || goto :fail
where npm >nul 2>nul || goto :no_node
rem the library from ..\src, so a change there reloads the API without reinstalling
set "PYTHONPATH=%~dp0..\src"
start "prosumer API" .venv\Scripts\python.exe -m uvicorn server.api:app --port 8080 --reload --reload-dir server --reload-dir ..\src
pushd web
if not exist node_modules call npm ci
start "" http://127.0.0.1:5173
call npm run dev
popd
exit /b 0

:install
if not exist .venv\Scripts\python.exe (
  echo Creating .venv ...
  py -3.12 -m venv .venv 2>nul || python -m venv .venv || exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install "..[lightgbm,net,fronius]" -r requirements.txt pyinstaller || exit /b 1
rem the library itself again even when its version did not change: the build carries the code as it is now
.venv\Scripts\python.exe -m pip install --no-deps --force-reinstall .. >nul || exit /b 1
exit /b 0

:no_node
echo Node.js 20+ is needed to build the page: https://nodejs.org (then run this again).
goto :fail

:fail_build
echo.
echo PyInstaller failed. If the site is open in another window, close it and run "prosumer_site.cmd rebuild".
goto :fail

:fail
echo.
echo Something failed above.
pause
exit /b 1
