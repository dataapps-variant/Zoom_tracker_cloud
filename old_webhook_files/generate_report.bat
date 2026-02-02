@echo off
cd /d C:\Users\shash\Downloads\zoom+tracker

REM Get yesterday's date (for reports)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set year=%datetime:~0,4%
set month=%datetime:~4,2%
set day=%datetime:~6,2%

REM Generate report for today
python generate_daily_report.py --date %year%-%month%-%day%

echo.
echo Report generated! Check the reports folder.
pause
