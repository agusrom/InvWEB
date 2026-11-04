# Migración y estandarización — instalación existente v1.16

## Etapa 1 implementada: retirar módulos de prueba

Se retiran la pantalla, API, modelos, formularios y almacenes de Conciliaciones
antiguas, y los archivos de Warehouse/Depósito. No se borran inventarios,
renglones, conteos, plantillas, programaciones, cierres ni relaciones de reconteos.
Análisis de stock y Componentes dentro del inventario siguen disponibles.

El historial antiguo de Conciliaciones está en MySQL. Actualizar el código no
lo borra automáticamente. El arranque ya no necesita sus tablas, por lo que el
nuevo código es compatible antes y después de la limpieza.

### Cambios que hay que aplicar en MySQL

Usar exclusivamente la base de gestión de `DATABASE_URL`, nunca la base
productiva de `PRODUCTION_DATABASE_URL`. Este procedimiento parte de una base
existente de la versión 1.16; no es un instalador de bases vacías.

1. Detener las instancias del servidor y los procesos que escriban. Tener un
   respaldo completo de MySQL cuya restauración se haya comprobado, y respaldar
   también los archivos SQLite/JSON de `data`. El respaldo no lo hace el script.
2. Con el entorno Python activado, desde la raíz del repositorio, inspeccionar:

   ```sh
   python scripts/retirar_modulos_prueba.py
   ```

   Es solo lectura: imprime el nombre de la base, los conteos y el SQL exacto.
   No se debe continuar si la base no es la esperada. Si encuentra claves foráneas
   inesperadas desde otras tablas, se detiene antes de ejecutar el plan.
3. Para aplicar, reemplazar `inventarios_web` por el nombre real mostrado:

   ```sh
   python scripts/retirar_modulos_prueba.py --apply --confirm-database inventarios_web --backup-confirmed
   ```

   Retira únicamente las tablas presentes de esta lista:

   - `conciliacion_remito_items`
   - `conciliacion_ingresos_control`
   - `conciliacion_egresos_control`
   - `conciliacion_items_excluidos`
   - `conciliacion_remitos`
   - `conciliacion_items`
   - `conciliaciones`

   Calcula el orden según las claves foráneas. Si `analisis_stock` tiene el enlace
   opcional `conciliacion_legacy_id`, lo pone en NULL y quita su clave foránea
   hacia la tabla retirada; conserva los análisis y sus cálculos. No desactiva
   `FOREIGN_KEY_CHECKS`. No toca la conexión productiva ni crea catálogos nuevos.
4. Revisar el resultado: compara las cantidades antes/después de las tablas
   protegidas de inventarios y conteos. Reiniciar y verificar portada,
   inventario existente, registros, Componentes, Análisis de stock y Excel.
   Ejecutar nuevamente la inspección debe producir un plan vacío.

Los `DROP TABLE`/`ALTER TABLE` hacen commit implícito en MySQL. Una falla durante
la aplicación puede dejar parte del retiro realizado: no se revierte con
ROLLBACK. Detenerse, revisar el error y volver a inspeccionar; restaurar el
respaldo si corresponde. No ejecutar con el sistema recibiendo escrituras.

Warehouse no tiene tablas MySQL propias en este código: usaba `data/deposito.db`.
Sus archivos locales `deposito.db`, `deposito.db-wal` y `deposito.db-shm`, y el
viejo `conciliacion_remitos.db` con sus archivos auxiliares, se pueden retirar
con el servidor detenido después de confirmar que son esos datos de prueba.
No borrar en bloque `data` ni los archivos `preconciliacion_*`: estos últimos
pertenecen al Análisis de stock actual. Los reconteos también se conservan.

Se retira el migrador antiguo `migrar_analisis_a_mysql.py` y su lanzador: estaban
desalineados con el almacenamiento actual y podían mover archivos todavía en
uso. Las migraciones SQL históricas se conservan como referencia; no volver a
ejecutarlas automáticamente ni usar `migracion_v130.sql` como limpieza.

## Etapa 2: catálogo de clientes (todavía pendiente de implementar)

Primero revisar los valores existentes sin modificarlos:

```sh
python scripts/auditar_clientes.py --output /tmp/clientes_revision.csv
```

El CSV se crea únicamente si no existe. Agrupa variantes de escritura para
revisión, pero no decide que dos valores sean el mismo cliente. Completar
`cliente_canonico`, `codigo_cliente` y `decision`: algunos textos actuales son
códigos de pieza del cliente o nombres genéricos de inventario, no clientes.

El siguiente cambio de esquema deberá crear `clientes` (id, código único,
nombre, activo) y las equivalencias de nombres históricos. Después se agregará
`cliente_id` nullable a plantillas e inventarios, se migrarán únicamente las
correspondencias revisadas y se actualizarán formularios, filtros y reportes.
Solo tras validar el mapeo se exigirán las relaciones y se retirará el texto
libre. Una baja de cliente con historial debe ser lógica (activo=false).
No ejecutar un UPDATE general sobre `cliente` ni asignar automáticamente
clientes por el campo `codigo_cliente` de las piezas.

## Etapas siguientes para llegar a MySQL

1. Corregir la transacción de conteos: API y almacén de registros deben compartir
   conexión y transacción; actualmente hay una conexión que bloquea renglones y
   otra que intenta guardar registros. Mantener idempotencia por `cliente_uid`.
2. Migrar los metadatos de `inventarios_auxiliares.db` junto con los conteos;
   no confirmar MySQL y luego depender de una segunda escritura en SQLite.
3. Migrar notas del cronograma, análisis, auditorías y notas JSON con importador
   explícito, preservación de IDs, conciliación de cantidades y copia verificada.
   Activar el nuevo almacén después de validar; no hacer doble escritura indefinida.
4. Versionar el esquema de forma secuencial, agregar pruebas de integración con
   MySQL y separar módulos de API/servicios. Mantener respaldos conjuntos hasta
   que ningún dato activo dependa de archivos locales.

En esta etapa todavía se usan `inventarios_auxiliares.db`,
`notas_cronograma.db`, `preconciliacion_auditoria.sqlite3` y
`preconciliacion_notas.json`. Deben conservarse y respaldarse. No se considera
terminada la migración total a MySQL.
