# Modelo de datos y migración a MySQL

## 1. Separar las dos bases

El sistema trabaja con dos conexiones distintas:

| Variable | Uso | Permisos recomendados |
|---|---|---|
| `DATABASE_URL` | Base propia del sistema: plantillas, programaciones, conteos, causas y conciliaciones | Lectura y escritura |
| `PRODUCTION_DATABASE_URL` | Base productiva existente: `produc01`, `produc05`, `produc10`, `produc21`, `mtprim01` y `mtprim05` | Sólo lectura |

No conviene crear las tablas del sistema dentro de la base productiva. Mantenerlas
separadas evita modificar accidentalmente el ERP y permite respaldar, migrar y
analizar los inventarios en forma independiente.

Ejemplo de configuración:

```env
DATABASE_URL=mysql+pymysql://usuario_inventarios:CLAVE@SERVIDOR:3306/inventarios_web
PRODUCTION_DATABASE_URL=mysql+pymysql://usuario_lectura:CLAVE@SERVIDOR:3306/base_productiva
```

## 2. Relaciones principales

```mermaid
erDiagram
    PLANTILLAS ||--o{ PLANTILLA_ITEMS : contiene
    PLANTILLAS ||--o{ PROGRAMACIONES_INVENTARIO : programa
    PROGRAMACIONES_INVENTARIO ||--o{ INVENTARIOS : genera
    INVENTARIOS ||--o{ INVENTARIO_ITEMS : registra
    FORMATOS_IMPRESION ||--o{ FORMATO_VERSIONES : versiona
    FORMATO_VERSIONES ||--o{ FORMATO_COLUMNAS : configura
    FORMATO_VERSIONES ||--o{ INVENTARIOS : fija_diseno
    CAUSAS_DIFERENCIA ||--o{ INVENTARIO_ITEMS : clasifica
    CONCILIACIONES ||--o{ CONCILIACION_ITEMS : contiene
```

La cabecera histórica es `inventarios`. La tabla de hechos para futuros
indicadores es `inventario_items`: cada fila representa un código en una etapa,
operación o lote determinado, con el stock teórico congelado y el conteo físico.

## 3. Catálogo de tablas

### `plantillas`

Define conjuntos reutilizables de artículos.

| Campo | Contenido |
|---|---|
| `id` | Identificador interno |
| `nombre`, `cliente`, `descripcion` | Datos visibles de la plantilla |
| `categoria` | `PIEZAS` o `MATERIA_PRIMA` |
| `tipo_conteo` | Proceso global o por operación |
| `formato_impresion` | Formato sugerido de impresión |
| `controla_remitos` | Habilita ingreso de remitos en el inventario |
| `activa`, `creada_en` | Estado y fecha de alta |

### `plantilla_items`

Artículos incluidos en una plantilla. Es una configuración, no un resultado
histórico.

| Campo | Contenido |
|---|---|
| `id`, `plantilla_id` | Clave y relación con la plantilla |
| `codigo`, `codigo_cliente`, `codigo_material` | Identificadores del artículo |
| `descripcion`, `ubicacion` | Datos descriptivos |
| `diametro`, `largo`, `espesor`, `unidad` | Datos específicos de materia prima |
| `stock_referencia` | Referencia usada solamente por datos de demostración |
| `contar_material` | Indica si esa pieza debe generar una fila de MP sin usar |

### `programaciones_inventario`

Agenda de inventarios tentativos.

| Campo | Contenido |
|---|---|
| `id`, `plantilla_id` | Clave y plantilla programada |
| `fecha_proxima` | Próxima fecha tentativa |
| `frecuencia`, `dia_mes` | Una vez, semanal o mensual |
| `responsable`, `colaboradores`, `observaciones` | Organización del conteo |
| `activa`, `ultima_ejecucion`, `creada_en` | Seguimiento de la programación |

### Diseños de impresión

El editor separa el tipo estable de planilla de cada versión publicada:

| Tabla | Contenido |
|---|---|
| `formatos_impresion` | Código, nombre, categoría, estado y posibilidad de edición |
| `formato_versiones` | Nombre, orientación, márgenes, letra, altura, firmas y número de versión |
| `formato_columnas` | Clave estable, título, orden, visibilidad y ancho porcentual |

Editar un diseño agrega una versión identificada por nombre y número; no
actualiza versiones anteriores. Al imprimir, el usuario puede elegir cualquiera
de las versiones que pertenezcan al formato seleccionado.

### `inventarios`

Cabecera de cada inventario efectivamente generado. Conserva la planificación y
la ejecución por separado.

| Campo | Contenido |
|---|---|
| `id`, `codigo` | Identificador interno y código visible |
| `origen` | `PLANTILLA`, `CICLICO` o `MANUAL` |
| `cliente`, `plantilla_id`, `programacion_id` | Cliente y referencias de origen |
| `fecha_programada`, `fecha`, `creado_en`, `cerrado_en` | Fechas tentativa, real, de alta y cierre |
| `responsable`, `colaboradores` | Personas participantes |
| `ambito` | `INTERNO` o `CLIENTE` |
| `estado` | En preparación, en conteo o cerrado |
| `categoria`, `formato_impresion` | Tipo de inventario y presentación |
| `formato_version_id` | Versión exacta del diseño utilizada por la impresión |
| `controla_remitos`, `ultimo_remito_ingreso`, `ultimo_remito_egreso` | Corte documental |
| `observaciones` | Comentario general |
| `stock_actualizado_en`, `stock_origen` | Momento y fuente de la foto teórica |

### `causas_diferencia`

Catálogo administrable de causas. Se usa un código estable para que cambiar el
nombre visible no rompa los indicadores históricos.

| Campo | Contenido |
|---|---|
| `codigo` | Clave estable, por ejemplo `ERROR_CONTEO` |
| `nombre`, `descripcion` | Texto visible y ayuda |
| `categoria` | Producción, documentación, conteo, ubicación, sistema u otra |
| `orden` | Orden del selector |
| `activa` | Permite ocultar una causa nueva sin borrar el historial |

### `inventario_items`

Detalle histórico y principal tabla analítica.

| Grupo | Campos |
|---|---|
| Claves | `id`, `inventario_id` |
| Artículo | `codigo`, `codigo_cliente`, `codigo_material`, `descripcion`, `ubicacion` |
| Materia prima | `diametro`, `largo`, `espesor`, `unidad`, `lote` |
| Estructura cíclica | `codigo_padre`, `nivel`, `uso`, `ruta` |
| Flujo | `etapa`, `operacion`, `titulo_operacion`, `proveedor` |
| Comparación | `stock_pendiente`, `stock_sistema`, `conteo_fisico` |
| Configuración congelada | `contar_material` |
| Análisis | `causa_diferencia_codigo`, `observaciones` |

Los datos descriptivos se copian intencionalmente al generar el inventario. Así,
si mañana cambia una descripción, material u operación en la base productiva,
el inventario histórico conserva exactamente lo que se contó ese día.

No es necesario guardar `diferencia`, `porcentaje` o `dentro_del_5_por_ciento`.
Son valores derivados:

- Diferencia: `conteo_fisico - stock_sistema`.
- Relación: `conteo_fisico / stock_sistema * 100`.
- Dentro de tolerancia: desvío absoluto menor o igual a 5%.

Calcularlos al consultar evita inconsistencias si se corrige un conteo.

La vista consolidada por pieza no crea otra tabla ni duplica cantidades:
agrupa temporalmente estos renglones en pantalla. Por eso la vista detallada,
las exportaciones y los futuros indicadores continúan usando el mismo historial.

### `conciliaciones`

Cabecera del análisis entre un inventario inicial y uno final.

| Campo | Contenido |
|---|---|
| `id`, `codigo`, `nombre` | Identificación |
| `inventario_inicial_id`, `inventario_final_id` | Inventarios comparados |
| `inventario_inicial_codigo`, `inventario_final_codigo` | Copia histórica de los códigos |
| `fecha_inicial`, `fecha_final` | Período |
| Campos `remito_*` | Cortes documentales iniciales y finales |
| `creada_en` | Fecha de creación |

### `conciliacion_items`

Resultado por componente después de explotar las estructuras.

| Campo | Contenido |
|---|---|
| `id`, `conciliacion_id` | Claves |
| `codigo`, `descripcion` | Componente |
| `stock_inicial`, `detalle_inicial` | Existencia inicial y trazabilidad |
| `ingresos`, `egresos` | Movimientos manuales |
| `stock_final`, `detalle_final` | Existencia final y trazabilidad |

## 4. Indicadores que soporta este modelo

Sin modificar las tablas se podrán obtener, entre otros:

- Confiabilidad por mes, cliente, código, etapa, operación o responsable.
- Evolución de un mismo código a lo largo de varios conteos.
- Cantidad y magnitud absoluta de diferencias por causa.
- Causas recurrentes por código, sector, proveedor u operación.
- Cumplimiento de fechas: fecha programada frente a fecha real y cierre.
- Comparación de inventarios internos frente a inventarios con cliente.
- Diferencias según el origen de stock: base productiva o reportes Excel.
- Conciliación de stock inicial + ingresos - egresos contra stock final.

Para tableros futuros conviene consultar solamente inventarios cerrados y unir
`inventario_items` con `inventarios` y `causas_diferencia`.

## 5. Migración recomendada durante las pruebas

Como los datos actuales todavía son de prueba, el camino más limpio es crear
una base MySQL vacía para el sistema:

1. Guardar una copia del archivo SQLite actual por seguridad.
2. Crear una base y un usuario MySQL exclusivos para la aplicación.
3. Ejecutar `sql/schema_mysql.sql` en esa base.
4. Cambiar únicamente `DATABASE_URL` en `.env`.
5. Mantener `PRODUCTION_DATABASE_URL` separado y con permisos de sólo lectura.
6. Iniciar la aplicación y hacer un inventario de prueba completo.
7. Verificar guardado, cierre, Excel, causas, observaciones y conciliación.

El cambio de `DATABASE_URL` inicia un historial nuevo en MySQL; no copia
automáticamente los datos de SQLite. Si más adelante hubiera información real
que conservar, debe hacerse una migración controlada manteniendo los IDs y el
orden de las claves foráneas.

## 6. Antes del uso productivo

- Crear copias de seguridad automáticas de `inventarios_web`.
- Usar un usuario de aplicación que no pueda crear ni borrar otras bases.
- Restringir el usuario productivo a `SELECT`.
- Incorporar Alembic para versionar cambios de esquema posteriores.
- Definir quién puede cerrar, reabrir o eliminar inventarios.
- Evitar borrar causas utilizadas: deben marcarse como inactivas.
- Administrar el catálogo desde `/configuracion/causas`; los códigos históricos
  no cambian aunque se editen el nombre o la descripción.
