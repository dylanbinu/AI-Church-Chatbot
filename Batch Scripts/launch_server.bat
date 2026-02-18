@echo off
:: The script is in "Batch Scripts" folder, so we use cd .. to get to project root

:: 1. Force the script to start in its own directory
cd /d "%~dp0"

:: 2. Move up one level to the Project Root
cd ..

ECHO ==========================================
ECHO          Current Folder: %CD%
ECHO ==========================================

:: 3. Verification Check (unchanged)
if not exist "requirements.txt" (
    ECHO [ERROR] requirements.txt missing!
    ECHO expected to find it in: %CD%
    pause
    exit /b
)

:: 4. Create Venv (unchanged)
if not exist "venv" (
    ECHO Creating venv...
    python -m venv venv
)

:: 5. Activate (unchanged)
call venv\Scripts\activate.bat

:: 6. Install (unchanged)
ECHO Installing/Updating libraries...
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m playwright install chromium

:: (CRITICAL FIX: We are now commenting out PYTHONPATH as it is unreliable)
:: set PYTHONPATH=%CD% 

:: 7. Launch FastAPI Server (The Brain)
ECHO.
ECHO ==============================================================
ECHO [7] Launching FastAPI Server (AI Church Chatbot)...
ECHO -> Open http://127.0.0.1:8003/docs for the API test page.
ECHO -> Open http://127.0.0.1:8003/ to chat!
ECHO ==============================================================
ECHO.

:: Check for the new application file
if exist "code\server.py" (
    :: FIRST, change directory to the 'code' folder
    cd code
    
    :: SECOND, run Uvicorn, now referencing the file directly (server:app)
    :: The path is resolved because we are inside the 'code' folder.
    ..\venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8003 --reload
    
    :: Move back up to the project root after server is closed (optional, but clean)
    cd ..
) else (
    ECHO [ERROR] Could not find code\server.py
    pause
)

:: 8. Catch Crashes
if %errorlevel% neq 0 pause