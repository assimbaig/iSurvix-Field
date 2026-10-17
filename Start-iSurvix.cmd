@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-iSurvix.ps1" %*
if errorlevel 1 pause
