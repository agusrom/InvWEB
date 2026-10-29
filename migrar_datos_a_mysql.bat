@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "scripts\migrar_analisis_a_mysql.py"
) else (
    python "scripts\migrar_analisis_a_mysql.py"
)

set "MIGRACION_EXIT=%ERRORLEVEL%"
echo.
if "%MIGRACION_EXIT%"=="0" (
    echo Migracion terminada correctamente.
) else (
    echo La migracion no termino correctamente. Revise el informe mostrado arriba.
)
pause
exit /b %MIGRACION_EXIT%
