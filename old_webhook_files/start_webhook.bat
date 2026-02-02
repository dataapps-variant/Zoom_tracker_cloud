@echo off
cd /d C:\Users\shash\Downloads\zoom+tracker
start "Ngrok" ngrok http 5000
timeout /t 5
start "Webhook" python zoom_webhook_listener.py
echo Webhook started! This window will close.
timeout /t 3
