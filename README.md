# Sistema de Inventarios

Aplicación FastAPI para inventarios físicos, plantillas, programaciones,
conteo PC/móvil, análisis de stock, componentes y reportes.

## Optimización de la portada

El listado carga 25 inventarios por página con filtros en servidor. El detalle
se solicita al abrir un inventario y el historial al desplegar su análisis.
Calendario y métricas globales se consultan independientemente del listado.
Esta mejora no requiere cambios de esquema ni ejecutar SQL de migración.
La migración de datos queda pospuesta; no ejecutar los SQL de limpieza como
parte de esta optimización.
Ver [alcance y validación de rendimiento](docs/rendimiento_portada.md).

## Estado de la migración

Se retiraron Conciliaciones antiguas y Warehouse/Depósito, incluidos sus modelos,
rutas y formularios. Los inventarios, registros, reconteos, plantillas,
programaciones y el Análisis de stock actual se conservan.

La migración total a MySQL todavía está en curso. La limpieza de tablas de
prueba es explícita y no se ejecuta al iniciar la aplicación. Seguí el
[procedimiento de migración y estandarización](docs/migracion_estandarizacion.md).

Si el usuario de la aplicación no tiene permisos DDL, entregar al administrador
[el SQL de la etapa 1](sql/etapa1_retirar_modulos_prueba.sql) y sus
[instrucciones](docs/ADMIN_ETAPA1_MYSQL.md). No requiere ejecutar Python ni
otorgarle privilegios administrativos al usuario operativo.

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

## Análisis de stock con conteo abierto

Se puede iniciar y guardar un análisis aunque el inventario final siga en conteo
(incluso sin códigos completos). Se muestra como **PROVISORIA**: los códigos
incompletos aparecen como pendientes, junto con sus movimientos y esperado.
El universo es la unión de piezas de ambos inventarios, explotadas a sus
componentes terminales; no se incorporan piezas ajenas desde los movimientos.
Los pendientes no se interpretan como físico cero ni participan de la confiabilidad.

El botón **Actualizar inventario final** relee el estado y los conteos guardados
y recalcula los mismos períodos iniciales. Si el análisis ya está guardado,
actualiza ese mismo registro sin cambiar su nombre ni duplicarlo; conserva las
notas y las correcciones de movimientos. Si el recálculo falla conserva la
fotografía anterior. Hay que terminar de guardar las notas y remitos pendientes
antes de actualizar. No modifica el stock del inventario ni requiere migraciones.

## Comparación de períodos (rama de prueba)

La vista de análisis permite comparar todos los iniciales contra el actual o
revisar tramos consecutivos, abrir su evidencia y exportar un Excel comparativo.
El [recorrido de prueba y las reglas de cobertura](docs/prueba_analisis_periodos.md)
detallan cómo validar esta vista sin migraciones de base de datos.

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
