@echo off
rem Development: the API with --reload on :8080 (new window) and the page with hot reload on :5173.
rem Run run.cmd once first (it makes .venv and installs everything).
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run run.cmd first: it creates .venv.
  pause
  exit /b 1
)
start "prosumer API" .venv\Scripts\python.exe -m uvicorn server.api:app --port 8080 --reload --reload-dir server --reload-dir ..\src
pushd web
if not exist node_modules call npm install
start "" http://127.0.0.1:5173
call npm run dev
popd
