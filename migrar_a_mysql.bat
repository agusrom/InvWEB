@echo off
setlocal
title Migrar datos DNC de SQLite a MySQL

if not exist .env (
    echo Falta el archivo .env. Copia .env.example y completa DATABASE_URL.
    pause
    exit /b 1
)
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Este asistente NO crea bases, tablas ni columnas.
echo La estructura debe existir previamente en MySQL.
echo.
echo 1 - Verificar estructura y mostrar cantidades actuales
echo 2 - Copiar SQLite a un MySQL vacio ^(recomendado^)
echo 3 - BORRAR los datos DNC de MySQL y reemplazarlos por SQLite
set /p "MODO=Elegi una opcion [2]: "
if "%MODO%"=="1" goto :verificar
if "%MODO%"=="3" goto :reemplazar
goto :copiar

:verificar
python migrar_a_mysql.py --solo-verificar
goto :resultado

:copiar
set /p "ORIGEN=Ruta completa del archivo .db anterior: "
set "ORIGEN=%ORIGEN:"=%"
python migrar_a_mysql.py --origen "%ORIGEN%"
goto :resultado

:reemplazar
echo.
echo ATENCION: se borraran declaraciones, configuraciones y usuarios de MySQL.
set /p "CONFIRMACION=Escribi REEMPLAZAR para continuar: "
if not "%CONFIRMACION%"=="REEMPLAZAR" (
    echo Operacion cancelada.
    pause
    exit /b 1
)
set /p "ORIGEN=Ruta completa del archivo .db anterior: "
set "ORIGEN=%ORIGEN:"=%"
python migrar_a_mysql.py --origen "%ORIGEN%" --reemplazar-datos --confirmar-reemplazo REEMPLAZAR

:resultado
if errorlevel 1 goto :error
echo.
echo Proceso completado correctamente.
pause
exit /b 0

:error
echo.
echo No se completo el proceso. Revisa el mensaje anterior.
pause
exit /b 1
