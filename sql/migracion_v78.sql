USE inventarios_web;

ALTER TABLE inventarios
    ADD COLUMN mes_cierre DATE NULL AFTER fecha_programada,
    ADD INDEX ix_inventarios_mes_cierre (mes_cierre);

ALTER TABLE programaciones_inventario
    ADD COLUMN mes_cierre_proximo DATE NULL AFTER dia_mes,
    ADD INDEX ix_programaciones_mes_cierre (mes_cierre_proximo);

UPDATE inventarios i
LEFT JOIN programaciones_inventario p ON p.id = i.programacion_id
SET i.mes_cierre = STR_TO_DATE(
    CONCAT(
        DATE_FORMAT(
            CASE
                WHEN p.frecuencia = 'MENSUAL'
                    THEN COALESCE(i.fecha_programada, i.fecha)
                ELSE COALESCE(DATE(i.cerrado_en), i.fecha)
            END,
            '%Y-%m'
        ),
        '-01'
    ),
    '%Y-%m-%d'
)
WHERE i.mes_cierre IS NULL;

UPDATE programaciones_inventario
SET mes_cierre_proximo = STR_TO_DATE(
    CONCAT(DATE_FORMAT(fecha_proxima, '%Y-%m'), '-01'),
    '%Y-%m-%d'
)
WHERE mes_cierre_proximo IS NULL;

-- Revisá las programaciones mensuales existentes cuya próxima fecha cae en
-- los primeros días del mes siguiente. El sistema ya no puede inferir si,
-- por ejemplo, 02/08 corresponde al cierre de julio; se corrige desde la UI.
