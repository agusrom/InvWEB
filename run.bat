@echo off
setlocal

if not exist .venv (
    echo No se encontro el entorno virtual .venv
    echo Ejecuta primero: py -m venv .venv
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
