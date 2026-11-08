# Portada ligera sin migraciones de base de datos

Esta mejora cambia consultas y carga de datos. No agrega ni modifica tablas,
columnas o índices, ni ejecuta los SQL de limpieza/migración. No requiere permisos
DDL para el usuario de la aplicación. La migración a MySQL queda pendiente.

## Comportamiento

- Listado de 25 inventarios por página, con búsqueda, estado y pestañas aplicados
  en el servidor. Orden estable por fecha e ID; filtros nuevos vuelven a página 1.
- Progreso, confiabilidad, diferencias y pendientes se obtienen mediante
  agregación SQL sobre los renglones de la página, sin serializarlos.
- El mes de cierre se consulta en bloque en la tabla existente.
- Las métricas globales no dependen de la página ni del filtro seleccionado.
- La semana obtiene cabeceras por fechas. El calendario completo se consulta al
  abrirlo, cambiar de período o exportarlo; no depende del listado paginado.
- Un inventario carga sus renglones al abrirse. Sus relaciones de reconteos
  incluyen cabeceras para poder navegar aunque no estén en la página actual.
- El historial comparable se consulta al desplegar el análisis de una pieza o
  las diferencias. Conserva la búsqueda de los tres últimos conteos comparables.
- Las búsquedas tienen una espera breve para evitar una petición por tecla y se
  descartan respuestas atrasadas. El listado y el calendario permiten reintentar.

Se mantiene `/api/inicio` con su contrato anterior para compatibilidad. La
interfaz PC usa `/api/inicio?ligero=true`, que omite los inventarios completos y
cuenta las ejecuciones programadas sin cargar todos sus inventarios.

Las lecturas nuevas están en `/api/portada`: `inventarios`, `metricas`,
`calendario`, `detalle/{id}` e `historial/{id}`. Los endpoints existentes de conteo,
stock, Componentes, notas, cierres, reconteos y exportación siguen vigentes.

## Validación

Once pruebas nuevas verifican paginación sin duplicados, búsqueda literal,
filtrado por estado/ámbito, equivalencia de métricas, cierres consultados en
bloque, métricas globales y calendario independientes, arranque ligero y última
ejecución programada, además de relaciones de reconteos fuera de página. El listado realiza un número constante de consultas
(hasta cinco) para páginas de 1 o 50 inventarios. Las consultas de esa prueba
son exclusivamente SELECT.

Prueba de navegador en una copia aislada de MySQL con 61 inventarios y 1.830
renglones sintéticos:

| Respuesta/carga | Bytes JSON |
|---|---:|
| `/api/inicio` anterior, con inventarios completos | 1.390.578 |
| Total inicial nuevo: arranque, página, métricas y semana | 19.044 |

Reducción de datos iniciales: 98,6 % en ese escenario. No es una medición del
volumen ni de la latencia de la instalación real. No incluye archivos estáticos.

Se comprobaron paginación, filtros, reintento tras error, apertura desde la
semana fuera del filtro actual, Componentes, historial diferido con tres conteos,
navegación mensual, creación/eliminación de notas, descarte de respuestas de
búsqueda atrasadas y navegación por reconteos fuera del filtro visible.

## Alcance pendiente

Los catálogos de plantillas todavía incluyen sus artículos. El portal móvil
conserva su arranque anterior y el historial comparable puede ser voluminoso
cuando se solicita explícitamente. Son mejoras posteriores: no se truncó el
historial para aparentar rendimiento ni se cambiaron los cálculos o las reglas
de negocio de inventarios.
