@echo off
echo ==================================================
echo   HERITAGE CHURCH DEPLOYMENT SCRIPT 🚀
echo ==================================================

:: Move to Project Root
pushd ..

echo [0/3] Authenticating with AWS ECR...
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 762297409734.dkr.ecr.us-east-1.amazonaws.com
if %errorlevel% neq 0 (
    echo [ERROR] AWS Login failed! Check your credentials.
    pause
    popd
    exit /b %errorlevel%
)
echo.

echo [1/3] Building Docker Image (church-chatbot:heritage-church)...
docker build -t church-chatbot:heritage-church .
if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    pause
    popd
    exit /b %errorlevel%
)

echo.
echo [2/3] Tagging Image for AWS ECR...
docker tag church-chatbot:heritage-church 762297409734.dkr.ecr.us-east-1.amazonaws.com/church-chatbot-heritage:latest
if %errorlevel% neq 0 (
    echo [ERROR] Tag failed!
    pause
    popd
    exit /b %errorlevel%
)

echo.
echo [3/3] Pushing Image to AWS ECR...
docker push 762297409734.dkr.ecr.us-east-1.amazonaws.com/church-chatbot-heritage:latest
if %errorlevel% neq 0 (
    echo [ERROR] Push failed!
    pause
    popd
    exit /b %errorlevel%
)

echo.
echo ==================================================
echo   SUCCESS! The image is in the cloud. ☁️
echo ==================================================
echo   REMINDER: Go to AWS Lambda Console and click "Update Code" -> "Deploy Image" to finish.
echo.

:: Return to original directory
popd
pause
