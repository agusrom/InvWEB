# Sistema de Inventarios

## v0.93.10 · MP inicial compartida sin duplicar

- Corrige el físico inicial explotado de los grupos que comparten materia prima.
- Cada combinación MP + lote se incorpora una sola vez aunque figure en las dos piezas.
- Proceso y PT continúan sumándose individualmente para cada pieza del grupo.
- Aplica la misma protección al conteo explotado actual.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.93.9 · Control de sistema individual dentro del grupo

- Mantiene una sola conciliación conjunta para las piezas que comparten MP.
- En Análisis detallado vuelve a mostrar por separado Sistema, Físico, MP, Proceso, PT y diferencia de cada pieza.
- Presenta los ajustes de produc16 y el historial contra sistema dentro de la pieza correspondiente.
- Evita que diferencias opuestas entre piezas marquen el control directo del grupo como correcto por compensación.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.93.8 · Análisis conjunto de MP compartida

- Agrupa en Resumen y Análisis detallado las piezas que comparten el mismo código de materia prima.
- Consolida físico inicial, Proceso, PT, egresos y scrap de todas las piezas del grupo.
- Cuenta una sola vez cada ingreso de la MP compartida y evita duplicarlo por pieza.
- Calcula esperado, diferencia y confiabilidad sobre la ecuación conjunta del grupo.
- Conserva el detalle de las piezas integrantes y de los remitos considerados.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.93.7 · Físico cero con stock teórico

- Permite confirmar físico 0 en cualquier lote de MP que todavía no tenga registros.
- Funciona aunque el lote tenga stock teórico: el sistema conserva ese valor y muestra la diferencia negativa correspondiente.
- Evita confirmar 0 sobre un lote que ya posee registros individuales.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.93.6 · Confirmación de cero por lote

- Permite confirmar físico 0 en cualquier lote cuyo stock de sistema sea 0.
- La opción funciona tanto para Sin lote como para un lote real dentro de una MP con varios lotes.
- Los lotes reales con stock 0 continúan incluidos en la cantidad total de lotes.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.93.5 · Corrección del indicador de lotes

- El grupo auxiliar Sin lote continúa visible para confirmar el físico 0, pero ya no se contabiliza como un lote real.
- Una materia prima sin lotes ahora muestra correctamente 0 lotes.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.93.4 · Registros PC y físico cero sin lote

- Permite eliminar desde la pantalla PC cada registro individual cargado dentro de un lote de materia prima.
- Recalcula el físico del renglón y actualiza la revisión del conteo después de eliminarlo.
- Permite confirmar físico 0 para una MP que aparece Sin lote y con sistema 0, evitando que el conteo quede incompleto.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.93.3 · Excel con físico por ubicación

- El resumen del Excel desglosa el conteo físico en Disponible, En línea, Scrap y Sin ubicación / ajuste PC.
- La suma del desglose conserva exactamente el físico total usado para calcular la diferencia.
- El detalle histórico mantiene la columna física total por compatibilidad y agrega las cuatro ubicaciones.
- Los conteos directos o registros antiguos sin sector se identifican separadamente.

## v0.93.2 · Resultado compartido centrado

- Centra verticalmente el resultado combinado de los grupos con MP compartida.
- Sistema, físico, diferencia, diagnóstico y acción quedan alineados con el centro de las piezas relacionadas.
- Mantiene cada pieza como un renglón independiente y conserva la tarjeta única de MP.

## v0.93.1 · Filas compartidas y lotes bajo demanda

- Mantiene cada pieza como un renglón normal aunque comparta materia prima con otra.
- Une solamente la celda de MP y el resultado combinado mediante una tarjeta que abarca las piezas relacionadas.
- Identifica los renglones del mismo grupo con un fondo violeta suave.
- Oculta los lotes de la tabla principal y los muestra como tarjetas al abrir `Registros`.
- Permite entrar a los registros de cada lote y volver al listado sin cerrar la ventana.
- En Recorrido móvil muestra una sola fila por código de MP; los lotes aparecen al desplegarla.
- Pinta también Proceso y PT con el color del grupo cuando comparten la misma MP.
- Evita que inventarios anteriores dupliquen visualmente el físico de una misma combinación `MP + lote`.
- Mantiene la carga offline, el alta/eliminación de lotes y los registros desde PC.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.93.0 · MP por lote, grupos compartidos y registros desde PC

- En inventarios normales de piezas, la MP se genera y actualiza por lote desde `mtprim05`.
- Reemplaza el reporte Excel de MP por las columnas `lote`, `cmat`, `descr`, `undad`, `cant`.
- Permite agregar o quitar lotes desde las vistas PC y móvil, conservando los controles de registros existentes.
- Agrupa visualmente las piezas que comparten una MP y calcula un único total combinado: MP compartida + Proceso/PT de todas las piezas relacionadas.
- Evita duplicar el stock de una MP compartida al generar, actualizar desde MySQL o importar Excel.
- Permite agregar desde la PC uno o varios registros, con cantidad y observación, dentro del detalle acumulado.
- Conserva el funcionamiento offline del conteo móvil y actualiza su caché.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.92.13 · Total general unificado en Análisis

- La pantalla de Análisis usa `MP equivalente + Proceso + PT` para el total del sistema.
- Calcula el físico total con exactamente las mismas tres etapas.
- La diferencia, el porcentaje y el diagnóstico salen de esos totales generales.
- Mantiene el desglose individual para explicar de dónde sale cada número.
- Conserva compatibilidad con los análisis y exportadores anteriores.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.92.12 · Total general MP + Proceso + PT

- Calcula el total del sistema sumando MP, Proceso y PT de cada pieza.
- Calcula el total físico con las mismas tres etapas.
- Usa ese total general para la diferencia, el desvío y el diagnóstico de la pieza.
- Actualiza el resultado en vivo al modificar cualquiera de las tres etapas.
- Conserva visibles los valores individuales de MP, Proceso y PT.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.92.11 · Títulos cortos en tarjetas de conteo

- Usa los títulos compactos `MP`, `Proceso` y `PT` en la vista PC.
- Identifica múltiples operaciones como `Proceso 010`, `Proceso 020`, etc.
- Mantiene el título y el stock de sistema en una sola línea.
- Conserva la distribución corregida de las tarjetas y el acceso a Registros.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.92.10 · Títulos completos en tarjetas de conteo

- Muestra completos los títulos Material sin usar, Total en proceso y Pieza terminada.
- Separa el título y la etiqueta de Sistema en dos niveles dentro de cada tarjeta.
- Permite que los títulos utilicen dos líneas sin invadir la tarjeta contigua.
- Mantiene alineados Físico, diferencia y Registros en las tres etapas.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.92.9 · Tarjetas de conteo PC corregidas

- Redistribuye el ancho de las columnas de MP, Proceso y Terminado en la vista por pieza.
- Evita que la tarjeta de Materia prima invada la columna de Proceso.
- Coloca el acceso `Registros` debajo del campo físico en lugar de enfrentarlo horizontalmente.
- Mantiene alineadas las tres tarjetas de etapa y sus diferencias.
- Conserva el detalle completo del acumulado incorporado en la versión anterior.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.92.8 · Eliminación múltiple y composición del conteo

- Permite seleccionar varios registros de una pieza desde el historial móvil.
- Agrega `Seleccionar todos` y `Misma carga` para localizar rápidamente un lote cargado como `10 × 6`.
- Elimina todos los registros seleccionados con una sola confirmación y una sola sincronización.
- Descuenta inmediatamente el total físico aunque el celular esté sin conexión.
- Incorpora en la vista PC el botón `Ver acumulado` o `Detalle` para cada renglón contable.
- Muestra el físico total, la base cargada o editada desde PC, el total móvil y la cantidad de registros.
- Detalla cada registro con cantidad, ubicación, observación, fecha y dispositivo.
- Carga el detalle bajo demanda para no aumentar el peso inicial del inventario.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.92.7 · Conteo móvil unificado

- Unifica Recorrido y Por pieza en una sola pantalla de conteo rápido.
- Mantiene cantidad, registros y guardado inline sin abrir otra pantalla.
- Despliega en cada renglón el físico, stock del sistema y todos sus registros.
- Permite eliminar registros equivocados desde el mismo renglón.
- Conserva como observación la ubicación física Disponible, En línea o Scrap.
- Permite agregar una observación opcional junto con la ubicación seleccionada.
- Identifica visualmente Padres, Subconjuntos, Hijos y Materias primas.
- Mantiene un orden fijo durante todo el conteo, incluso después de guardar.
- Muestra primero la copia local y actualiza desde el servidor en segundo plano.
- Sincroniza sin volver a descargar ni dibujar todo el inventario después de cada carga.
- Conserva la vista móvil específica de MEDIOS dentro del mismo flujo general.
- No requiere cambios en MySQL ni ejecutar SQL.

## v0.92.6 · Difusión de conciliación

- Agrega el botón `Difusión conciliación` dentro del resumen de un análisis guardado.
- Genera una vista independiente y preparada para imprimir o guardar como PDF.
- Muestra el período seleccionado, confiabilidad, piezas correctas, diferencias y pendientes de análisis.
- Detalla por componente el inicial, ingresos, egresos, scrap, esperado, conteo actual, diferencia y desvío.
- Incluye estado, causa probable y comentario guardado para cada pieza.
- Añade una segunda hoja ejecutiva con top de diferencias, causas informadas, auditoría documental y balance de faltantes/sobrantes.
- Excluye `Sin causa asignada` de la distribución porcentual de causas.
- Requiere que el análisis esté guardado para asegurar una difusión reproducible.

## v0.92.5 · Confiabilidad unificada y resumen legible

- El resultado general de Difusión utiliza exactamente la misma confiabilidad que la pantalla PC.
- Calcula sobre los mismos renglones evaluables y respeta los pendientes de actualización de stock.
- Usa la tolerancia y el objetivo de confiabilidad configurados, sin valores fijos en el reporte.
- Alinea las cantidades de renglones correctos, fuera de tolerancia y pendientes con la pantalla principal.
- Aumenta el tamaño y el peso de códigos, cantidades, porcentajes y análisis en el resumen de conciliación.
- Mantiene una tipografía compacta específica para impresión.

## v0.92.4 · Resumen compacto de conciliación

- Separa el análisis en Resumen, Análisis detallado y Conciliación y remitos.
- Abre por defecto un resumen liviano con una sola fila por pieza.
- Muestra un único indicador: piezas dentro de tolerancia sobre el total del escenario de conciliación elegido.
- Permite cambiar el inventario inicial sin mezclar el control directo contra sistema con la conciliación explotada.
- Incluye inicial, ingresos, egresos, esperado, conteo actual, diferencia, desvío y análisis guardado.
- Agrega filtros rápidos y acceso directo desde cada fila a la tarjeta completa de la pieza.
- Conserva toda la auditoría de remitos y el diagnóstico avanzado en sus pestañas específicas.

## v0.92.3 · Código de cliente en los reportes

- Agrega `Código cliente` junto al código interno en todas las hojas del Excel que contienen piezas.
- Completa los códigos en bloque desde `produc01.CCOD_` para piezas y componentes explotados.
- En Egresos diferencia el código de cliente del componente destino y el de la pieza padre de origen.
- Incorpora el código de cliente en Análisis general, Conciliación, Ingresos, Egresos, Auditoría de remitos y Ajustes del sistema.
- Los análisis nuevos conservan el código dentro del resultado guardado.
- Al exportar análisis anteriores completa automáticamente los códigos faltantes, sin obligar a recalcularlos.

## v0.92.2 · Verificación completa por remito

- Reemplaza el guardado y recálculo pieza por pieza por una única operación por remito.
- Permite revisar cantidades, comentarios, períodos y verificaciones de todas las piezas antes de guardar.
- Agrega la acción rápida para marcar o desmarcar todas las piezas del remito como verificadas.
- Si sólo cambia la verificación o el comentario, guarda la auditoría sin recalcular estructuras ni consultar nuevamente los remitos.
- Si cambia una cantidad o la inclusión en un período, recalcula todos los escenarios una sola vez al finalizar el remito.
- El guardado por lote es atómico: no deja un remito guardado a medias si algún movimiento es inválido.

## v0.92.1 · Separación correcta de sistema y conciliación

- Elimina la comparación inválida entre stock directo del sistema y esperado explotado de conciliación.
- La comparación contra sistema utiliza únicamente físico directo y stock directo del mismo código.
- La conciliación muestra exclusivamente inicial, ingresos, egresos, scrap, esperado y conteo actual, todos explotados a componentes.
- Los ajustes de `produc16` pasan al bloque del sistema y se presentan como evidencia, nunca como parte de la fórmula explotada.
- Elimina diagnósticos automáticos de reconteo basados en comparar cantidades de distinta naturaleza.
- Los indicadores identifican explícitamente Control directo, Control explotado y piezas que aprueban ambos controles por separado.
- Corrige el diseño responsive para que Esperado y Conteo actual explotado permanezcan siempre visibles.
- Excel separa la conciliación de la hoja de ajustes y elimina toda columna sistema-vs-esperado.

## v0.92.0 · Indicadores porcentuales por análisis

- Recupera el indicador clásico de piezas buenas y malas dentro de la tolerancia configurada, normalmente ±5%.
- Muestra confiabilidad contra sistema, peor conciliación y consistencia integral.
- Presenta la confiabilidad de cada inventario inicial por separado para evitar que un promedio oculte un período problemático.
- Agrega porcentajes de remitos verificados, cobertura de causas, avance, resolución y ajustes explicativos de `produc16`.
- El listado de análisis guardados muestra Sistema, Conciliación e Integral sin necesidad de abrir cada análisis.
- El Excel incorpora una hoja de Indicadores con cantidades, porcentajes y detalle por escenario.

## v0.91.0 · Diagnóstico triangular y ajustes de sistema

- Consulta `produc16` por pieza y período para mostrar ajustes del sistema sin mezclarlos con ingresos o egresos físicos.
- Interpreta `OPE1_ = 999` como producto terminado y las demás operaciones como stock en proceso.
- Muestra fecha, operación, cantidad y motivo de cada ajuste, además de sus totales netos por etapa.
- Cruza físico, sistema y evolución esperada para sugerir reconteo, revisión documental o revisión del sistema.
- Indica nivel de confianza, siguiente acción y permite aplicar el estado sugerido con un clic.
- Agrega filtros por ajustes, remitos pendientes, movimientos corregidos/manuales y diferencias recurrentes.
- Permite ordenar por acción recomendada, diferencia en cantidad, porcentaje, recurrencia o código.
- Incorpora una lista de comprobación persistente por pieza para conteo, ingresos, egresos, scrap y ajustes.
- Excel agrega el cruce sistema-esperado y una hoja dedicada a los ajustes de `produc16`.
- No suma los ajustes a la conciliación física: se mantienen como evidencia para evitar cierres artificiales.

## v0.90.3 · Más espacio horizontal y gestión completa

- Integra Estado y Causa debajo del diagnóstico, aprovechando el espacio libre de la columna de la pieza.
- Ubica la Observación debajo del historial y elimina la franja inferior de análisis para reducir el alto de cada tarjeta.
- Destaca la diferencia de conciliación con cantidad, porcentaje y color según tolerancia.
- Permite eliminar un análisis guardado desde el listado, con confirmación y sin borrar inventarios ni auditorías de remitos.
- El alta de movimientos manuales busca dinámicamente en `produc01` y `mtprim01` por código o descripción.
- Las sugerencias distinguen visualmente piezas y materias primas e incluyen código de cliente cuando corresponde.

## v0.90.2 · Tarjetas compactas y listado de análisis

- El acceso principal a Análisis muestra primero un listado independiente de análisis guardados.
- Incorpora búsqueda por nombre, inventario final o inventarios iniciales y un botón dedicado para crear un análisis nuevo.
- Cada análisis guardado puede abrirse y actualizarse conservando su nombre.
- Elimina la tarjeta de escenario que repetía los datos de conciliación dentro de cada pieza.
- Resume en una única franja por período: inicial, ingresos, egresos, scrap, esperado y diferencia.
- Al desplegar la franja muestra directamente los remitos de ingreso y egreso, sin repetir la fórmula en un bloque grande.
- Distribuye scrap, ingresos y egresos en columnas para reducir el alto de cada pieza.

## v0.90.1 · Análisis y remitos en una sola pantalla

- Unifica el análisis general y la conciliación sin cambiar de pestaña o pantalla.
- Agrupa globalmente ingresos y egresos por número de remito en paneles desplegables.
- Permite verificar cada movimiento, corregir su cantidad, comentar y recalcular todos los períodos relacionados.
- Conserva el alta y la eliminación de ingresos y egresos manuales.
- Cada pieza muestra ingresos, egresos, scrap, esperado y diferencia por período.
- Cada período se despliega dentro del mismo renglón para mostrar la fórmula y los remitos que originan los totales.
- Las verificaciones, correcciones, comentarios y manuales continúan guardándose en la auditoría auxiliar existente; no requiere migraciones SQL.

## v0.90.0 · Guardado explícito y Excel de conciliación

- “Calcular escenarios” ya no guarda: el nuevo botón “Guardar análisis” solicita un nombre y confirma el alta en el historial.
- El selector de exportación permite elegir el período y siempre genera el Excel detallado de cuatro hojas usado como referencia.
- Los análisis guardados conservan su instantánea y pueden volver a exportarse sin recalcular.

## v0.89.0 · Escenarios compactos y Excel restaurado

- Las conciliaciones distribuyen hasta cuatro escenarios en una grilla y muestran primero la fecha del inventario inicial.
- El histórico prioriza también la fecha para facilitar la ubicación temporal.
- Se restauró exactamente el formato Excel de v0.87, incluida la conciliación de cuatro hojas.

## v0.88.0 · Historial de análisis y resumen de conciliación

- Cada combinación calculada queda guardada y puede reabrirse desde “Análisis guardados”.
- El conteo explotado se muestra junto al esperado y se agrega el porcentaje de desvío.
- El físico muestra las diferencias pequeñas de MP, proceso y PT contra el sistema.
- Excel incorpora porcentajes auditables mediante fórmulas; la impresión de conciliación usa un resumen tabular.

## v0.87.0 · Materia prima comparable y físico por etapa

- El análisis muestra el físico separado en MP equivalente, proceso y PT.
- La MP integra los totales físico y de sistema mediante `cantidad / CONS_`.
- `UMCO_`, la cantidad original de MP y el equivalente quedan incluidos en Excel para auditar la conversión.

## v0.86.0 · Tarjetas, Excel e impresión

- Aumenta tamaño y peso de la tipografía del análisis general.
- Presenta la conciliación en tarjetas compactas para aprovechar mejor el ancho.
- Exporta el análisis general a Excel con historial, stock por etapa, escenarios y notas.
- Exporta la conciliación con hojas de resumen, ingresos, egresos y auditoría de remitos.
- Incorpora impresión optimizada para cada una de las dos vistas.

## v0.85.0 · Módulo independiente y stock por etapa

- Incorpora Análisis de stock como pantalla principal accesible desde la navegación lateral.
- Permite elegir el inventario final dentro del módulo y conserva el acceso rápido desde cada inventario.
- Redistribuye cada fila en identidad, valores actuales, escenarios e historial para aprovechar el ancho disponible.
- Desglosa el sistema en materia prima de referencia, en proceso y producto terminado, sin sumar MP al total productivo.
- Identifica el stock asignado incluido dentro de producto terminado.

## v0.84.0 · Análisis general e investigación de conciliación

- Reúne diagnóstico, sistema, conteo directo, conteo explotado y todos los escenarios en una sola vista general.
- Muestra por pieza las diferencias contra sistema de los tres inventarios anteriores comparables.
- Reduce la navegación principal a Análisis general y Conciliación y remitos.
- Permite elegir el período dentro de Conciliación y conserva fórmula, scrap, remitos, correcciones y movimientos manuales.
- Mantiene estado, causa y observación en la vista general para revisar patrones sin cambiar de pantalla.

## v0.83.2 · Resumen cruzado diferenciado

- Muestra sistema, conteo directo, diferencia contra sistema y conteo explotado en cada pieza.
- Resume cada escenario con esperado y diferencia contra el conteo explotado.
- Traslada la fórmula y los remitos exclusivamente a la pestaña individual del período.
- Permite abrir el período correspondiente directamente desde el resumen.

## v0.83.1 · Comparaciones con granularidad correcta

- Separa el conteo directo para comparar contra sistema del conteo explotado utilizado contra el esperado de conciliación.
- Elimina el diagnóstico que comparaba sistema contra esperado, porque pertenecen a granularidades diferentes.
- Muestra ambos conteos y ambas diferencias con etiquetas explícitas en la comparación individual.

## v0.83.0 · Conciliación cruzada con auditoría compartida
- Organiza la preconciliación en resumen cruzado, una pestaña por inventario inicial y movimientos/remitos.
- Guarda cada movimiento una sola vez y comparte cantidad corregida, verificación y observación entre escenarios.
- Permite excluir un movimiento de un escenario puntual sin duplicarlo.
- Incorpora movimientos manuales generales por fecha, con resolución de materiales y estructuras de egreso.
- Permite cargar scrap por pieza y período y lo descuenta de la fórmula esperada.
- Conserva sin cambios la conciliación anterior y sus tablas de auditoría.

## v0.82.41 · Trazabilidad de ingresos y egresos

- Cada escenario de preconciliación incorpora un desplegable `Ver cálculo`.
- Expone la fórmula completa: inventario inicial más ingresos menos egresos igual a esperado.
- Detalla ingresos por remito, fecha, material y cantidad.
- Detalla egresos por remito, pieza despachada, cantidad, uso y equivalente descontado.
- Mantiene los movimientos plegados para no recargar la comparación principal.

## v0.82.40 · Preconciliación multi-origen

- Agrega un botón `Preconciliación` dentro de cada inventario.
- Permite comparar el inventario actual contra hasta cuatro inventarios iniciales.
- El inventario actual puede continuar abierto y se analizan los códigos completos.
- Cruza físico actual, stock del sistema y stock esperado por movimientos.
- Clasifica cada pieza entre gestión del sistema, movimientos, reconteo, desvío localizado, revisión completa o consistente.
- Incorpora filtros, resumen de prioridades y resultado individual por escenario.
- Guarda por pieza un estado, una causa probable y una observación propios de la preconciliación.
- Las notas se conservan en la carpeta `data` sin modificar los comentarios originales del conteo.

## v0.82.39 · Historial disponible en cada pieza

- El botón `Analizar` de cada renglón despliega el historial de esa pieza.
- Muestra sistema, físico y diferencia actuales junto con los últimos tres conteos comparables.
- Incluye orientación de tendencia para piezas correctas, pendientes o con diferencia.
- Mantiene debajo los campos existentes de causa, comentario y ajuste.
- Carga el historial únicamente al desplegar el renglón para mantener ágil la tabla.

## v0.82.38 · Diagnósticos de diferencias más visibles

- Aumenta el tamaño y peso de las etiquetas de prioridad, evolución y diferencias repetidas.
- Amplía también la explicación que acompaña cada orientación.
- Ajusta el espaciado del cartel sin modificar las reglas de diagnóstico.

## v0.82.37 · Historial de conteos más legible

- Aumenta el tamaño y peso de fechas, diferencias y porcentajes del historial.
- Refuerza el título de últimos conteos y el contraste de sus tarjetas.
- Conserva sin cambios las reglas de orientación para reconteo y diferencias repetidas.

## v0.82.36 · Análisis desplegable y orientación de reconteo

- El foco de diferencias queda cerrado por defecto dentro de cada inventario.
- El botón `Analizar diferencias` abre y cierra el panel sin cambiar de pantalla.
- Cada pieza recibe una orientación basada en sus últimos conteos: prioridad de reconteo, diferencia repetida, cambio de signo o sin antecedentes.
- La orientación es informativa y conserva causa, comentario e historial para confirmar el diagnóstico.

## v0.82.35 · Orden móvil fijo y foco de diferencias

- El recorrido móvil conserva el orden original de los códigos después de cada carga.
- La vista PC incorpora un foco de las ocho piezas con mayor diferencia absoluta.
- Cada prioridad muestra sistema, físico, diferencia, desvío, causa y comentario.
- Se comparan los últimos tres conteos equivalentes de la misma pieza, cliente y modalidad.
- El resumen de causas considera únicamente causas asignadas.
- Desde el foco se puede ir directamente al renglón de la pieza para analizarlo.

## v0.82.34 · Gráficos consolidados en una hoja

- Coloca el Top 6 primero y ocupando toda la columna izquierda.
- Apila Causas, Confiabilidad y Balance en la columna derecha.
- Evita que la hoja de gráficos se fragmente en dos páginas al imprimir.
- Mantiene el detalle del inventario con paginado flexible independiente.

## v0.82.33 · Prioridad visual en causas y códigos

- Invierte el orden del Top 6 para mostrar primero cantidad y luego porcentaje de desvío.
- Reduce el ancho de Confiabilidad y Balance para priorizar Causas y Códigos críticos.
- Amplía el espacio disponible para comentarios y explicaciones de Producción.

## v0.82.32 · Paginado de difusión sin recortes

- Permite que la tabla continúe en una segunda hoja cuando hay muchos códigos.
- Repite el encabezado de columnas y evita cortar renglones entre páginas.
- Elimina alturas y desbordamientos que podían ocultar contenido al cambiar de impresora.
- La hoja de gráficos comienza después del detalle y puede continuar si el dispositivo lo requiere.

## v0.82.31 · Comentarios en el Top de diferencias

- Muestra el comentario de cada código dentro del Top 6 de mayores desvíos.
- Consolida observaciones de distintas etapas sin perder información.
- Indica Sin comentario de forma neutra cuando todavía no existe una explicación.

## v0.82.30 · Causas pendientes sin penalización

- Excluye los códigos sin causa asignada del gráfico y de sus porcentajes.
- La distribución considera únicamente causas efectivamente informadas.
- La primera hoja conserva Sin informar para facilitar el seguimiento pendiente.

## v0.82.29 · Segunda hoja de análisis

- Agrega una segunda hoja de difusión con gráficos para Producción.
- Compara confiabilidad de Producto terminado, En proceso y Materia prima.
- Resume causas, faltantes, sobrantes, códigos correctos y mayores desvíos.
- Mantiene impresión A4 horizontal y lectura compatible con blanco y negro.

## v0.82.28 · Botón Difusión integrado

- Cambia el botón Difusión al mismo estilo visual que las demás acciones del inventario.
- Unifica altura, bordes, tipografía, espaciado, icono y comportamiento hover.

## v0.82.27 · Padres primero en difusión

- Ordena los códigos por Padre, Subconjunto, Hijo e Independiente.
- Mantiene el orden original dentro de cada grupo estructural.
- Destaca suavemente las filas Padre para pantalla e impresión en blanco y negro.

## v0.82.26 · Valores de difusión más legibles

- Aumenta el tamaño de valores, códigos, encabezados y renglones en pantalla e impresión.
- Resalta los datos numéricos y conserva mayor jerarquía para total, diferencia y desvío.
- Mantiene la compactación automática sólo para inventarios con gran cantidad de códigos.

## v0.82.25 · Detalle del stock del sistema

- La difusión separa el stock PT, en proceso y de materia prima.
- Mantiene el total del sistema productivo frente al total físico.
- El código interno pasa a ser la identificación principal y se elimina el código de cliente.

## v0.82.24 · Difusión visual con comentarios

- Mejora la presentación visual manteniendo el formato compacto de una hoja.
- Agrega una columna Comentario con las observaciones vinculadas a cada causa.
- Refuerza la lectura de resultados correctos, diferencias e indicadores generales.

## v0.82.23 · Difusión compacta en una hoja

- Reemplaza el tablero de difusión por una tabla sencilla y compacta.
- Presenta todas las piezas como renglones, con sistema, físico, diferencia, desvío y causa.
- Ajusta automáticamente la densidad según la cantidad de códigos.
- Configura la impresión en una única hoja A4 horizontal siempre que la cantidad resulte legible.

## v0.82.22 · Pantalla de difusión por inventario

- Agrega una vista ejecutiva para comunicar resultados a Producción.
- Resume confiabilidad, diferencias principales, causas y detalle por pieza.
- Adapta los indicadores para piezas, materia prima y medios.
- Permite imprimir o guardar la difusión como PDF desde el navegador.

## v0.82.21 · Conciliación limitada a códigos contados

- La explosión sólo conserva códigos que existan como renglón en al menos uno de los dos inventarios.
- Un código presente en un solo inventario también aparece, con valor cero en el inventario donde falta.
- Los componentes de estructura que no fueron contados en ninguno quedan excluidos.
- Mantiene los filtros y la agrupación rápida de movimientos incorporados en v0.82.20.
- No requiere cambios de tablas ni ejecutar SQL.

## v0.82.20 · Conciliaciones más rápidas

- Los egresos de `produc08` se filtran en MySQL por período, estado y códigos de la conciliación.
- Los movimientos repetidos se agrupan en MySQL antes de enviarlos a la aplicación.
- Las estructuras de piezas se reutilizan durante todo el cálculo.
- El registro detallado fila por fila queda desactivado por defecto.
- No requiere cambios de tablas ni ejecutar SQL.

## v0.82.19 · Conciliaciones y corrección autorizada

- Corrige el error de `Cursor.rowcount` al guardar movimientos de conciliación.
- Los inventarios cerrados muestran “Habilitar corrección”.
- La reapertura exige clave administrativa, persona que autoriza y motivo.
- La clave se configura como `INVENTORY_ADMIN_PASSWORD` en `.env`.
- La reapertura queda registrada en las observaciones del inventario.
- MEDIOS vuelve a permitir abrir el conteo móvil desde la vista de PC.
- No requiere cambios de tablas ni ejecutar SQL.

## v0.82.18 · Buscar MEDIOS por código de cliente

- El alta móvil encuentra piezas por código interno, código de cliente o descripción.
- Las coincidencias por código de cliente se priorizan en los resultados.
- En MEDIOS, la sugerencia destaca el código de cliente y muestra debajo el interno.
- No requiere cambios de tablas ni ejecutar SQL.

## v0.82.17 · Conteo móvil de MEDIOS

- MEDIOS dispone de una vista móvil rápida tipo Recorrido.
- Prioriza visualmente el código de cliente y muestra también el código interno.
- Vacíos, Llenos y Rotos se cargan directamente en cada tarjeta.
- Calcula Total encontrado, Utilizables (Vacíos) y Diferencia contra sistema.
- Permite filtrar, agregar códigos desde `produc01` y eliminar códigos sin conteo.
- Mantiene una cola local y sincronización posterior cuando falta señal.
- No requiere cambios de tablas ni ejecutar SQL.

## v0.82.16 · Eliminar códigos desde el móvil

- Cada código del modo Recorrido tiene una papelera.
- Una pieza elimina juntos sus renglones de MP, Proceso y Terminado.
- Una materia prima elimina el código y sus lotes solamente del inventario.
- Si existen registros sincronizados o pendientes, exige eliminarlos primero.
- No modifica los maestros `produc01` ni `mtprim01`.
- No requiere cambios de tablas ni ejecutar SQL.

## v0.82.15 · Alta móvil de códigos y regreso rápido

- El modo Recorrido permite agregar códigos sin abandonar el conteo.
- En MP busca y valida exclusivamente contra `mtprim01`.
- En Proceso y Terminado busca y valida exclusivamente contra `produc01`.
- Los inventarios de piezas pueden incorporar una MP encontrada durante el recorrido.
- El portal móvil muestra primero el último listado guardado y lo actualiza en segundo plano.
- La carga del inicio móvil ya no consulta programaciones, conciliaciones, causas ni reportes.
- No requiere cambios de tablas ni ejecutar SQL.

Versión 0.82.2 — migrador compatible con usuarios MySQL sin permiso CREATE.

## Migración sin cambios de esquema

`migrar_almacenes_locales_a_mysql.bat` no crea, altera ni elimina tablas.
Primero valida que las tablas requeridas ya existan y sean accesibles; después
copia los datos locales mediante operaciones idempotentes. El usuario MySQL
necesita permisos `SELECT`, `INSERT` y `UPDATE`, pero no necesita `CREATE`.

El archivo `sql/migracion_v82.sql` se conserva únicamente para que un
administrador prepare el esquema cuando corresponda. El migrador no lo ejecuta.

Versión 0.82.0 — almacenes auxiliares migrados a MySQL.

## Migración de SQLite auxiliares a MySQL

Esta versión guarda en `DATABASE_URL` los cierres mensuales, el detalle del
conteo móvil, la auditoría y exclusiones de conciliación y las relaciones entre
inventarios y reconteos. Los cuatro SQLite anteriores dejan de utilizarse.

1. Detener por completo la versión anterior.
2. Copiar el `.env` y la carpeta `data` de la v0.81.2 dentro de esta versión.
3. Confirmar que `DATABASE_URL` apunta a la base MySQL correcta.
4. Ejecutar `migrar_almacenes_locales_a_mysql.bat`.
5. Verificar el mensaje `Migración terminada correctamente`.
6. Iniciar la aplicación con `run.bat`.

El migrador valida las tablas existentes, crea un respaldo fechado dentro de
`data` y copia mediante operaciones idempotentes. No ejecuta
`sql/migracion_v82.sql`. Si informa un error, no inicie la aplicación. Conserve
los `.db` como respaldo.

Las secciones de versiones anteriores que mencionan SQLite se mantienen sólo
como historial de cambios; desde v0.82.0 esas funciones trabajan con MySQL.

Versión 0.81.2 — reconteos como inventarios vinculados.

## Versión 0.81.2: inventarios de reconteo

- Cada reconteo genera un inventario normal con código propio.
- Reutiliza conteo, autoguardado, cierre, impresión, Excel y reportes.
- Puede ser completo, por diferencias o por selección manual de piezas.
- Copia todas las etapas de cada pieza seleccionada.
- Permite mantener el stock original o capturar uno actualizado.
- El vínculo entre inventarios se guarda sólo en
  `data/relaciones_inventarios.db`; no crea tablas nuevas en MySQL.
- Desde el original y desde el reconteo se puede navegar entre ambos.

Versión 0.81.1 — filas excluibles en conciliación y reconteos locales.

## Versión 0.81.1: almacenamiento local de prueba

- Permite eliminar componentes que no interesan de una conciliación.
- La exclusión se guarda por código en `data/conciliacion_remitos.db` y se
  conserva al recalcular desde remitos.
- Las filas excluidas dejan de participar en totales y confiabilidad.
- Los reconteos se guardan exclusivamente en `data/reconteos.db`.
- No se crean tablas de reconteo ni exclusiones en MySQL.
- MySQL continúa utilizándose solamente como fuente productiva de lectura.

Versión 0.81.0 — reconteos completos o parciales con stock original o actualizado.

## Versión 0.81.0: reconteos

- Conserva el primer conteo cerrado como evidencia.
- Permite iniciar un reconteo completo, manual o automático de diferencias.
- Permite mantener la foto de stock original o consultar y congelar una nueva.
- Autoguarda las cantidades del reconteo y permite cerrarlo al completarlo.
- Una vez cerrado, compara sistema y conteo originales contra stock y reconteo.
- Corrige la columna productiva de unidad de materia prima a `UNDAD_`.

Versión 0.80.5 — diagnósticos y confiabilidad consistentes con la tolerancia.

## Versión 0.80.5: tolerancia y confiabilidad sincronizadas

- Una diferencia distinta de cero dentro de la tolerancia configurada se
  identifica como `Dentro de tolerancia`, no como diferencia real de stock.
- El mismo criterio se aplica al abrir el inventario y al editar el conteo.
- Tras cada autoguardado se actualiza la confiabilidad de la lista general sin
  recargar el detalle ni interrumpir el campo que se está completando.

## Versión 0.80.4: corrección del stock asignado

- El reporte ASIGNADO se aplica siempre sobre el renglón `TERMINADO`.
- No depende de que la pieza tenga operaciones.
- No depende de que la pieza aparezca en el reporte PRD.
- Al recalcular recupera el asignado desde `TERMINADO`.
- También reconoce y limpia valores heredados que versiones anteriores hayan
  guardado en `OPERACION` o `PROCESO_GLOBAL`.
- No requiere migraciones ni cambios en MySQL.

## Versión 0.80.3: búsqueda histórica por pieza

- Busca piezas contadas por código interno, código de cliente o descripción.
- Muestra cada inventario cerrado donde apareció la pieza.
- Separa los resultados por etapa y operación.
- Compara stock de sistema, conteo físico, diferencia y desvío.
- Muestra causa, observación, tolerancia y estado del ajuste.

Versión 0.80.2 — autoguardado seguro en conteos y conciliaciones.

## Versión 0.80.2: autoguardado

- Guarda automáticamente conteo físico, causas, ajustes, observaciones y remitos.
- Guarda automáticamente scrap, cantidades, verificaciones y observaciones de conciliación.
- Informa los estados pendiente, guardando, guardado y error.
- Advierte antes de recargar o cerrar si queda un cambio pendiente o fallido.
- Conserva los botones de guardado manual como respaldo.

Versión 0.80.1 — egresos válidos por estado, sin excluir por `LACTIVO_`.

## Versión 0.80.1: LACTIVO_ informativo en egresos

- Los movimientos de `produc08` se consideran válidos cuando `STAT_ = 'D'`.
- `LACTIVO_` se conserva en las trazas de diagnóstico, pero ya no descarta
  padres, subconjuntos ni componentes despachados directamente.
- La misma regla se aplica al localizar los remitos de corte y en todos los
  caminos auxiliares de consulta de egresos.
- El diagnóstico detallado de la versión 0.80.0 continúa activo.

## Versión 0.80.0: diagnóstico de egresos

- La consulta del intervalo trae las filas de `produc08` sin descartarlas antes
  por `GCOD_`, `LACTIVO_` o `STAT_`.
- Python informa por consola si cada fila fue incluida o descartada y el motivo.
- Muestra la estructura admitida, el tratamiento directo/explotado y cada suma.
- Las mismas trazas quedan en `data/conciliacion_debug.log`.
- El diagnóstico está activo por defecto. Puede apagarse con
  `MOVIMIENTOS_DEBUG=0` en `.env`.

## Versión 0.79.9: intervalo por fecha de los documentos de corte

- Los números de remito inicial y final se usan para localizar su `FECH_`.
- Después se incluyen todos los movimientos cronológicamente ubicados entre
  ambas fechas, aunque pertenezcan a otra serie de numeración.
- Un egreso directo con remito `39950`, por ejemplo, entra si su fecha está
  entre las fechas de los cortes `50609` y `50808`.
- El corte inicial continúa excluido y el final incluido.
- Si un documento de corte no aparece, sólo ese extremo usa la fecha del
  inventario como respaldo.

## Versión 0.79.8: devoluciones de componentes en produc08

- Los egresos pueden originarse en un padre, subconjunto o componente de la
  estructura de las piezas comunes a ambos inventarios.
- Un componente final informado directamente en `produc08` se descuenta con
  coeficiente 1.
- Un subconjunto informado directamente se explota desde ese código hasta los
  componentes finales comparables.
- Se mantienen el control agrupado por remito, las verificaciones, correcciones
  y egresos manuales de la versión anterior.

## Versión 0.79.7: control por remito y egresos editables

- Agrupa ingresos y egresos por número de remito y permite desplegar sus piezas.
- El encabezado de cada remito muestra su fecha, cantidad de líneas y avance de
  verificación sin sumar materiales o piezas de unidades incompatibles.
- Agrega verificación, observación y corrección de cantidad a cada egreso.
- La cantidad original de `produc08` permanece visible cuando se corrige y la
  nueva cantidad recalcula todos los componentes explotados de esa línea.
- Permite agregar y eliminar egresos manuales como despachos directos.
- Conserva correcciones, verificaciones y movimientos manuales al recalcular.
- La actualización de esquema es automática únicamente en
  `data/conciliacion_remitos.db`; no modifica MySQL.

## Versión 0.79.6: auditoría editable de movimientos

- Cada extremo del intervalo usa remito si existe o fecha si falta.
- Los ingresos permiten verificación, observación y corrección de cantidad.
- Se pueden agregar y eliminar ingresos manuales con trazabilidad.
- Scrap manual por componente, incluido en el stock esperado.
- Los despachos directos de componentes en `produc08` se suman con uso 1.
- Los nuevos datos permanecen en `data/conciliacion_remitos.db`.

## Versión 0.79.5: corte aproximado por fecha

- Para ingresos y egresos se intenta primero el corte exacto por número de
  remito, excluyendo el inicial e incluyendo el final.
- Si falta cualquiera de los dos remitos de un tipo de movimiento, sólo ese
  cálculo pasa automáticamente a las fechas de los inventarios.
- El intervalo alternativo excluye la fecha del inventario inicial e incluye
  la fecha del inventario final.
- Ingresos y egresos resuelven su criterio de manera independiente: uno puede
  quedar exacto por remitos y el otro aproximado por fechas.
- La conciliación muestra el criterio aplicado y una advertencia explícita
  cuando usa la aproximación.
- La actualización de `conciliacion_remitos.db` es automática. No requiere
  cambios ni migraciones en MySQL.

## Versión 0.79.4: alcance correcto de movimientos

- La conciliación se construye sólo con códigos raíz presentes tanto en el
  inventario inicial como en el final.
- Las estructuras de ambos inventarios se explotan únicamente desde esas
  piezas comunes; los componentes comparables son la intersección resultante.
- Los ingresos consultan sólo los `CMAT_` relacionados mediante
  `produc01.MATE_` con los códigos de pieza incluidos en la conciliación.
- La auditoría de ingresos muestra por separado el material del remito y la
  pieza relacionada utilizada por el cálculo.
- Los egresos consultan sólo los `produc08.GCOD_` raíz presentes en ambos
  inventarios y recién después explotan `produc10` hacia sus componentes.
- Un movimiento ajeno ya no puede crear un renglón nuevo en la conciliación.
- `Recalcular desde remitos` también limpia los renglones ajenos que hayan sido
  creados por la versión 0.79.3.
- No requiere migraciones ni cambios adicionales en MySQL o en las SQLite
  locales.

## Versión 0.79.3: mes de cierre local

- Las tablas existentes de inventarios y programaciones continúan en MySQL.
- `mes_cierre` y `mes_cierre_proximo` se guardan en
  `data/meses_cierre.db` y no agregan columnas a MySQL.
- Al iniciar se asigna localmente un cierre inicial a los registros históricos
  que todavía no tengan uno.
- El conteo móvil permanece en `data/conteo_cajas.db`.
- La auditoría de remitos permanece en `data/conciliacion_remitos.db`.
- No hay que ejecutar una migración MySQL para las versiones 0.78 o 0.79.

## Versión 0.79.2: separación correcta de bases

- `DATABASE_URL` sigue usando la base MySQL existente para plantillas,
  inventarios, programaciones, usuarios, causas, conciliaciones y sus totales.
- `PRODUCTION_DATABASE_URL` continúa leyendo los maestros y movimientos reales,
  incluidas `mtprim06`, `produc08` y `produc10`.
- El detalle caja por caja permanece en `data/conteo_cajas.db`.
- La foto calculada y el detalle auditable de los remitos se guardan únicamente
  en `data/conciliacion_remitos.db`.
- No se agregan en MySQL las ocho columnas introducidas originalmente por la
  migración v0.79.
- No usar `USE_LOCAL_APP_DATABASE`: esta versión respeta siempre el
  `DATABASE_URL` configurado.
- Para esta corrección no se ejecuta ninguna migración v0.79 en MySQL.

## Versión 0.79: ingresos y egresos verificables

- La conciliación toma automáticamente los ingresos desde `mtprim06`, usando
  únicamente registros `CODI_ = 'RC'`.
- El intervalo excluye el remito del inventario inicial e incluye el del
  inventario final.
- Los egresos se toman desde `produc08` con `STAT_ = 'D'`. Desde la versión
  0.80.1, `LACTIVO_` es sólo informativo y no restringe los movimientos.
- Un documento como `X0007-00036950` se normaliza como corte `36950`, que es el
  formato cargado manualmente en los inventarios.
- Cada pieza despachada se explota por `produc10`; la conciliación suma el
  consumo equivalente de cada componente terminal.
- Los totales calculados permanecen editables, pero se conserva y muestra el
  valor original obtenido desde los remitos.
- Dos secciones desplegables permiten verificar cada remito de ingreso y de
  egreso contra el comprobante físico.
- El detalle de egreso muestra pieza origen, cantidad despachada, uso de
  estructura y cantidad equivalente.
- `Recalcular desde remitos` vuelve a leer las tablas productivas después de
  una corrección y reemplaza los valores manuales actuales.
- Se advierte cuando alguno de los cuatro remitos de corte no existe entre los
  movimientos activos.

La persistencia nueva de esta función fue trasladada a SQLite local en v0.79.2;
no existe una migración v0.79 para MySQL en este paquete.

## Versión 0.78: fecha de conteo y mes de cierre independientes

- Cada inventario guarda un `mes_cierre` explícito, independiente de su fecha
  prevista, realizada o de cierre operativo.
- Al crear un inventario no programado se propone el mes de la fecha real y se
  puede cambiar antes de generarlo.
- Las programaciones guardan el mes de cierre de su próxima ocurrencia.
- En una programación mensual, la fecha prevista y el mes de cierre avanzan un
  mes calendario por cada ocurrencia. Ejemplo: 02/08 cierre julio; 02/09 cierre
  agosto.
- En una programación semanal, al generar se propone para la próxima semana el
  mes de su nueva fecha. Una excepción se modifica sólo para la ocurrencia que
  corresponda.
- Una programación de una sola vez conserva el mes elegido.
- Reprogramar una fecha no cambia automáticamente el mes de cierre ya asignado.
- El mes de cierre de cualquier inventario se puede corregir desde `Datos del
  inventario`, incluso después de generado.
- Los reportes filtran exclusivamente por `mes_cierre`; el gráfico diario y
  semanal conserva la fecha real de realización.
- Los mensuales no permiten generar dos inventarios para el mismo mes de cierre
  desde una misma programación.
- La impresión y el Excel muestran el mes de cierre.

La asignación inicial se hace automáticamente en SQLite local. Después conviene
revisar desde Programados las ocurrencias históricas que caen a comienzos de
mes, ya que el sistema no puede saber si corresponden al cierre anterior.

## Versión 0.77: mes de cierre en reportes

- Reemplaza los períodos móviles por un selector de mes de cierre.
- Abre por defecto el último mes completo.
- Los inventarios de una programación mensual se asignan al mes de su
  `fecha_programada`, aunque hayan sido cerrados en los primeros días del mes
  siguiente.
- Los inventarios no programados, semanales y de una sola vez se asignan al
  mes de su fecha real de cierre.
- La tendencia contra el período anterior compara contra el mes de cierre
  inmediatamente anterior.
- El alcance del reporte informa cuántos mensuales fueron reasignados por su
  fecha programada.
- No requiere migraciones ni cambios en MySQL.

## Versión 0.76: tipo de inventario en reportes

- Agrega el filtro global `Todos / Piezas / Medios / Materia prima`.
- El tipo se combina con período, cliente y origen programado/no programado.
- Agrega un resumen comparativo de confiabilidad por tipo de inventario.
- Los inventarios de modalidad `MEDIOS` se clasifican como Medios.
- Los inventarios de categoría `MATERIA_PRIMA` se clasifican como Materia prima.
- Los demás, incluidos los cíclicos de piezas, se clasifican como Piezas.
- No requiere migraciones ni cambios en MySQL.

## Versión 0.75: comparación por cliente y programación

- Nuevo gráfico de confiabilidad por cliente.
- Compara inventarios programados y no programados en barras separadas.
- Nuevo filtro global `Todos / Programados / No programados`.
- La condición programada se reconoce por `programacion_id` o
  `fecha_programada`, incluyendo registros históricos.
- No requiere cambios ni migraciones de MySQL.

## Versión 0.74: evolución por día

- El gráfico de confiabilidad permite alternar entre día, semana y mes.
- La vista diaria consolida todos los inventarios cerrados en cada fecha.
- Cada punto informa confiabilidad, inventarios y renglones evaluados.
- Cuando hay muchas fechas, el gráfico permite desplazamiento horizontal.
- Mantiene los filtros generales de período y cliente.
- No requiere migraciones ni cambios en MySQL.

## Versión 0.73: varias cajas iguales

- El conteo móvil permite indicar cantidad por caja y número de cajas.
- Muestra el total antes de confirmar (por ejemplo, `8 × 12 = 96`).
- Cada caja se conserva como un registro individual en el historial.
- Las cargas múltiples funcionan también sin conexión y se sincronizan por lotes.
- No requiere migraciones ni cambios en MySQL o en la base local de cajas.

## Versión 0.72: piezas desplegables

- La pantalla móvil muestra un encabezado por código de pieza.
- Al desplegarlo aparecen solamente sus etapas disponibles: materia prima,
  proceso/operaciones y pieza terminada.
- Cada etapa conserva su propio historial de cajas y total físico.
- La cantidad de una caja debe ser un número entero mayor que cero; se valida
  tanto en el celular como en el servidor.
- No requiere migraciones ni cambios en MySQL.

## Versión 0.71: cajas en base local

- No requiere crear tablas ni agregar columnas en MySQL.
- El inventario y el total físico continúan guardándose en la base principal.
- El detalle caja por caja se guarda automáticamente en
  `data/conteo_cajas.db`.
- La revisión que evita que una PC pise cargas del celular también queda en
  esa base local.
- Al reemplazar o mover la aplicación, conservá la carpeta `data` para no
  perder el historial detallado de cajas.
- La ubicación puede cambiarse con `LOCAL_COUNT_DATABASE_PATH` en `.env`.

## Versión 0.70: conteo móvil

- Desde el detalle del inventario, `Conteo móvil` abre una pantalla adaptada
  al celular.
- El buscador filtra por código, descripción, lote u operación.
- Cada caja se registra sobre el renglón exacto y suma su cantidad al conteo
  físico existente.
- El historial permite eliminar una caja cargada por error.
- Cada carga se guarda primero en el celular. Si se corta el Wi-Fi queda como
  `Pendiente de sincronizar` y se envía automáticamente cuando vuelve la red.
- Los identificadores únicos evitan duplicar cajas durante un reintento.
- Si la pantalla de PC quedó desactualizada porque otro celular contó, el
  sistema impide que `Guardar conteo` pise esos registros y pide recargar.
- Después de abrir una vez el inventario móvil, la pantalla y la última copia
  del inventario pueden seguir usándose durante un corte de red.
- En la versión 0.71 esta función ya no requiere la migración v0.70 de MySQL.

## Versión 0.69: autocompletado manual de materia prima

- El campo Código busca mientras se escribe en `mtprim01.CODGO_` y `mtprim01.DESCR_`.
- Los resultados se muestran en una lista propia con código, descripción y datos dimensionales.
- Se puede recorrer la lista con las flechas y elegir con Enter, o seleccionar con el mouse.
- Los errores del buscador se muestran debajo del campo en lugar de quedar ocultos.
- La validación exacta contra `mtprim01` se mantiene al agregar y al generar el inventario.
- No requiere migración de MySQL.

## Versión 0.68: validación manual de materia prima

- Los códigos ingresados como materia prima se validan contra
  `mtprim01.CODGO_` antes de agregarse al listado.
- La búsqueda y la validación toleran espacios de relleno y diferencias de
  mayúsculas en el código almacenado.
- Se corrigió el nombre del campo de unidad de `mtprim01` a `UNIDAD`.
- La consulta de stock por lote también normaliza `mtprim05.CMAT_`.
- No requiere migraciones ni cambios en la base de datos.

## Versión 0.67: stock asignado desde Excel

- La actualización de stock incorpora un cuarto archivo opcional, `Stock
  asignado`, con las columnas `ccodmat` y `ncantidad`.
- Se aceptan archivos `.xls` y `.xlsx`.
- Las filas repetidas de un mismo código se suman.
- El stock asignado se suma al stock en proceso y se muestra por separado
  dentro de la tarjeta como `Asignado`.
- Si se actualiza desde MySQL o desde los otros reportes sin adjuntar un nuevo
  archivo de asignados, se conserva el último valor importado.
- Requiere ejecutar una vez `sql/migracion_v67.sql` con un usuario administrador.

## Versión 0.66: encabezado de conteo corregido

- El encabezado fijo ya no deja un margen vacío dentro de la tarjeta.
- La cabecera de columnas y el primer renglón dejan de quedar debajo del
  bloque `Detalle del conteo`.
- `Guardar conteo` continúa visible al desplazarse por el inventario.
- El fondo opaco y el borde inferior evitan que se transparenten los datos que
  pasan por debajo.
- No requiere migraciones ni cambios en MySQL.

## Versión 0.65: análisis más compacto

- El selector de causa mantiene un ancho fijo de 190 px.
- El texto inicial se simplificó a `Sin causa`.
- La observación aprovecha el espacio liberado.
- Los bloques de etapa y ajuste quedan alineados y con menos espacio desperdiciado.
- No requiere cambios en MySQL.

Esta versión no modifica tablas ni columnas de la base de datos. Para
actualizar desde v0.63 no hace falta ejecutar ninguna migración SQL.

En el detalle de un inventario:

- `Archivo` agrupa la impresión y la exportación a Excel.
- `Gestionar` agrupa agregar artículos, actualizar stock y eliminar.
- `Cerrar inventario` permanece visible en la cabecera.
- `Guardar conteo` está junto al aviso de cambios sin guardar.
- El encabezado del conteo permanece visible al desplazarse por los renglones.
- Las métricas y los paneles plegados ocupan menos altura.

## Personalizar visualmente los renglones

Los estilos de la vista `Por pieza` están en:

```text
app/static/css/styles.css
```

Los selectores principales son:

- `.piece-count-table`: tabla completa y ancho de sus columnas.
- `.piece-summary-row > td`: alto y espaciado general de cada renglón.
- `.piece-summary-identity`: código CGR, código de cliente y descripción.
- `.stage-line`: tarjeta individual de Proceso o Pieza terminada.
- `.stage-line > div small`: nombre de la operación o etapa.
- `.stage-line > div span`: etiqueta gris que contiene “Sistema”.
- `.stage-line > div strong`: número de stock del sistema.
- `.stage-line label`: texto “Físico”.
- `.stage-line input`: casilla donde se carga el conteo.
- `.productive-total`: bloque de Total productivo.
- `.summary-deviation`: porcentaje de desvío total de la pieza.
- `.piece-diagnosis`: bloque de Diagnóstico.
- `.count-row-actions`: columna de Analizar y papelera.

Al final del archivo existe un bloque `@media screen` que puede sobreescribir
algunos tamaños de letra. Si un cambio no se refleja, buscá allí el mismo
selector y ajustalo también.

La columna `Uso` de las planillas de flujo horizontal y resumen vertical ahora
muestra el valor guardado en cada renglón del inventario. El editor de
planillas permite definir, para cada columna y versión:

- tamaño de fuente entre 5 y 18 pt;
- texto normal o en negrita;
- además de orden, visibilidad, título y ancho.

Los estilos se guardan en `configuracion_sistema`, asociados a la versión y a
la clave estable de cada columna. Esta solución no agrega tablas ni columnas,
por lo que la actualización desde v0.59 no requiere ejecutar SQL ni otorgar
permisos `ALTER`.

## Versión 0.59: configuración organizada

La pantalla `Configuración` ahora se abre desde el engranaje inferior de la
barra lateral y separa el sistema en tres bloques:

- Catálogos: tipos de inventario, personas, sectores y causas.
- Indicadores: tolerancia, objetivo, alerta por cliente y muestra mínima.
- Planillas de impresión: formatos y diseños guardados.

Esta actualización no modifica la estructura de la base de datos y no requiere
ejecutar una migración de MySQL.

## Catálogos escalables

En `/configuracion/catalogos` se administran:

- Tipos de inventario, con nombre, motor operativo, modalidad, formato
  predeterminado, orden y estado.
- Sectores.
- Personas, con sector, legajo y contacto opcional.

Las personas activas se utilizan como responsables y colaboradores en
inventarios y programaciones. Los nombres se guardan como una foto histórica:
renombrar o desactivar una persona no modifica inventarios anteriores.

Las plantillas y los inventarios guardan `tipo_inventario_codigo`. Los tipos
nuevos reutilizan uno de los motores estables (`PIEZAS`, `MATERIA_PRIMA` o
`CICLICO`), por lo que las variantes futuras del mismo comportamiento se
agregan desde la pantalla sin crear columnas ni modificar MySQL.

Para actualizar una instalación MySQL v0.57, ejecutá una sola vez:

```text
sql/migracion_v58.sql
```

## Versión 0.57: diseños con nombre

## Nombres y selección de versiones

Cada diseño puede guardarse con un nombre reconocible, por ejemplo
`Conteo estándar`, `Honda compacta` o `Con firmas`. El número técnico de
versión se mantiene automáticamente para conservar el historial.

En `/configuracion/planillas` se puede:

- elegir una versión anterior como punto de partida;
- editar su configuración;
- asignar un nombre;
- guardarla como una versión nueva, sin sobrescribir la anterior.

En la pantalla de impresión se puede elegir el formato y luego cualquiera de
los diseños guardados compatibles. La selección sólo afecta esa impresión.
El inventario conserva en `formato_version_id` la versión que tenía asociada.

Para actualizar una instalación MySQL v0.56, ejecutá una sola vez:

```text
sql/migracion_v57.sql
```

## Editor de planillas

La página `/configuracion/planillas` permite personalizar los diseños sin
modificar HTML o CSS:

- orden, visibilidad y título de las columnas;
- ancho porcentual mediante valor numérico o arrastre en la vista previa;
- orientación A4;
- márgenes;
- tamaño general de letra y tamaño específico por columna;
- negrita configurable por columna;
- altura de fila;
- bloque de firmas.

Cada guardado crea una fila nueva en `formato_versiones`. Los inventarios
conservan `formato_version_id`, por lo que una modificación futura no cambia
la impresión histórica.

La versión incorpora:

- `formatos_impresion`;
- `formato_versiones`;
- `formato_columnas`;
- la referencia `inventarios.formato_version_id`.

Si la base MySQL ya estaba funcionando con la v0.55, detené el sistema y
ejecutá una sola vez en MySQL Workbench:

```text
sql/migracion_v56.sql
```

Después iniciá la aplicación normalmente. Los diseños predeterminados y la
versión inicial de los inventarios existentes se completan automáticamente.
En una instalación MySQL nueva, `sql/schema_mysql.sql` ya contiene todo el
esquema y no se ejecuta `migracion_v56.sql`.

## Migrar los datos anteriores a MySQL

La raíz del proyecto incluye `migrar_sqlite_a_mysql.py`. El script copia la
base `inventarios_demo.db` a la base MySQL indicada por `DATABASE_URL` en
`.env`, conservando los IDs y las relaciones entre:

- causas y configuración;
- plantillas y artículos;
- programaciones;
- inventarios y renglones;
- conteos, observaciones y ajustes;
- conciliaciones.

Antes de usarlo:

1. Detené el sistema y cerrá cualquier terminal que esté ejecutando Uvicorn.
2. Confirmá que `.env` ya apunte a la base MySQL propia del sistema.
3. Confirmá que `inventarios_demo.db` esté en la raíz del proyecto.
4. Hacé doble clic en:

```text
migrar_sqlite_a_mysql.bat
```

También podés ejecutarlo desde una terminal:

```powershell
python migrar_sqlite_a_mysql.py
```

El migrador muestra la cantidad de registros de ambas bases y exige escribir
`MIGRAR` antes de reemplazar el contenido de MySQL. Antes de modificarla crea
automáticamente, dentro de `backups`, una copia de SQLite y un respaldo JSON
del contenido previo de MySQL.

Toda la copia se ejecuta dentro de una transacción. Si una fila no puede
insertarse o se rompe una relación, MySQL vuelve al estado anterior. Al final
se comparan nuevamente todas las cantidades por tabla.

La migración no utiliza ni modifica `PRODUCTION_DATABASE_URL`.

Si la SQLite tiene otro nombre o ubicación:

```powershell
python migrar_sqlite_a_mysql.py --sqlite "C:\ruta\inventarios_demo.db"
```

La opción `--si` permite omitir la confirmación escrita y está pensada sólo
para ejecuciones controladas.

El migrador conserva las tablas históricas y admite que el destino v0.58 tenga
la nueva clasificación. Antes de usarlo, abrí una vez la base SQLite con esta
versión. En MySQL aplicá las migraciones pendientes hasta
`migracion_v58.sql`.

## Calendario y legibilidad

- El calendario utiliza menos altura en los resúmenes, la barra de navegación
  y las celdas sin eventos.
- Las tarjetas muestran plantilla, cliente, categoría, responsable,
  colaboradores y estado.
- La vista semanal también reduce el espacio vacío.
- Se aumentaron tamaños y contraste de textos secundarios en inventarios,
  programaciones, plantillas, conteos, reportes y configuración.
- La impresión y la imagen del cronograma conservan los colaboradores.

## Reglas de indicadores

La página `Configuración de causas` incorpora un bloque independiente para
administrar:

- tolerancia porcentual del conteo;
- objetivo general de confiabilidad, inicialmente 90%;
- umbral de alerta por cliente;
- cantidad mínima de renglones necesaria para emitir esa alerta.

Una fila dentro de la tolerancia se considera correcta y no requiere ajuste
en el sistema. Si el stock teórico y el físico son cero, el desvío es 0%. Si
el teórico es cero y el físico es positivo, el desvío se informa como 100%.
El cálculo es el mismo en el detalle, los resúmenes y los reportes.

SQLite crea la tabla nueva automáticamente al iniciar. Para MySQL se incluye
`sql/migracion_v52.sql`.

## Reportes e indicadores

El botón `Reportes` abre una página independiente con filtros de período y
cliente. Para evitar resultados provisorios, los cálculos toman únicamente
inventarios cerrados.

- Confiabilidad global ponderada por renglón evaluable.
- Inventarios realizados y renglones fuera del ±5%.
- Diferencias ajustadas y ajustes pendientes.
- Cobertura de causas asignadas.
- Evolución semanal o mensual de la confiabilidad.
- Resumen por cliente con tendencia contra el período anterior.
- Ranking de causas, incluyendo `Sin causa asignada`.
- Alertas por confiabilidad baja con muestra suficiente, ajustes pendientes,
  programaciones vencidas y códigos con diferencias repetidas.

Las cantidades físicas de artículos diferentes no se suman entre sí: el
tablero trabaja con inventarios, renglones y porcentajes para no mezclar
unidades ni escalas.

El panel de análisis mantiene la observación como campo central y ubica
`Ajustado en sistema` a su derecha. El mismo orden se aplica en la vista por
pieza, detallada y de medios. Esta versión conserva la migración
`sql/migracion_v49.sql`; no agrega columnas nuevas.

## Ajustes realizados en el sistema

Cada renglón del inventario incorpora, dentro de `Causa / observación`, la
opción `Ajustado en sistema`.

- La marca es independiente de la causa y la observación.
- Al activarla se registra automáticamente la fecha y hora.
- Si se desmarca, se elimina la fecha del ajuste.
- El botón de análisis muestra `✓ Ajustado`; en la vista por pieza indica
  cuántos estadios están ajustados sobre el total.
- El resumen y el detalle histórico del Excel exportan tanto el estado como la
  fecha del ajuste, preparados para futuros indicadores en Power BI.

SQLite incorpora las columnas automáticamente. Para MySQL se incluye
`sql/migracion_v49.sql`.

## Listados manuales y artículos adicionales

Al generar un inventario manual se pueden validar y agregar varios códigos a
una lista previa. El listado muestra código y descripción, permite quitar
artículos antes de generar y evita códigos repetidos.

- Un inventario manual contiene piezas o materias primas, sin mezclar ambos
  tipos para conservar una impresión y comparación coherentes.
- En piezas, la opción `Incluir material sin usar` se conserva individualmente
  para cada código agregado.
- Cualquier inventario abierto, ya sea de plantilla, programado, manual o
  cíclico, permite usar `+ Agregar artículo`.
- El tipo admitido se adapta a la categoría del inventario y los conteos ya
  escritos se preservan antes de incorporar el nuevo artículo.
- Los inventarios cerrados no pueden ampliarse y tampoco se permiten códigos
  duplicados.

Esta versión no agrega columnas nuevas: no requiere migración SQL.

## Rol dentro de la estructura

Las piezas se clasifican automáticamente consultando `produc10`:

- `Padre`: aparece como `VCOD_`.
- `Subconjunto`: aparece como `VCOD_` y también como `GCOD_`.
- `Hijo`: aparece como `GCOD_`.
- `Independiente`: no participa en ninguna relación registrada.

El rol queda guardado como una foto dentro de cada inventario y plantilla. En
pantalla se muestra con color lateral y una etiqueta escrita; las planillas de
impresión conservan ambos recursos para seguir siendo claras aun en blanco y
negro. La exportación detallada a Excel incluye la columna `Tipo estructura`.

SQLite incorpora las columnas automáticamente. Para MySQL se incluye
`sql/migracion_v47.sql`.

## Vigencia de plantillas

Cada plantilla registra su fecha de creación y su última actualización. Desde
la pantalla de edición puede marcarse como activa o inactiva.

- Las plantillas inactivas conservan sus códigos y todo el historial.
- No pueden utilizarse ni programarse mientras permanezcan inactivas.
- Al desactivar una plantilla se pausan sus programaciones activas.
- Al reactivarla vuelve a estar disponible; las programaciones anteriores se
  reanudan manualmente.

SQLite incorpora la columna automáticamente. Para MySQL se incluye
`sql/migracion_v45.sql`.

## Inventarios de medios

Al crear un inventario de piezas podés elegir **Medios: vacíos, llenos y
rotos**. Esta modalidad:

- genera una sola fila por código y toma el stock terminado de `produc01.STOK_`
  o del reporte Excel de PT;
- registra por separado vacíos, llenos y rotos;
- calcula el total físico como la suma de los tres valores;
- conserva como indicador auxiliar los medios utilizables (`vacíos`);
- incluye una planilla horizontal específica y el desglose completo en Excel.

Para MySQL, aplicá `sql/migracion_v43.sql`. En SQLite las columnas nuevas se
agregan automáticamente al iniciar la aplicación.

Versión local y editable del sistema de inventarios. Está pensada para trabajar
en Windows con Visual Studio Code y para conectarse posteriormente a la base
productiva.

## Qué incluye

- FastAPI como backend.
- HTML, CSS y JavaScript sin frameworks de frontend.
- SQLAlchemy como capa de acceso a datos.
- Compatibilidad con SQLite para pruebas inmediatas.
- Compatibilidad con MySQL mediante PyMySQL.
- Autocompletado desde dos caracteres para buscar piezas por código, código de
  cliente o descripción, y materias primas por código o descripción.
- Selección de sugerencias con mouse o con las teclas de dirección y Enter.
- Plantillas predefinidas por cliente.
- Programación de inventarios para una fecha, con repetición única, semanal o
  mensual.
- Pantalla independiente de `Programados`, con indicadores de vencidos, para
  hoy, próximos y activos.
- Acciones para generar el inventario cuando corresponde, editar, pausar,
  reanudar o eliminar una programación.
- Una programación activa puede generarse antes, durante o después de la fecha
  tentativa; la fecha nunca bloquea el botón.
- El inventario conserva por separado la fecha programada, la fecha real de
  generación y la fecha/hora de cierre. Estos datos aparecen en pantalla,
  impresión y Excel.
- Cada inventario puede registrar un responsable y varios colaboradores. En
  las programaciones, los colaboradores se copian al inventario generado.
- Cada inventario se identifica como `Interno` o `Con cliente`; los registros
  existentes se migran automáticamente como internos.
- El comentario del inventario puede escribirse al crearlo y modificarse desde
  el detalle mientras esté abierto. También se incluye en la impresión y Excel.
- Cada renglón del conteo permite seleccionar una causa de diferencia y escribir
  una observación. Ambos datos quedan en el historial y se exportan a Excel.
- Las causas usan códigos estables y un catálogo independiente, preparado para
  indicadores históricos por causa, artículo, cliente, etapa u operación.
- La página `/configuracion/causas`, accesible desde el engranaje, permite
  crear, editar, ordenar, categorizar, activar y desactivar causas. Sólo pueden
  eliminarse las que todavía no tienen historial asociado.
- En inventarios de piezas se puede alternar entre `Por pieza` y `Detallada`.
  La vista consolidada presenta material, proceso y terminado en una sola fila,
  pero conserva los mismos renglones internos para el historial y Power BI.
- El total productivo suma proceso y terminado, sin mezclar materia prima que
  podría estar expresada en otra unidad. Cuando ese total coincide pero las
  etapas no, se señala una posible producción o reclasificación pendiente.
- La tabla consolidada se adapta al ancho disponible, compacta los datos de
  cada estadio y mantiene fija la columna `Análisis` en el borde derecho.
- El panel `Datos del inventario` inicia contraído, conserva un resumen del tipo
  y comentario, y se despliega sólo cuando hace falta editar esos campos.
- Un inventario abierto permite quitar un renglón desde la vista detallada o
  una pieza completa, con todos sus estadios, desde la vista consolidada.
- El origen `Manual` permite generar un conteo sin plantilla buscando una sola
  pieza, componente o materia prima. Para piezas se configura proceso global o
  por operación, inclusión de MP y control de remitos.
- La interfaz de escritorio utiliza una densidad compacta: encabezado y menú
  lateral más bajos, paneles y tablas con menos espacio vacío y acciones más
  pequeñas.
- En el detalle, los datos generales y el control de remitos comparten una fila
  cuando hay espacio. El diseño vuelve a una columna en pantallas angostas.
- Las plantillas se muestran en filas compactas con sus datos principales y
  acciones directas. Los códigos se despliegan sólo al seleccionar
  `Ver códigos`.
- El buscador de plantillas encuentra coincidencias por nombre, cliente,
  descripción, códigos de pieza, códigos de cliente y materiales.
- Al generar una programación se congela el stock en ese momento. Las
  programaciones semanales y mensuales avanzan automáticamente a la próxima
  fecha; las de una sola vez quedan completadas.
- Navegación de inventarios entre `En curso`, `Realizados` y `Todos`.
- Navegación mediante páginas y URLs independientes:
  `/inventarios`, `/programados`, `/plantillas` y `/conciliaciones`.
  Todas comparten el mismo diseño y la ruta `/` redirige a inventarios.
- Vista de programaciones en formato lista o calendario.
- Calendario mensual de seis semanas y agenda semanal, con navegación hacia
  períodos anteriores y futuros.
- Proyección visual de las próximas ocurrencias semanales y mensuales, además
  de los inventarios ya generados y realizados.
- Cada evento muestra plantilla, cliente, tipo de inventario, responsable y
  estado. Al seleccionarlo abre la programación o el inventario correspondiente.
- Impresión A4 horizontal del cronograma para entregar en producción o guardar
  como PDF.
- Copia del cronograma como tabla HTML con respaldo en texto, para pegar en
  Outlook, Word o Teams conservando filas y columnas.
- Copia del calendario visible como imagen PNG, ideal para WhatsApp. Cuando el
  navegador bloquea imágenes en el portapapeles, el archivo PNG se descarga
  automáticamente para poder adjuntarlo.
- Página independiente para crear y editar plantillas, sin ventanas modales.
- Opción `Controla remitos` en cada plantilla. Cuando está habilitada, el
  inventario conserva el último remito de ingreso y el último remito de egreso.
  Ambos datos se guardan con el conteo y aparecen en la impresión y en Excel.
- Lista visible de piezas agregadas con contador, orden, datos principales,
  ubicación, confirmación de cada alta y opción para quitar filas.
- Categoría por plantilla: piezas/proceso o materia prima.
- Cada pieza de una plantilla puede incluir o excluir su fila de materia prima.
  La decisión queda congelada en el inventario y también se respeta al
  actualizar el stock posteriormente.
- Las filas `Total en proceso` y por operación sólo se generan cuando la pieza
  tiene al menos una operación definida en `produc21`. La pieza terminada sigue
  apareciendo aunque no tenga proceso.
- El modo cíclico se elige al crear cada inventario, sin necesidad de guardar
  una plantilla distinta para cada pieza.
- El inventario cíclico valida una pieza raíz contra `produc01`, muestra una
  vista previa y recorre `produc10` (`VCOD_` padre, `GCOD_` hijo y `QXUN_` uso)
  por todos sus niveles.
- En cada cíclico se puede elegir proceso global o detalle por operación y
  activar opcionalmente el control de remitos.
- Protección ante referencias circulares, estructuras de más de 20 niveles y
  más de 5000 relaciones.
- Formato de impresión cíclico por nivel, además del detalle por operación y
  el listado simple.
- Maestro de materia prima desde `mtprim01`: código, descripción, diámetro,
  largo, espesor y unidad.
- Stock de materia prima por lote desde `mtprim05`; un material sin stock
  continúa apareciendo con cantidad de sistema cero.
- Formato seleccionable al abrir la vista de impresión:
  `Flujo horizontal por sectores`, `Resumen vertical para inventarios
  grandes`, `Detalle por etapa u operación` y `Listado simple de piezas`.
- En las planillas de piezas la materia prima aparece como un renglón adicional
  sólo cuando ese inventario realmente incluye la etapa `MATERIAL`. El código
  de MP ocupa la columna de código CGR y los lotes se muestran en la descripción.
- El flujo horizontal deja vacías las columnas de sectores, incluida
  `Línea / proceso`, para maximizar el espacio disponible para escritura manual.
- El resumen vertical usa A4 vertical y filas compactas; admite alrededor de
  25 renglones por página según la longitud de los textos.
- La exportación Excel genera dos hojas. `Resumen` conserva la ficha completa
  del inventario, remitos, comentario, indicadores y un detalle operativo
  legible con colores para los renglones dentro y fuera de tolerancia.
- `Detalle histórico` conserva una fila por punto de conteo con los datos de
  cabecera repetidos, IDs internos, origen, fechas, estructura, stock, conteo,
  diferencias, causas y observaciones. Su formato tabular queda preparado para
  filtros, auditoría y consolidación posterior en Power BI.
- El formato no modifica la plantilla ni el inventario: una misma toma puede
  imprimirse de distintas maneras cuando sea necesario.
- Impresión específica de materia prima con dos renglones por código
  (`Cant.` y `Lote`) y seis espacios de conteo.
- Validación de piezas contra `produc01`.
- Datos maestros desde `produc01`: código cliente, material y descripción.
- Stock terminado desde `produc01.STOK_`.
- Stock en proceso desde `produc05`, relacionado con `produc21`.
- Stock de materia prima desde `mtprim05`, sumando todos los lotes del mismo
  `CMAT_`.
- Plantillas con proceso global o conteo operación por operación.
- Creación de inventarios congelando el stock de referencia.
- Carga y guardado de conteos.
- Cálculo de diferencias.
- Página de conciliaciones para comparar un inventario inicial y uno final.
  Por código calcula `inicial + ingresos - egresos`, lo compara con el conteo
  final y muestra diferencia, porcentaje y confiabilidad dentro de ±5%.
- Los ingresos y egresos se cargan manualmente y quedan guardados. Los números
  de último remito de ambos inventarios se muestran como referencia de corte.
- Antes de conciliar, toda cantidad contada cuyo código tenga estructura se
  explota recursivamente con `produc10`. Se consideran todas las filas por
  igual, sin distinguir terminado, proceso u operación, y se agrupan los
  componentes hoja resultantes. La pantalla conserva la trazabilidad
  `cantidad padre × uso acumulado = cantidad equivalente`.
- Cierre del inventario.
- Eliminación de inventarios con confirmación.
- Edición y eliminación de plantillas existentes.
- Impresión A4 horizontal, con varias páginas cuando sea necesario.
- Exportación individual a Excel.
- Documentación automática de la API en `/docs`.

El botón de impresión abre una página independiente, preparada exclusivamente
en A4 horizontal. Usa una fila por pieza y deja espacios amplios para completar
Abastecimiento, Despacho, Línea, Scrap y Stock final. La vista normal conserva
el detalle por etapa u operación.

Las piezas cuyo `MATE_` esté vacío siguen formando parte del inventario y
conservan sus filas de proceso y producto terminado. Solamente se omite para
ellas la fila **Material sin usar**.

Para cada pieza con material, la aplicación consulta `mtprim05`, agrupa por
`LOTE_` y suma `CANT_`. La fila de materia prima congela la suma de todos los
lotes como stock de sistema y conserva los números de lote como referencia.

## 1. Descomprimir y abrir en VS Code

1. Descomprimí el ZIP en una carpeta normal, por ejemplo:

   `C:\Users\aromero\Documents\sistema-inventarios-local`

2. Abrí Visual Studio Code.
3. Elegí **Archivo → Abrir carpeta**.
4. Seleccioná la carpeta `sistema-inventarios-local`.
5. Si VS Code recomienda las extensiones Python y Pylance, instalalas.

## 2. Crear el entorno virtual

Abrí una terminal integrada desde **Terminal → Nueva terminal** y ejecutá:

```powershell
py -m venv .venv
```

Si `py` no existe, probá:

```powershell
python -m venv .venv
```

Activá el entorno:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación, ejecutá una sola vez en esa terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

No requiere permisos de administrador porque `-Scope Process` sólo afecta la
terminal actual.

## 3. Instalar las librerías

Con el entorno virtual activado:

```powershell
python -m pip install -r requirements.txt
```

## 4. Primera prueba sin MySQL

El proyecto trae un archivo `.env` configurado para SQLite. Esto permite probar
todo sin instalar ni configurar nada más.

Ejecutá:

```powershell
python -m uvicorn app.main:app --reload
```

También podés hacer doble clic en `run.bat` después de crear el entorno virtual.

Abrí en el navegador:

- Aplicación: <http://127.0.0.1:8000>
- Documentación API: <http://127.0.0.1:8000/docs>
- Prueba de salud: <http://127.0.0.1:8000/salud>

Al arrancar por primera vez se crea `inventarios_demo.db` y se cargan tres
plantillas y tres inventarios ficticios.

Para borrar todas las pruebas y empezar nuevamente, detené el servidor y
eliminá `inventarios_demo.db`. Se recreará en el próximo arranque.

## 5. Ejecutar desde el depurador de VS Code

El proyecto incluye la configuración necesaria.

1. Presioná `Ctrl + Shift + D`.
2. Elegí **Inventarios: FastAPI**.
3. Presioná `F5`.

Podés colocar puntos de interrupción en cualquier archivo Python.

## 6. Pasar de SQLite a MySQL

### Crear la base

Abrí MySQL Workbench y ejecutá:

```sql
CREATE DATABASE inventarios_web
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
```

No es obligatorio ejecutar manualmente todas las tablas: SQLAlchemy las crea al
arrancar. De todos modos, el modelo SQL completo está en
`sql/schema_mysql.sql` para poder revisarlo o administrarlo desde Workbench.

### Configurar la conexión

Editá `.env`:

```env
DATABASE_URL=mysql+pymysql://inventarios_user:TU_PASSWORD@127.0.0.1:3306/inventarios_web?charset=utf8mb4
PRODUCTION_DATABASE_URL=mysql+pymysql://consulta_user:TU_PASSWORD@127.0.0.1:3306/BASE_PRODUCTIVA?charset=utf8mb4
APP_HOST=127.0.0.1
APP_PORT=8000
```

`DATABASE_URL` guarda las plantillas, inventarios y conteos del sistema nuevo.
`PRODUCTION_DATABASE_URL` debe apuntar a la base donde existen `produc01`,
`produc05` y `produc21`. Pueden usar el mismo servidor o servidores distintos.

Para `PRODUCTION_DATABASE_URL` conviene crear un usuario MySQL con permisos
solamente de lectura:

```sql
GRANT SELECT
ON BASE_PRODUCTIVA.*
TO 'consulta_user'@'localhost';
```

Reemplazá usuarios, contraseñas y bases por los tuyos. No compartas ni subas el
`.env` real a Git.

Reiniciá el servidor. En el primer arranque MySQL recibirá las tablas y los
datos ficticios.

### Usuario MySQL exclusivo recomendado

Ejemplo para ejecutar como administrador de MySQL:

```sql
CREATE USER 'inventarios_user'@'localhost'
IDENTIFIED BY 'UNA_PASSWORD_SEGURA';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX
ON inventarios_web.*
TO 'inventarios_user'@'localhost';

FLUSH PRIVILEGES;
```

## 7. Integración actual con las tablas productivas

El archivo principal es:

`app/services/piece_provider.py`

Consultas implementadas:

- `produc01`: valida `gcod_` y obtiene `ccod_`, `MATE_`, `DESC` y `STOK_`.
- `produc05`: suma `CANT_` por pieza y operación; también conserva los números
  de proveedor disponibles en `NPRV_`.
- `produc21`: obtiene todas las operaciones maestras, incluso si actualmente no
  existe stock en `produc05`. En ese caso muestra stock cero.
- `produc10`: recorre de forma recursiva `VCOD_` → `GCOD_` y multiplica
  `QXUN_` para obtener el uso acumulado en cada nivel.
- `mtprim01`: obtiene descripción, diámetro, largo, espesor y unidad de cada
  materia prima.
- `mtprim05`: suma `CANT_` de todos los lotes asociados al mismo `CMAT_`.

Los valores recuperados se limpian con `TRIM()`. Los filtros por código se
realizan sin funciones para que MySQL pueda aprovechar sus índices.

### Tipos de plantilla

- **Proceso global:** crea una fila con la suma completa de `produc05` y una
  fila de pieza terminada.
- **Por operación:** crea una fila por cada operación de `produc21` y una fila
  de pieza terminada.

En ambos modos se agrega además una fila de materia prima únicamente cuando la
pieza tiene `MATE_`.

El stock queda congelado dentro del inventario en el momento de crearlo.

### Diferencias y confiabilidad

Cada renglón contado muestra la diferencia en cantidad, la relación
`físico / teórico` y el desvío porcentual. La confiabilidad general se calcula
como `renglones dentro de ±5% / total de renglones evaluables`.

- Teórico 0 y físico 0: correcto (100%, desvío 0%).
- Teórico 0 y físico mayor a 0: incorrecto, porcentaje sin base.
- Los stocks pendientes de integrar no forman parte del denominador.
- Mientras queden renglones sin contar, la confiabilidad se muestra como
  parcial y esos renglones todavía cuentan en el total.

### Actualización manual del stock

Dentro de un inventario abierto, **Actualizar stock** vuelve a consultar
`produc01`, `produc05`, `produc21`, `mtprim01` y `mtprim05` según los códigos
incluidos. Conserva y guarda los conteos físicos escritos, actualiza la fecha y
el origen de la foto de stock, y recalcula diferencias y confiabilidad.

Si aparecen operaciones o lotes nuevos, se agregan al inventario como
renglones pendientes de contar. Los inventarios cerrados no se modifican.

La futura importación desde Excel utilizará este mismo mecanismo, cambiando
solamente el origen de los valores.

También se pueden importar los reportes `.xls` o `.xlsx` del sistema:

- PT: `gcod`, `ccod`, `stok`, `nueva_cant`.
- PRD: `piezacod`, `codigocliente`, `operacion`, `proceso`, `cantidad`,
  `retorno`, `proveedor`.
- MP: `lote`, `cmat`, `descr`, `undad`, `cant`.
- Stock asignado (opcional): `ccodmat`, `ncantidad`.

PT se agrupa por código, PRD por código y operación, y MP por código de
material y lote. Las filas ausentes en un reporte se interpretan como stock
cero, pero no se eliminan conteos físicos existentes. El mismo reporte por lote
se utiliza tanto en inventarios de MP como en la etapa MP de inventarios de
piezas.

### Inventarios programados

Una programación guarda la plantilla, la próxima fecha, la frecuencia, el
responsable y las observaciones. No crea el inventario automáticamente en
segundo plano: cuando la fecha vence o llega al día actual se habilita
**Generar inventario**. El botón también queda disponible antes de esa fecha,
porque la planificación es tentativa. Así, el stock productivo se consulta y
congela justo cuando realmente comienza el conteo.

- `Una sola vez`: después de generar queda como completada.
- `Semanal`: avanza al mismo día de la semana siguiente.
- `Mensual`: conserva el día elegido; si un mes no tiene ese día, usa su último
  día y luego recupera el día original en el mes siguiente.

Si una programación quedó atrasada varios períodos, al generar un inventario
avanza hasta la primera fecha futura y evita crear automáticamente conteos
duplicados por las semanas o meses omitidos.

En la vista **Programados**, cada fila tiene una acción principal
**Generar inventario**. Al usarla, el inventario queda vinculado con esa
programación y la ocurrencia correspondiente se muestra como en curso o
realizada. En las programaciones semanales y mensuales también se conserva y
se muestra la próxima fecha; no corresponde al inventario ya cerrado sino al
próximo conteo del ciclo.

Al guardar o cerrar un conteo se actualizan inmediatamente el listado
principal, la vista de programaciones y el calendario.

### Stock de material sin usar

Cuando existe `produc01.MATE_`, se consulta `mtprim05` con
`CMAT_ = MATE_`, se agrupa por `LOTE_` y se suma `CANT_`. Si el material no
tiene registros de stock, la cantidad del sistema es cero. Los números de lote
quedan guardados como referencia en el inventario.

### Probar sin conexión productiva

Si `PRODUCTION_DATABASE_URL` queda vacío, se usa un catálogo ficticio incorporado
con los nueve códigos de ejemplo. Esto permite seguir desarrollando sin tocar
la base real.

## 8. Estructura del proyecto

```text
sistema-inventarios-local/
├── app/
│   ├── main.py                 Entrada de FastAPI
│   ├── config.py               Variables de configuración
│   ├── database.py             Conexión SQLAlchemy
│   ├── models.py               Tablas y relaciones
│   ├── schemas.py              Validaciones de entrada
│   ├── seed.py                 Datos ficticios iniciales
│   ├── serializers.py          Conversión de datos a JSON
│   ├── routers/
│   │   └── api.py              Endpoints del sistema
│   ├── services/
│   │   ├── piece_provider.py   Consultas produc01, produc05 y produc21
│   │   └── excel.py            Exportación a Excel
│   ├── templates/
│   │   └── index.html          Interfaz principal
│   └── static/
│       ├── css/styles.css
│       └── js/app.js
├── sql/schema_mysql.sql
├── docs/modelo_datos_mysql.md  Tablas, relaciones y plan de migración
├── .env
├── .env.example
├── requirements.txt
└── run.bat
```

## Migración desde la versión anterior

Al iniciar, `app/migrations.py` agrega las nuevas columnas sin borrar los
inventarios existentes. También se incluye `sql/migracion_v2.sql` por si
preferís ejecutar y revisar la migración manualmente en MySQL Workbench.

No ejecutes ambas alternativas manualmente: si el sistema ya arrancó y agregó
las columnas, no vuelvas a ejecutar el SQL.

La descripción completa de las tablas, sus relaciones, los indicadores posibles
y el procedimiento recomendado para separar la base de gestión de la base
productiva está en `docs/modelo_datos_mysql.md`.

## Próximas validaciones recomendadas

Al probar con datos productivos conviene confirmar:

1. Si todos los hijos de `produc10` existen en `produc01` o `mtprim01`.
2. Si un material declarado tanto en `produc10` como en `produc01.MATE_` debe
   tomar siempre el uso explícito de `produc10` (comportamiento actual).
3. Si `NPRV_` debe mostrarse solamente como dato o contarse por proveedor.
4. Si hay operaciones de `produc21` que deban excluirse.
# Versión 0.82.1

Corrige la compatibilidad del esquema de migración con instalaciones antiguas de
MySQL/InnoDB cuyo límite por columna indexada es de 767 bytes. Las claves
`movimiento_clave` de ingresos y egresos usan `latin1_bin`, conservando sus 255
caracteres y la comparación exacta, mientras el resto del esquema continúa en
`utf8mb4`.
