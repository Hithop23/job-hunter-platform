@echo off
title JOB-HUNTER-CO - Iniciar Sesion en Portales
echo ============================================================
echo   JOB-HUNTER-CO: NAVEGADOR DE AUTENTICACION Y SESIONES
echo ============================================================
echo Abriendo ventana de Chromium...
echo Inicia sesion en LinkedIn o en tu portal de empleo.
echo Cuando termines de iniciar sesion, simplemente cierra la ventana.
echo ============================================================
cd /d "%~dp0"
set TARGET_URL=%~1
if "%TARGET_URL%"=="" set TARGET_URL=https://www.linkedin.com/login
.\.venv\Scripts\python.exe launch_browser.py "%TARGET_URL%"
echo ============================================================
echo Proceso finalizado. Sesion guardada.
echo ============================================================
pause
