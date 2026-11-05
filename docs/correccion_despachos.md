# Corrección de lectura de despachos en análisis de stock

Se corrigen filtros que podían dejar fuera egresos automáticos:

- Además de los códigos de los inventarios y sus descendientes, se buscan en
  `produc10` las piezas terminadas y subconjuntos que consumen los componentes del
  análisis, aunque esos padres no estén incluidos directamente en el inventario.
- Los despachos encontrados se explotan y solo aportan a los componentes ya
  analizados. No se crean filas para componentes ajenos ni se duplica el documento
  si el padre ya estaba incluido.
- Cuando el corte es una fecha sin hora, se excluye todo el día inicial y se
  incluye todo el día final. Los cortes de remitos con timestamp mantienen sus
  límites exactos. Se aplica la misma política a ingresos y egresos.
- El estado D se normaliza de la misma forma al buscar los remitos de corte y al
  leer los movimientos. LACTIVO_ permanece informativo y no excluye despachos.

Los análisis guardados conservan su fotografía; abrirlos no consulta de nuevo
los despachos. Después de actualizar la aplicación hay que pulsar **Actualizar
inventario final**. Se muestra un aviso en las fotografías anteriores a la
revisión 2 del cálculo de movimientos. Se conservan ID, nombre, notas y controles.

El diagnóstico de cada acumulado informa fuente configurada, cantidad de códigos
consultados, despachos encontrados y despachos aplicados. Si no se configuró la
conexión productiva, se avisa explícitamente en vez de presentar el cero sin
contexto. Los tramos derivados siguen usando la misma auditoría de los acumulados.

La corrección solo cambia consultas de lectura; no modifica tablas ni saldos en
MySQL. Las pruebas usan tablas temporales con el SQL del servicio y cubren piezas
directas, padres ausentes del inventario, varios niveles, estados y espacios en
códigos, límites por día/timestamp, ciclos y auditoría de inventarios abiertos y
cerrados. No se verificó contra la base productiva del usuario, cuya conexión no
está disponible en este entorno.
