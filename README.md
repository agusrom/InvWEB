# Sistema de Inventarios

Aplicación FastAPI para inventarios físicos, plantillas, programaciones,
conteo PC/móvil, análisis de stock, componentes y reportes.

## Estado de la migración

Se retiraron Conciliaciones antiguas y Warehouse/Depósito, incluidos sus modelos,
rutas y formularios. Los inventarios, registros, reconteos, plantillas,
programaciones y el Análisis de stock actual se conservan.

La migración total a MySQL todavía está en curso. La limpieza de tablas de
prueba es explícita y no se ejecuta al iniciar la aplicación. Seguí el
[procedimiento de migración y estandarización](docs/migracion_estandarizacion.md).

El esquema de gestión debe corresponder a una instalación existente v1.16.
Estas instrucciones no crean una base vacía. Los SQL históricos no constituyen
un instalador consolidado ni deben ejecutarse nuevamente en bloque.

## Desarrollo

Desde la raíz del repositorio, crear y activar un entorno Python:

```sh
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Configurar `.env` a partir de `.env.example`, con `DATABASE_URL` apuntando a la
base MySQL de gestión. `PRODUCTION_DATABASE_URL` es la conexión de consulta al
sistema productivo: debe tener permisos de solo lectura. Si queda vacía, se usa
el catálogo de demostración; eso no valida los datos ni la integración real.
No guardar credenciales en Git.

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

El arranque valida las tablas MySQL existentes. No crea ni migra ese esquema.
Los almacenes locales vigentes se inicializan según los módulos que los usan.

## Funciones vigentes

- Inventarios: vistas Pendientes, Por pieza, Detallada y Componentes.
- Plantillas mixtas y combinación de plantillas del mismo cliente.
- Conteo mediante registros, confirmación de cero y sincronización móvil.
- Calendario semanal, programaciones, cierres y reconteos.
- Análisis de stock, auditorías y exportaciones Excel/impresión.
- Notas del calendario: título, fecha, edición, cierre/reapertura y eliminación
  con confirmación. Si el guardado falla se conserva el texto.
- Búsqueda de plantillas por nombre o cliente sin perder selecciones.
- Progreso y confiabilidad juntos en el listado principal.

## Datos que se deben conservar y respaldar

| Ubicación | Contenido activo |
|---|---|
| MySQL de gestión | Inventarios, renglones, registros, plantillas, programaciones, cierres, reconteos y configuración |
| `data/inventarios_auxiliares.db` | Tipos de artículos, origen de plantillas combinadas y metadatos de registros |
| `data/notas_cronograma.db` | Notas del calendario |
| `data/preconciliacion_auditoria.sqlite3` | Análisis de stock guardados y auditorías |
| `data/preconciliacion_notas.json` | Notas y controles del análisis actual |

No borrar `data` ni copiar archivos WAL/SHM aisladamente como respaldo. Hasta
terminar la migración es necesario respaldar MySQL y los almacenes locales de
forma consistente, y comprobar la restauración.

## Verificaciones

```sh
python -m unittest discover -s tests -v
node --check app/static/js/app.js
```

Las pruebas unitarias no sustituyen la validación de MySQL real, concurrencia,
restauración y sincronización offline. La guía de migración detalla los pasos
pendientes y la inspección de clientes antes de normalizarlos.

El [historial de versiones](docs/historial_versiones.md) se conserva como
referencia, no como procedimiento operativo.
