# Migración completa a MySQL — v1.30.1

Esta migración conserva los IDs históricos y copia a MySQL los datos que las
versiones anteriores guardaban en SQLite o JSON. No modifica
`PRODUCTION_DATABASE_URL` ni las tablas productivas de consulta.

## Orden de ejecución

1. Detener Uvicorn y cerrar cualquier instancia del sistema.
2. Conservar el `.env` y la carpeta `data` de la instalación actual.
3. Confirmar que `DATABASE_URL` apunte a la base propia del sistema.
4. Desde phpMyAdmin o MySQL Workbench, seleccionar esa misma base y ejecutar:

   `sql/migracion_v130.sql`

5. Cuando el SQL termine sin errores, ejecutar:

   `migrar_datos_a_mysql.bat`

6. Verificar que el proceso finalice con `Migración terminada correctamente`.
7. Revisar el informe `data/migracion_v130_resultado.json` y recién entonces
   iniciar la aplicación con `run.bat`.

## Datos importados

- cierres mensuales de inventarios y programaciones;
- registros caja por caja, bases acumuladas y revisiones móviles;
- remitos, cantidades corregidas, verificaciones, comentarios, scrap y
  movimientos manuales de las conciliaciones anteriores;
- relaciones entre inventarios originales y reconteos;
- análisis guardados, auditorías y notas del análisis unificado;
- reconteos experimentales antiguos, conservados como datos legacy.

El migrador es idempotente: puede repetirse después de corregir un error sin
duplicar registros. Los archivos locales se mueven al respaldo fechado sólo si
no se registró ningún error. El prototipo WMS se respalda pero no se importa.

## Corrección del error #1215

Los IDs de la base MySQL histórica son `BIGINT`. Por eso todas las columnas que
los referencian también son `BIGINT`; MySQL exige que ambos lados de una clave
foránea coincidan exactamente.
