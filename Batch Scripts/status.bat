@echo off
setlocal
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
if "%CHAT_FUNCTION_NAME%"=="" set CHAT_FUNCTION_NAME=church-bot-heritage
if "%UPDATER_FUNCTION_NAME%"=="" set UPDATER_FUNCTION_NAME=church-bot-updater
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b "FUNCTION_URL=" .env`) do (
    if "%%a"=="FUNCTION_URL" if "%FUNCTION_URL%"=="" set "FUNCTION_URL=%%b"
  )
)

echo ==================================================
echo   CHURCH BOT STATUS
echo ==================================================

echo.
echo [Lambda chat]
aws lambda get-function --region %AWS_REGION% --function-name %CHAT_FUNCTION_NAME% --query "{Status:Configuration.LastUpdateStatus,State:Configuration.State,Memory:Configuration.MemorySize,Timeout:Configuration.Timeout,Image:Code.ImageUri}" --output json

echo.
echo [Lambda updater]
aws lambda get-function --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME% --query "{Status:Configuration.LastUpdateStatus,State:Configuration.State,Memory:Configuration.MemorySize,Timeout:Configuration.Timeout,Image:Code.ImageUri}" --output json 2>NUL
if errorlevel 1 echo (updater not found yet)

echo.
echo [Health]
if "%FUNCTION_URL%"=="" (
  echo Set FUNCTION_URL in .env to check the chat address. Do not commit that file.
) else (
  curl -s "%FUNCTION_URL%/health?church_id=heritage"
  echo.
)
echo.
pause
endlocal
