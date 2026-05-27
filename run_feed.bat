@echo off
:: Bloomberg Briefing Feed — one-click runner
::
:: Option A: Double-click this any time Bloomberg Terminal is open.
:: Option B: Drop this file into your Startup folder so it runs at login:
::           Win+R → type: shell:startup → paste this file there. No admin needed.
::
:: The 45-second delay below gives Bloomberg Terminal time to fully initialize
:: at login. Remove the timeout line if you're running it manually.

cd /d "%~dp0"
echo.
echo Bloomberg Briefing Feed
echo -----------------------

:: Skip weekends
for /f %%d in ('powershell -nologo -command "(Get-Date).DayOfWeek"') do set DOW=%%d
if /i "%DOW%"=="Saturday" (echo Skipping — weekend. & timeout /t 4 /nobreak >nul & exit)
if /i "%DOW%"=="Sunday"   (echo Skipping — weekend. & timeout /t 4 /nobreak >nul & exit)

:: Wait for Bloomberg Terminal to initialize (startup folder only — remove if manual)
echo Waiting 45s for Bloomberg Terminal to initialize...
timeout /t 45 /nobreak >nul

echo Fetching Bloomberg data...
python "%~dp0fetch_bloomberg.py"

echo.
echo Done. This window closes in 10 seconds.
timeout /t 10 /nobreak >nul
