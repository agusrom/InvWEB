@echo off
setlocal
if not exist .env (
    echo.
    echo ============================================================
    echo  FALTA LA CONFIGURACION DE ESTA INSTALACION
    echo ============================================================
    echo.
    echo No se inicio el sistema para evitar cargar datos de prueba.
    echo.
    echo Copia .env.example como .env, configura MySQL y ejecuta:
    echo   migrar_a_mysql.bat
    echo.
    pause
    exit /b 1
)
if not exist .venv (
    py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo No se pudieron instalar las dependencias.
    pause
    exit /b 1
)
python app.py
pause
