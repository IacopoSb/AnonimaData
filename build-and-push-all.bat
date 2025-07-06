@echo off

cd ./backend/anonymizer
docker build -t gcr.io/gruppo-3-456912/anonymizer:latest .
if %errorlevel% neq 0 (
    echo "Error building anonymizer image"
    exit /b %errorlevel%
)
cd ../orchestratore
docker build -t gcr.io/gruppo-3-456912/orchestratore:latest .
if %errorlevel% neq 0 (
    echo "Error building orchestratore image"
    exit /b %errorlevel%
)
cd ../formatter
docker build -t gcr.io/gruppo-3-456912/formatter:latest .
if %errorlevel% neq 0 (
    echo "Error building formatter image"
    exit /b %errorlevel%
)
@REM cd ../../frontend
@REM docker build -t gcr.io/gruppo-3-456912/frontend:latest .
@REM if %errorlevel% neq 0 (
@REM     echo "Error building frontend image"
@REM     exit /b %errorlevel%
@REM )

docker push gcr.io/gruppo-3-456912/anonymizer:latest
docker push gcr.io/gruppo-3-456912/orchestratore:latest
docker push gcr.io/gruppo-3-456912/formatter:latest
@REM docker push gcr.io/gruppo-3-456912/frontend:latest

