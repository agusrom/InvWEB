-- Sistema de Inventarios v0.79
-- Guarda la trazabilidad de los movimientos calculados por remito.

ALTER TABLE `conciliaciones`
    ADD COLUMN `remitos_ingreso_json` TEXT NULL,
    ADD COLUMN `remitos_egreso_json` TEXT NULL,
    ADD COLUMN `advertencias_movimientos_json` TEXT NULL,
    ADD COLUMN `movimientos_calculados_en` DATETIME NULL;

ALTER TABLE `conciliacion_items`
    ADD COLUMN `ingresos_calculados` DOUBLE NOT NULL DEFAULT 0,
    ADD COLUMN `egresos_calculados` DOUBLE NOT NULL DEFAULT 0,
    ADD COLUMN `detalle_ingresos_json` TEXT NULL,
    ADD COLUMN `detalle_egresos_json` TEXT NULL;
