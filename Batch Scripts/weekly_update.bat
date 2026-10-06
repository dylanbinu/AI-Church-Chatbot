@echo off
setlocal
cd /d "%~dp0.."

if not exist "venv\Scripts\activate.bat" (
  echo [ERROR] Create a venv first: python -m venv venv
  exit /b 1
)
call venv\Scripts\activate.bat

set CHURCH_ID=%1
if "%CHURCH_ID%"=="" set CHURCH_ID=heritage

echo ==================================================
echo   Weekly / on-demand data update: %CHURCH_ID%
echo   (scrape -^> ingest -^> validate -^> S3 if configured)
echo ==================================================

python code\updater.py --church_id %CHURCH_ID% %2 %3
if errorlevel 1 (
  echo [ERROR] Update failed.
  exit /b 1
)

echo Done.
endlocal
