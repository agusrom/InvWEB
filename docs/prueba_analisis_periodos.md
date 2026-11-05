# Prueba de la comparación de períodos

Rama: `feat/analisis-stock-periodos-ergonomia`, basada en
`feat/optimizar-portada-v116`. No requiere migraciones ni nuevas tablas. La
fotografía del análisis sigue guardándose en la auditoría SQLite existente.

## Recorrido para probar

1. Abrir **Análisis de stock**, elegir un inventario actual y seleccionar de dos
   a cuatro inventarios iniciales completos y comparables. Se conservan los
   filtros existentes de cliente, categoría y modalidad.
2. Pulsar **Calcular escenarios**. La nueva entrada es una matriz de componentes
   y MP, con una columna por inicial → actual y el control directo contra sistema
   actual en otra columna.
   Al abrir un análisis guardado se muestran directamente sus resultados. Para
   modificar los iniciales, usar **Cambiar períodos**: la configuración se abre en
   una ventana separada, con **Aplicar y recalcular**. Cerrar o volver sin aplicar
   conserva los períodos del análisis.
3. Cambiar **Períodos** a **Tramos consecutivos**. Se ordenan por fecha: A → B,
   B → C, C → actual. Abrir una celda para ver su cálculo.
4. En el panel lateral, contrastar los dos controles independientes: sistema
   actual y evolución física del tramo. Revisar cobertura, cantidades, explosión,
   cortes efectivos de ingresos/egresos, scrap y documentación.
5. Abrir un número de remito. El registro queda filtrado por documento. Usar
   **Volver a la evidencia del componente** para retomar el mismo tramo.
6. Usar **Abrir revisión** para registrar estado, causa manual, comprobaciones y
   observación. La matriz conserva su búsqueda y el tipo de período al volver.
7. Probar los filtros de diferencias, conteos pendientes, comparaciones no
   evaluables, remitos sin verificar y revisiones resueltas/sin resolver.
8. Guardar el análisis y comprobar la cabecera: último cálculo, último guardado y
   cambios pendientes. Las notas se guardan automáticamente, pero la fotografía
   requiere **Guardar análisis/Guardar cambios**, como antes.
9. Exportar **Excel comparativo**: incluye acumulados, consecutivos, control de
   sistema, cortes/advertencias e indicadores. Se mantiene la exportación anterior
   por período. Si hay cálculos sin guardar, la exportación se recalcula con los
   datos persistidos de inventarios y auditoría y lo informa al finalizar.
10. Reabrir una fotografía anterior a esta rama. Los datos previos se conservan;
    para disponer de consecutivos y cobertura nueva hay que actualizar el cálculo
    explícitamente.

El resumen anterior sigue disponible en el desplegable **Resumen y filtros del
período acumulado seleccionado**. También se conservan el detalle por pieza, la
carga de remitos manuales con varios renglones, las correcciones, verificaciones,
exclusiones, scrap, difusión e impresión.

## Cómo se calculan los consecutivos

Se derivan de los acumulados calculados con el mismo inventario actual y la misma
auditoría. Por ejemplo:

- Ingresos A → B = ingresos A → actual − ingresos B → actual.
- Egresos A → B = egresos A → actual − egresos B → actual.
- Scrap A → B = scrap A → actual − scrap B → actual.
- Esperado en B = físico explotado de A + ingresos A → B − egresos A → B − scrap.
- Diferencia del tramo = físico explotado de B − esperado en B.

El inventario B se obtiene del físico inicial del acumulado B → actual, por lo
que un conteo actual pendiente no impide revisar un tramo histórico completo.
Los documentos compartidos se restan por su identidad de origen, conservando las
cantidades corregidas y las verificaciones. No se crea ni modifica una auditoría
independiente sobre el inventario histórico B.

Si las exclusiones, los cortes o el scrap de dos acumulados no permiten separar
un tramo de forma consistente, se muestran los datos de respaldo y el motivo de
**No evaluable**, sin dar una diferencia por válida. También se bloquea la
evaluación cuando no coinciden la composición de un grupo o las unidades, o los
inventarios tienen la misma fecha.

## Cobertura e indicadores

- **Contado:** el componente está incluido directamente y su conteo está completo;
  un cero registrado es un dato válido.
- **Componente explotado:** proviene de la estructura de piezas incluidas, con sus
  usos acumulados y cantidades de origen disponibles como traza.
- **Conteo pendiente:** faltan conteos de algún renglón que aporta al componente.
- **No incluido:** el componente no está cubierto en uno de los inventarios. No se
  supone que su stock es cero.

La evolución física y el control directo contra sistema tienen cobertura
independiente. Un componente explotado puede no tener un renglón directo contra
sistema; se informa esa ausencia sin fabricar una comparación 0 contra 0.

La matriz separa cobertura comparable, proporción dentro de tolerancia y
verificación documental. Los pendientes y las comparaciones sin cobertura se
excluyen de los porcentajes evaluados; los errores de período se muestran aparte.

No se agregan detección, compensación ni sugerencias automáticas de errores de
identificación. Las causas siguen siendo registradas por quien revisa. Los
patrones anteriores se presentan como hipótesis orientativas, sin asignarles un
nivel de certeza estadística.

## Verificación de la rama

Pruebas aisladas de acumulados/consecutivos, orden cronológico, ausencia frente a
cero, conteo actual pendiente, ajustes manuales, scrap, cortes/exclusiones no
anidados, guardado y Excel. Pruebas de navegador de matriz, evidencia, navegación
hacia remitos y regreso, filtros, notas, estado de la fotografía, exportación,
compatibilidad con fotografías anteriores y distribución en escritorio/celular.


## Presentación de la revisión

La cabecera muestra el nombre del análisis y el inventario actual. Las pestañas
Comparación, Detalle por pieza y Remitos, junto con Guardar análisis/Guardar cambios,
quedan fijas al desplazarse. Exportar reúne el Excel comparativo, el período
seleccionado y la impresión. Los indicadores y el estado de guardado son compactos;
el historial por pieza se despliega cuando hace falta. Al crear un análisis,
la selección de inventarios sigue disponible en la pantalla inicial.
