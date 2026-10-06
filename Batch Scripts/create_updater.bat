@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

:: One-time: create the updater Lambda from the :updater ECR image.
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b "AWS_ACCOUNT_ID= S3_BUCKET_NAME=" .env`) do (
    if "%%a"=="AWS_ACCOUNT_ID" if "%AWS_ACCOUNT_ID%"=="" set "AWS_ACCOUNT_ID=%%b"
    if "%%a"=="S3_BUCKET_NAME" if "%S3_BUCKET_NAME%"=="" set "S3_BUCKET_NAME=%%b"
  )
)
if "%AWS_ACCOUNT_ID%"=="" (
  echo [ERROR] Set AWS_ACCOUNT_ID in .env or the environment. Do not commit that file.
  exit /b 1
)
if "%S3_BUCKET_NAME%"=="" (
  echo [ERROR] Set S3_BUCKET_NAME in .env or the environment. Do not commit that file.
  exit /b 1
)
if "%ECR_REPO%"=="" set ECR_REPO=church-chatbot-heritage
if "%CHAT_FUNCTION_NAME%"=="" set CHAT_FUNCTION_NAME=church-bot-heritage
if "%UPDATER_FUNCTION_NAME%"=="" set UPDATER_FUNCTION_NAME=church-bot-updater

set UPDATER_IMAGE=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%ECR_REPO%:updater

for /f "delims=" %%r in ('aws lambda get-function-configuration --region %AWS_REGION% --function-name %CHAT_FUNCTION_NAME% --query Role --output text') do set ROLE_ARN=%%r
if "%ROLE_ARN%"=="" (
  echo [ERROR] Could not read IAM role from %CHAT_FUNCTION_NAME%.
  pause
  exit /b 1
)

for /f "delims=" %%n in ('powershell -NoProfile -Command "'%ROLE_ARN%'.Split('/')[-1]"') do set ROLE_NAME=%%n

echo ==================================================
echo   CREATE UPDATER LAMBDA
echo ==================================================
echo Name:  %UPDATER_FUNCTION_NAME%
echo Image: %UPDATER_IMAGE%
echo Role:  %ROLE_ARN% (%ROLE_NAME%)
echo.

aws lambda get-function --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME% >NUL 2>&1
if not errorlevel 1 (
  echo Updater already exists. Updating code...
  aws lambda update-function-code --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME% --image-uri %UPDATER_IMAGE%
  aws lambda wait function-updated --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME%
) else (
  echo Creating function...
  aws lambda create-function --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME% --package-type Image --code ImageUri=%UPDATER_IMAGE% --role %ROLE_ARN% --timeout 900 --memory-size 3008 --architectures x86_64
  if errorlevel 1 (
    echo [ERROR] create-function failed. Push :updater via deploy_heritage.bat first.
    pause
    exit /b 1
  )
  aws lambda wait function-active --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME%
)

echo Configuring environment...
set ENV_FILE=%TEMP%\church_updater_env.json
aws lambda get-function-configuration --region %AWS_REGION% --function-name %CHAT_FUNCTION_NAME% --query "Environment.Variables" --output json > "%TEMP%\church_chat_env.json"
powershell -NoProfile -Command "$e=Get-Content '%TEMP%\church_chat_env.json' | ConvertFrom-Json; if ($null -eq $e) { $e = [pscustomobject]@{} }; if (-not $e.PSObject.Properties['CHAT_FUNCTION_NAME']) { $e | Add-Member CHAT_FUNCTION_NAME '%CHAT_FUNCTION_NAME%' } else { $e.CHAT_FUNCTION_NAME='%CHAT_FUNCTION_NAME%' }; if (-not $e.PSObject.Properties['S3_BUCKET_NAME'] -or -not $e.S3_BUCKET_NAME) { if (-not $e.PSObject.Properties['S3_BUCKET_NAME']) { $e | Add-Member S3_BUCKET_NAME '%S3_BUCKET_NAME%' } else { $e.S3_BUCKET_NAME='%S3_BUCKET_NAME%' } }; @{Variables=$e} | ConvertTo-Json -Compress | Set-Content -Encoding ascii '%ENV_FILE%'"

aws lambda update-function-configuration --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME% --timeout 900 --memory-size 3008 --environment file://%ENV_FILE%
aws lambda wait function-updated --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME%

echo Attaching IAM extras on role %ROLE_NAME% ...
set POLICY=%TEMP%\church_updater_inline.json
powershell -NoProfile -Command "@{Version='2012-10-17';Statement=@(@{Effect='Allow';Action=@('s3:GetObject','s3:PutObject','s3:ListBucket');Resource=@('arn:aws:s3:::%S3_BUCKET_NAME%','arn:aws:s3:::%S3_BUCKET_NAME%/*')},@{Effect='Allow';Action=@('lambda:UpdateFunctionConfiguration','lambda:GetFunctionConfiguration');Resource='arn:aws:lambda:%AWS_REGION%:%AWS_ACCOUNT_ID%:function:%CHAT_FUNCTION_NAME%'})} | ConvertTo-Json -Depth 6 | Set-Content -Encoding ascii '%POLICY%'"
aws iam put-role-policy --role-name %ROLE_NAME% --policy-name ChurchBotUpdaterExtras --policy-document file://%POLICY%
if errorlevel 1 echo [WARN] Attach S3 + UpdateFunctionConfiguration on the role manually if needed.

echo.
echo SUCCESS. Next:
echo   Batch Scripts\setup_schedule.bat
echo   Batch Scripts\setup_schedule.bat --invoke-now
echo.
pause
endlocal
exit /b 0
