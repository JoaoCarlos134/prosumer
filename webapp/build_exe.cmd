@echo off
rem Builds the standalone site: dist\prosumer\prosumer.exe (one folder, nothing to install) and
rem dist\prosumer-site.zip. Needs Python 3.12 and Node.js 20+ on this machine; uses its own .venv-build.
setlocal
cd /d "%~dp0"

if not exist .venv-build\Scripts\python.exe (
  py -3.12 -m venv .venv-build 2>nul || python -m venv .venv-build || goto :fail
)
.venv-build\Scripts\python.exe -m pip install --upgrade pip >nul
.venv-build\Scripts\python.exe -m pip install "..[lightgbm,net,fronius]" fastapi uvicorn python-multipart pyinstaller || goto :fail

pushd web
call npm ci || (popd & goto :fail)
call npm run build || (popd & goto :fail)
popd

.venv-build\Scripts\python.exe -m PyInstaller --noconfirm prosumer_site.spec || goto :fail
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\prosumer -DestinationPath dist\prosumer-site.zip" || goto :fail
echo.
echo Built: dist\prosumer\prosumer.exe  (zip: dist\prosumer-site.zip)
goto :eof

:fail
echo.
echo The build failed above.
pause
exit /b 1
