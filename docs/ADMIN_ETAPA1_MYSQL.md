# Entrega al administrador — MySQL, etapa 1

Archivo a ejecutar: `sql/etapa1_retirar_modulos_prueba.sql`.
No requiere Python ni otorgar permisos de DDL al usuario de la aplicación.

## Alcance

Retira exclusivamente las siete tablas del antiguo módulo de Conciliaciones de
prueba. Preserva inventarios, renglones, conteos, reconteos, plantillas,
programaciones y cierres. Si `analisis_stock` tiene una clave foránea opcional
hacia Conciliaciones, elimina ese enlace y conserva los análisis y sus cálculos.
Warehouse era local/SQLite y no necesita borrado de tablas MySQL.

No crea tablas permanentes ni índices nuevos. Utiliza un procedimiento
transitorio con `SQL SECURITY INVOKER` y tablas temporales sin índices, que se
retiran al finalizar. Detecta los nombres reales de claves foráneas; no asume
que sean los mismos de otras instalaciones. Las claves deben estar habilitadas.

## Preparación

1. Coordinar el despliegue del código nuevo, detener servidores y procesos que
   escriban, y comprobar un respaldo restaurable de MySQL y de los archivos
   locales activos de `data`.
2. Usar una cuenta administradora con permisos de inspección, creación/ejecución/
   eliminación de rutinas, tablas temporales, UPDATE, ALTER y DROP. Esos permisos
   no se deben conceder al usuario operativo para ejecutar esta migración.
3. Seleccionar expresamente la base de gestión que usa `DATABASE_URL`, nunca la
   base productiva. Registrar `SELECT DATABASE();` y `SELECT VERSION();`.

## Inspección y aplicación

Abrir y ejecutar el archivo como **script completo** en MySQL Workbench o con
el cliente `mysql`, respetando las instrucciones `DELIMITER`. El archivo no
contiene `USE`: la base se selecciona en la herramienta o al conectar.

La primera ejecución debe mantener estos valores predeterminados:

```sql
SET @invweb_e1_aplicar = 0;
SET @invweb_e1_base_confirmada = 'REEMPLAZAR_POR_BASE_DE_GESTION';
SET @invweb_e1_respaldo_verificado = 0;
```

Imprime la base, la versión y el SQL previsto. No elimina tablas ni actualiza
registros de negocio. Esta inspección también requiere cuenta administradora,
porque el script crea y elimina su procedimiento transitorio.

Después de revisar el plan y comprobar el respaldo, editar **esas tres líneas
en el archivo** y ejecutar nuevamente el script completo:

```sql
SET @invweb_e1_aplicar = 1;
SET @invweb_e1_base_confirmada = 'NOMBRE_EXACTO_DE_LA_BASE_DE_GESTION';
SET @invweb_e1_respaldo_verificado = 1;
```

No basta con ejecutar los SET por separado antes del archivo: sus valores se
restablecen en las primeras líneas. No usar la opción de continuar ignorando
errores del cliente. Si aparece un error, detenerse y enviar el mensaje completo
con su número, la versión y la definición de la tabla afectada.

El script aborta antes del primer borrado/UPDATE si falta la confirmación, la
base no contiene las tablas de inventarios esperadas, las claves foráneas están
deshabilitadas o hay claves declaradas/dependencias en un orden no previsto.
Nunca usa `FOREIGN_KEY_CHECKS=0`. Una dependencia no reconocida se debe revisar,
no desactivar para forzar el borrado.

Al terminar muestra las cantidades antes/después de las tablas protegidas.
Repetir en modo inspección debe producir un plan sin sentencias de limpieza.
Validar en la aplicación un inventario existente, sus registros, Componentes,
Análisis de stock y Excel. Actualizar el código por sí solo no borra las tablas.

Los DDL hacen commit implícito: una falla durante la aplicación puede dejar una
limpieza parcial y **no se revierte con ROLLBACK**. Volver a inspeccionar antes de
reintentar y utilizar el respaldo si corresponde. La cuenta debe tener visibilidad
de las claves foráneas que referencien estas tablas, incluso desde otros esquemas.

## Validación realizada

| Motor aislado | Pruebas del SQL real |
|---|---|
| MySQL 5.7.44 | 8 aprobadas |
| MySQL 8.0.46 | 8 aprobadas |
| MariaDB 11.4.13 | 8 aprobadas |

Se verificaron inspección sin cambios, conservación de todos los valores de las
filas protegidas, limpieza repetible, tabla de análisis opcional y abortos por
base incorrecta, falta de respaldo, claves deshabilitadas y dependencias no
previstas. También se ejecutó el archivo completo con el cliente `mysql` 5.7.
Las pruebas usan bases efímeras; no se ejecutó sobre la base real del usuario.

Pruebas reproducibles: `tests/test_retire_legacy_sql_integration.py`. Son opt-in
mediante `INVWEB_SQL_TEST_PORT` y crean/eliminan sus propias bases temporales.
Requieren una instancia de prueba con permisos administrativos, no la cuenta
operativa ni la base del sistema.

## Para las siguientes migraciones de creación de tablas

La versión y el esquema real todavía deben confirmarse para la instalación del
usuario. Pedir al administrador estos resultados de metadatos (no contienen filas
de inventarios ni contraseñas):

```sql
SELECT VERSION();
SHOW CREATE TABLE inventarios;
SHOW CREATE TABLE inventario_items;
SHOW CREATE TABLE plantillas;
```

Antes de agregar clientes y sus relaciones se deben revisar tipos exactos de
IDs (INT/BIGINT y signed/unsigned), charset/collation, motor y límites de índices.
Esto evita repetir incompatibilidades de claves foráneas o índices demasiado
largos en servidores antiguos. Este archivo no crea el catálogo de clientes ni
completa la migración de SQLite/JSON; corresponde únicamente a la etapa 1.
