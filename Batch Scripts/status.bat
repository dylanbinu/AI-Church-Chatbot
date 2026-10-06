@echo off
setlocal
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
if "%CHAT_FUNCTION_NAME%"=="" set CHAT_FUNCTION_NAME=church-bot-heritage
if "%UPDATER_FUNCTION_NAME%"=="" set UPDATER_FUNCTION_NAME=church-bot-updater
if "%FUNCTION_URL%"=="" set FUNCTION_URL=https://2h5pmesij2pbwj5iey7gweodpm0pfnxb.lambda-url.us-east-1.on.aws

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
curl -s "%FUNCTION_URL%/health?church_id=heritage"
echo.
echo.
pause
endlocal
