@echo off
rem Commits everything and pushes to GitHub. The site rebuilds itself in about a minute.
cd /d "%~dp0"
python build.py || (echo Build failed, nothing was published. & pause & exit /b 1)
git add -A
set /p MSG=What changed? (one line):
git commit -m "%MSG%"
git push
echo.
echo Pushed. Watch it deploy at https://github.com/ycgNem/ycgnem.github.io/actions
pause
