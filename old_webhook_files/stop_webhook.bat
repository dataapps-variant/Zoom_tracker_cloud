@echo off
taskkill /FI "WINDOWTITLE eq Webhook*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Ngrok*" /F >nul 2>&1
taskkill /IM ngrok.exe /F >nul 2>&1
taskkill /IM python.exe /F >nul 2>&1
echo Webhook stopped!
timeout /t 2
