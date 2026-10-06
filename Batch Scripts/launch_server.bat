@echo off
setlocal
cd /d "%~dp0.."

if not exist "requirements.txt" (
  echo [ERROR] requirements.txt missing in %CD%
  exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
  echo Creating venv...
  python -m venv venv
)
call venv\Scripts\activate.bat

if /I "%1"=="--setup" (
  echo Installing dependencies...
  pip install -r requirements.txt
)

if not exist ".runtime\heritage\chroma_db" (
  echo [WARN] No local heritage bundle found.
  echo Run: Batch Scripts\data_prep.bat heritage
)

echo.
echo Starting server at http://127.0.0.1:8004
echo Health: http://127.0.0.1:8004/health
echo.

cd code
..\venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8004
endlocal
