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

ECHO.
ECHO --- Stabilizing Playwright Dependencies ---
:: Playwright browsers often get corrupted. Reinstalling them fixes most crashes.
    call venv\Scripts\python.exe -m pip install -r requirements.txt
    
    ECHO.
    
    :: --- Get URL Input ---
    SET target_url=
    SET /P target_url=Please enter the Church Website URL: 
    
    :: --- CRITICAL: URL EMPTY CHECK ---
    IF "%target_url%"=="" (
        ECHO.
        ECHO [ERROR] Input cannot be empty! Please provide a valid URL.
        PAUSE
        EXIT /B 1
    )
    
    ECHO.
    ECHO Target URL set to: %target_url%
    ECHO ----------------------------------------------------------
    
    :: Run the webscraping script, passing the URL as the first argument
    :: We use START /WAIT to ensure the batch script waits correctly for the python process
    :: Run the webscraping script directly so output is visible
    venv\Scripts\python.exe code\webscrape.py "%target_url%"
    IF ERRORLEVEL 1 (
        ECHO.
        ECHO Webscrape failed.
        PAUSE
        EXIT /B 1
    )


ECHO.
ECHO [2/2] Running Data Ingestion (ingest.py)...
ECHO (Converting scraped data to vector embeddings...)
ECHO.
ECHO [2/2] Running Data Ingestion (ingest.py)...
ECHO (Converting scraped data to vector embeddings...)
venv\Scripts\python.exe code\ingest.py --reset
IF ERRORLEVEL 1 (
    ECHO.
    ECHO Ingest failed. See error messages above.
    PAUSE
    EXIT /B 1
)

ECHO ----------------------------------------------------------
ECHO ✅ Data preparation complete! Database is updated.
ECHO --- You can now launch the API server via launch_server.bat ---

:: Keep the window open so you can see the results/logs
PAUSE