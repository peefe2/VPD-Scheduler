@echo off
rem Double-click to run. Calls start.ps1 even where PowerShell scripts are blocked.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
