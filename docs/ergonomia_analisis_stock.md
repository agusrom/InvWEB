# Ergonomía del análisis de stock

## Flujo revisado

Se revisaron el historial, la elección de inventarios, el resumen, el detalle por
pieza, la auditoría de remitos, la carga manual, la actualización del inventario
final y la exportación. Se conserva la separación entre control directo contra
sistema y conciliación del conteo explotado.

El resumen sirve para encontrar diferencias; el detalle explica su cálculo; el
registro de remitos permite verificar y corregir la documentación. Conviene
mantener estas tres vistas y mejorar su conexión progresivamente.

## Primera mejora implementada: remitos manuales

- Una cabecera con tipo, fecha, número y observación común.
- Renglones numerados con buscador de código/descripción, cantidad y acción Quitar.
- Agregar renglones conserva lo escrito y enfoca el nuevo código. La fecha y el
  tipo se conservan después del guardado para agilizar la carga siguiente.
- En ingresos se buscan materiales y piezas; en egresos se buscan piezas,
  incluidas las terminadas que no aparecen directamente como fila del análisis.
- Un egreso conserva el código de origen y su cantidad. El cálculo recorre su
  estructura recursiva y aplica los usos acumulados solamente a los componentes
  del análisis. Los componentes ajenos no crean filas nuevas.
- Todo el remito se valida y persiste en una transacción. No se admiten códigos
  repetidos en el mismo envío: su cantidad debe unificarse en un renglón.
- Un identificador de envío evita duplicar el remito al reintentar tras un fallo
  de red. Si falla el guardado, se conserva el formulario; si se guarda pero falla
  el recálculo, se avisa que hay que recalcular y se limpia la carga ya guardada.
- Se bloquea cambiar el inventario durante el envío. La disposición pasa de
  renglones horizontales a tarjetas verticales en pantallas chicas.

La persistencia usa el JSON de auditoría SQLite existente. No requiere nuevas
tablas ni permisos DDL. Los endpoints y movimientos individuales anteriores
siguen disponibles, al igual que su edición, verificación y eliminación.

## Próximas mejoras recomendadas

| Prioridad | Hallazgo | Mejora propuesta |
| --- | --- | --- |
| Alta | Después de recalcular, el resultado en pantalla y la fotografía del análisis guardado pueden representar momentos diferentes. | Mostrar estado «Cambios sin guardar» y fecha/hora del último cálculo y del último guardado junto a sus acciones. Distinguir actualizar conteos de guardar la fotografía. |
| Alta | El impacto de una pieza terminada se explica en el detalle, después de cargar el remito. | Previsualizar antes de guardar: pieza de origen, componentes alcanzados, uso acumulado y cantidad equivalente. Advertir si un renglón no afecta ningún componente o período seleccionado. |
| Alta | El registro agrupa por tipo y número de remito y puede contener varias fechas; una búsqueda encuentra un remito y muestra también sus otros renglones. | Hacer explícito que el filtro encuentra documentos completos. Definir la identidad documental con número, fecha y, si corresponde al negocio, proveedor/serie antes de separar documentos con números reutilizados. |
| Alta | El registro muestra un «Total» sumando cantidades de distintos códigos, que pueden tener unidades diferentes. | Mostrar totales por unidad o limitar el resumen a cantidad de renglones y verificados hasta disponer de unidades homogéneas. |
| Media | Las advertencias por escenario y código pueden formar una lista extensa antes de los remitos. | Resumirlas por causa y período en un panel desplegable, con acceso a las piezas afectadas y contador de pendientes. |
| Media | En algunos controles y detalles hay textos de 9–10 px y muchas acciones simultáneas. | Unificar tamaños de texto y botones; priorizar esperado, conteo y diferencia, y dejar historial, ajustes y trazabilidad bajo despliegue. Aplicarlo por sección para conservar densidad útil. |
| Media | El detalle de piezas y el registro de remitos se recorren por separado. | Agregar enlaces en ambos sentidos: del movimiento al componente afectado y del componente al documento, conservando búsqueda, período y posición. |
| Media | El historial y varios registros se renderizan completos en el navegador. | Agregar paginación o carga progresiva y conservar filtros al volver del detalle. Medir con inventarios y remitos de tamaño real antes de elegir límites. |
| Técnica | El JavaScript reúne navegación, formularios, cálculo visible, auditoría y exportación; el CSS acumula reglas sucesivas para las mismas secciones. | Separar por responsabilidades y consolidar estilos en cambios pequeños, manteniendo pruebas del flujo completo y las tres vistas. |

Estas recomendaciones quedan pendientes; no se cambian en esta entrega los
criterios de corte por remitos/fechas, tolerancias, unidades ni fórmulas existentes.

## Verificación

Pruebas aisladas con SQLite temporal: remito con varias MP, egresos con piezas
terminadas y estructuras de varios niveles, exclusión de componentes ajenos,
límites de fecha y cantidad, rechazo completo de renglones inválidos, reintentos
sin duplicación y fallo de persistencia. La verificación de navegador cubre
búsqueda en distintas filas, agregar/quitar, rechazo de códigos repetidos,
doble envío, conservación ante errores y distribución a 390 px de ancho.
