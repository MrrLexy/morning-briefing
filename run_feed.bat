@echo off
:: Bloomberg Briefing Feed — run this any time Bloomberg Terminal is open.
cd /d "%~dp0"

for /f %%d in ('powershell -nologo -command "(Get-Date).DayOfWeek"') do set DOW=%%d
if /i "%DOW%"=="Saturday" (echo Skipping — weekend. & timeout /t 3 /nobreak >nul & exit)
if /i "%DOW%"=="Sunday"   (echo Skipping — weekend. & timeout /t 3 /nobreak >nul & exit)

echo Bloomberg Briefing Feed — %DATE% %TIME%
python "%~dp0fetch_bloomberg.py"

echo.
echo Done. Window closes in 5 seconds.
timeout /t 5 /nobreak >nul
