@echo off
setlocal
cd /d "%~dp0.."

if not exist "venv\Scripts\activate.bat" (
  echo Creating venv...
  python -m venv venv
)
call venv\Scripts\activate.bat

set CHURCH_ID=%1
if "%CHURCH_ID%"=="" set CHURCH_ID=heritage
set TARGET_URL=%2

if not "%TARGET_URL%"=="" (
  echo Custom URL scrape for %CHURCH_ID% at %TARGET_URL%
  if not exist ".runtime\%CHURCH_ID%" mkdir ".runtime\%CHURCH_ID%"
  python code\webscrape.py "%TARGET_URL%" --output_file ".runtime\%CHURCH_ID%\scraped_data.jsonl"
  if errorlevel 1 exit /b 1
  python code\ingest.py --church_id %CHURCH_ID% --input_file ".runtime\%CHURCH_ID%\scraped_data.jsonl" --reset
  if errorlevel 1 exit /b 1
) else (
  echo Building local bundle for registered church: %CHURCH_ID%
  python code\updater.py --church_id %CHURCH_ID% --dry-run
  if errorlevel 1 exit /b 1
)

echo.
echo Local data ready under .runtime\%CHURCH_ID%\
echo Start the API with Batch Scripts\launch_server.bat
endlocal
