@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

:: Builds TWO images (chat + updater), pushes to ECR, updates Lambdas.
:: Does NOT scrape church websites. Data updates: weekly_update.bat / updater Lambda.

if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
if "%AWS_ACCOUNT_ID%"=="" set AWS_ACCOUNT_ID=762297409734
if "%ECR_REPO%"=="" set ECR_REPO=church-chatbot-heritage
if "%CHAT_FUNCTION_NAME%"=="" set CHAT_FUNCTION_NAME=church-bot-heritage
if "%UPDATER_FUNCTION_NAME%"=="" set UPDATER_FUNCTION_NAME=church-bot-updater

set ECR_BASE=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%ECR_REPO%
set CHAT_IMAGE=%ECR_BASE%:chat
set UPDATER_IMAGE=%ECR_BASE%:updater
set LATEST_IMAGE=%ECR_BASE%:latest
set ECR_PASS=%TEMP%\ecr_login_password.txt

echo ==================================================
echo   CODE DEPLOY - slim chat + updater images
echo ==================================================
echo Region:      %AWS_REGION%
echo Chat image:  %CHAT_IMAGE%
echo Updater img: %UPDATER_IMAGE%
echo Chat FN:     %CHAT_FUNCTION_NAME%
echo Updater FN:  %UPDATER_FUNCTION_NAME%
echo.

where aws >NUL 2>&1
if errorlevel 1 (
  echo [ERROR] AWS CLI not found on PATH.
  goto :fail
)
where docker >NUL 2>&1
if errorlevel 1 (
  echo [ERROR] Docker not found. Start Docker Desktop first.
  goto :fail
)

echo [1/6] Logging into Amazon ECR...
aws ecr get-login-password --region %AWS_REGION% > "%ECR_PASS%"
if errorlevel 1 (
  echo [ERROR] Could not get ECR login password.
  goto :fail
)
for /f "usebackq delims=" %%p in ("%ECR_PASS%") do (
  docker login --username AWS --password "%%p" %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com
)
set LOGIN_ERR=%errorlevel%
del /f /q "%ECR_PASS%" >NUL 2>&1
if not "%LOGIN_ERR%"=="0" (
  echo [ERROR] Docker login to ECR failed.
  goto :fail
)

echo.
echo [2/6] Building SLIM chat image (Dockerfile.chat)...
docker build -f Dockerfile.chat -t church-chatbot:chat .
if errorlevel 1 goto :fail

echo.
echo [3/6] Building UPDATER image (Dockerfile.updater)...
docker build -f Dockerfile.updater -t church-chatbot:updater .
if errorlevel 1 goto :fail

echo.
echo [4/6] Pushing images to ECR...
docker tag church-chatbot:chat %CHAT_IMAGE%
docker tag church-chatbot:chat %LATEST_IMAGE%
docker tag church-chatbot:updater %UPDATER_IMAGE%
docker push %CHAT_IMAGE%
if errorlevel 1 goto :fail
docker push %LATEST_IMAGE%
if errorlevel 1 goto :fail
docker push %UPDATER_IMAGE%
if errorlevel 1 goto :fail

echo.
echo [5/6] Updating chat Lambda: %CHAT_FUNCTION_NAME%
aws lambda update-function-code --region %AWS_REGION% --function-name %CHAT_FUNCTION_NAME% --image-uri %CHAT_IMAGE%
if errorlevel 1 goto :fail
aws lambda wait function-updated --region %AWS_REGION% --function-name %CHAT_FUNCTION_NAME%
aws lambda update-function-configuration --region %AWS_REGION% --function-name %CHAT_FUNCTION_NAME% --timeout 60 --memory-size 1536 >NUL
aws lambda wait function-updated --region %AWS_REGION% --function-name %CHAT_FUNCTION_NAME%

echo.
echo [6/6] Updating updater Lambda: %UPDATER_FUNCTION_NAME%
aws lambda get-function --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME% >NUL 2>&1
if errorlevel 1 (
  echo [WARN] Updater "%UPDATER_FUNCTION_NAME%" does not exist yet.
  echo        Run: Batch Scripts\create_updater.bat
  echo        Chat image WAS deployed successfully.
) else (
  aws lambda update-function-code --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME% --image-uri %UPDATER_IMAGE%
  if errorlevel 1 goto :fail
  aws lambda wait function-updated --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME%
)

echo.
echo SUCCESS.
echo   Chat    handler: server.handler   image tag: chat
echo   Updater handler: updater.handler  image tag: updater
echo.
echo Next: open Function URL /health  OR  run create_updater.bat if needed.
echo.
pause
endlocal
exit /b 0

:fail
echo.
echo Deploy failed. See errors above.
if exist "%ECR_PASS%" del /f /q "%ECR_PASS%" >NUL 2>&1
echo.
pause
endlocal
exit /b 1
