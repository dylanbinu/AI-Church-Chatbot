@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

:: Creates/updates an EventBridge Scheduler rule that invokes the updater Lambda weekly.
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
if "%AWS_ACCOUNT_ID%"=="" set AWS_ACCOUNT_ID=762297409734
if "%UPDATER_FUNCTION_NAME%"=="" set UPDATER_FUNCTION_NAME=church-bot-updater
if "%CHURCH_ID%"=="" set CHURCH_ID=heritage
if "%SCHEDULE_NAME%"=="" set SCHEDULE_NAME=church-bot-weekly-%CHURCH_ID%
if "%SCHEDULE_ROLE_NAME%"=="" set SCHEDULE_ROLE_NAME=church-bot-scheduler-role
if "%CRON%"=="" set CRON=cron(0 3 ? * MON *)
if "%TIMEZONE%"=="" set TIMEZONE=America/Detroit

set FUNCTION_ARN=arn:aws:lambda:%AWS_REGION%:%AWS_ACCOUNT_ID%:function:%UPDATER_FUNCTION_NAME%
set ROLE_ARN=arn:aws:iam::%AWS_ACCOUNT_ID%:role/%SCHEDULE_ROLE_NAME%

set TRUST=%TEMP%\church_scheduler_trust.json
set POLICY=%TEMP%\church_scheduler_policy.json
set TARGET=%TEMP%\church_scheduler_target.json
set FLEX=%TEMP%\church_scheduler_flex.json

> "%TRUST%" echo {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"scheduler.amazonaws.com"},"Action":"sts:AssumeRole"}]}
> "%POLICY%" echo {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"lambda:InvokeFunction","Resource":"%FUNCTION_ARN%"}]}
> "%FLEX%" echo {"Mode":"OFF"}
> "%TARGET%" echo {"RoleArn":"%ROLE_ARN%","Arn":"%FUNCTION_ARN%","Input":"{\"task\":\"weekly_update\",\"church_id\":\"%CHURCH_ID%\"}","RetryPolicy":{"MaximumEventAgeInSeconds":3600,"MaximumRetryAttempts":2}}

echo Ensuring IAM role %SCHEDULE_ROLE_NAME% ...
aws iam get-role --role-name %SCHEDULE_ROLE_NAME% >NUL 2>&1
if errorlevel 1 (
  aws iam create-role --role-name %SCHEDULE_ROLE_NAME% --assume-role-policy-document file://%TRUST%
)
aws iam put-role-policy --role-name %SCHEDULE_ROLE_NAME% --policy-name InvokeUpdater --policy-document file://%POLICY%

echo Creating / updating schedule %SCHEDULE_NAME% ...
aws scheduler get-schedule --name %SCHEDULE_NAME% --region %AWS_REGION% >NUL 2>&1
if errorlevel 1 (
  aws scheduler create-schedule --region %AWS_REGION% --name %SCHEDULE_NAME% --schedule-expression "%CRON%" --schedule-expression-timezone "%TIMEZONE%" --flexible-time-window file://%FLEX% --target file://%TARGET% --state ENABLED
) else (
  aws scheduler update-schedule --region %AWS_REGION% --name %SCHEDULE_NAME% --schedule-expression "%CRON%" --schedule-expression-timezone "%TIMEZONE%" --flexible-time-window file://%FLEX% --target file://%TARGET% --state ENABLED
)

echo.
echo Schedule ready: %SCHEDULE_NAME%
echo Payload: {"task":"weekly_update","church_id":"%CHURCH_ID%"}

if /I "%1"=="--invoke-now" (
  echo Invoking updater now...
  > "%TEMP%\church_update_payload.json" echo {"task":"weekly_update","church_id":"%CHURCH_ID%"}
  aws lambda invoke --region %AWS_REGION% --function-name %UPDATER_FUNCTION_NAME% --payload fileb://%TEMP%\church_update_payload.json "%TEMP%\church_update_result.json"
  type "%TEMP%\church_update_result.json"
)

endlocal
