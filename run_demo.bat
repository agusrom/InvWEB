@echo off
setlocal
if not exist .venv (
    py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt

set "DATABASE_URL=sqlite:///demo_material_no_conforme.db"
set "PRODUCTIVE_DEMO_MODE=true"
set "AUXILIARY_DEMO_MODE=true"
set "SECRET_KEY=modo-demostracion-local"

echo.
echo Iniciando con datos de demostracion.
echo Esta opcion no consulta las bases productivas.
echo.
python app.py
pause
