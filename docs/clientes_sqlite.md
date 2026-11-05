# Primera etapa: maestro de clientes en SQLite

Rama: `feat/catalogos-sqlite-clientes`, basada en la última rama de análisis.

## Alcance

Se agrega un maestro nuevo de clientes. **Todo lo que ya utilizaba MySQL sigue
allí**, incluidos inventarios, plantillas, programaciones, tipos de inventario,
personas, sectores, causas, indicadores y formatos. No se trasladan esos catálogos
ni se crean o modifican tablas en MySQL. Sus pantallas y endpoints existentes
conservan su fuente de datos.

Los únicos datos nuevos de esta etapa se guardan en SQLite:

| Tabla | Uso |
| --- | --- |
| `clientes` | ID, código estable, nombre visible, valor compatible con formularios existentes, descripción, orden, activo y destino de unificación. |
| `cliente_nombres` | Nombres actuales e históricos asociados a cada ID. La clave normalizada usa SHA-256 de 64 caracteres para mantener un índice corto y portable. |
| `catalogo_meta` | Fecha de incorporación inicial de nombres históricos. |

## Uso desde la web

En **Configuración → Catálogos → Clientes** se puede:

- Agregar y editar clientes, descripción, orden y estado activo/inactivo.
- Agregar nombres alternativos, uno por línea. Se conservan los nombres anteriores
  para que las referencias históricas sigan resolviendo.
- Buscar por nombre actual, código o nombre asociado.
- Ver la cantidad de inventarios y plantillas asociadas.
- Eliminar un cliente sin uso. Si tiene historial o identidades unificadas, la
  eliminación se bloquea y se debe desactivar.
- Unificar explícitamente dos clientes que representen a la misma entidad: los
  nombres pasan al destino y el origen queda inactivo. Esta acción cambia su
  agrupación en reportes y comparaciones, pero no reescribe inventarios ni
  plantillas existentes. Hay que revisar el conjunto de registros afectado;
  etiquetas genéricas antiguas pueden no representar a un único cliente.
- Exportar los clientes, sus códigos, IDs y nombres asociados en JSON.

Las pestañas existentes de tipos, personas y sectores continúan administrando sus
registros en MySQL, exactamente como antes.

## Integración con los formularios

La plantilla usa un selector de clientes en lugar de texto libre. En inventarios
manuales y cíclicos se elige también un cliente explícito. El código de pieza del
cliente (`codigo_cliente`) ya no se interpreta como si fuera el nombre de la
empresa. Ese código sigue siendo un atributo del artículo y no se modifica.

Los clientes inactivos no se ofrecen para nuevas asignaciones. Una plantilla
existente puede conservar su cliente inactivo al editar otros datos. Hay enlaces
a Configuración y botones **Actualizar lista** para incorporar un cliente recién
creado sin recargar el formulario.

Los tipos y las personas de esos formularios siguen viniendo de MySQL.

## Compatibilidad e historial

Al iniciar la aplicación, se consultan los nombres distintos de las cabeceras de
inventarios y plantillas existentes y se incorporan al nuevo maestro local. Esa
consulta es de solo lectura. La página de clientes también detecta nombres
históricos nuevos al cargar su listado.

Se normalizan espacios, mayúsculas/minúsculas y acentos para evitar duplicados.
No se unifican automáticamente nombres con otras diferencias, por ejemplo
`Empresa SA` y `Empresa S.A.`; se revisan desde la web.

Cada cliente conserva un ID y un código estables. Renombrarlo cambia su nombre
visible y agrega un nombre asociado. Los textos originales de los inventarios se
mantienen; la API agrega campos de identidad/nombre visible sin reemplazarlos.
La búsqueda de inventarios también reconoce el nombre visible actualizado.
Las nuevas asignaciones usan un valor estable compatible con las columnas
actuales. Los nombres asociados permiten comparar y agrupar registros que el
usuario haya decidido unificar.

No se agrega detección automática de material mal identificado ni se modifica la
explosión, las tolerancias o la fórmula del análisis de stock.

## Persistencia y respaldo

El archivo predeterminado es `data/catalogos.sqlite3`. Opcionalmente se puede
configurar `CATALOG_DATABASE_PATH` con una ruta persistente. Esto no cambia
`DATABASE_URL`, que sigue apuntando a la BD principal existente.

Las tablas nuevas se crean únicamente en ese archivo SQLite. Se usan transacciones,
claves únicas, claves foráneas y WAL. El alta/edición y la unificación se guardan de
forma atómica; un nombre asociado a otro cliente produce un error sin cambios
parciales. Los reinicios no reemplazan nombres editados ni reactivan clientes.

El archivo es dato operativo y no se publica en Git. Debe conservarse entre
publicaciones. Para una copia física en funcionamiento se debe usar el mecanismo
`backup` de SQLite, que contempla WAL; no copiar solo el archivo principal mientras
hay escrituras. La exportación JSON desde la web permite revisar y conservar las
identidades y sus asociaciones. Conviene respaldar antes de una unificación.

## MySQL, más adelante

En esta etapa **no hay SQL para ejecutar por el administrador**. Para la futura
migración habrá que preparar y probar un SQL independiente que cree el maestro de
clientes y las asociaciones, importe los IDs estables y permita enlazar los
registros existentes. Las columnas de ID en inventarios/plantillas y cualquier
conversión de sus referencias quedan para esa etapa, con respaldo y validación
previos. No se deben borrar catálogos ni tablas actuales de MySQL.

## Validación

Las pruebas usan bases temporales separadas y verifican que la incorporación del
historial solo ejecute SELECT sobre la fuente; que SQLite contenga únicamente las
tres tablas nuevas; IDs y valores estables; duplicados; rollback de asociaciones
inválidas; desactivación; eliminación protegida; unificación explícita; compatibilidad
con tipos ya existentes y exportación. La prueba en navegador usa APIs reales
contra esas bases temporales y cubre configuración, selectores, actualización de
listas, estado inactivo, nombres asociados, exportación y vista móvil.
