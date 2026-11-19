@echo off
rem Builds the site and opens it at http://localhost:8090 (close this window to stop).
cd /d "%~dp0"
if not exist node_modules call npm install
call npm run build:js || (echo Script build failed. & pause & exit /b 1)
python build.py || (echo Build failed. & pause & exit /b 1)
start "" http://localhost:8090
python -m http.server 8090 --directory _site
