-- Migración puntual desde la versión 0.35.
-- No es necesaria si la aplicación ya arrancó: app/migrations.py la aplica.

USE inventarios_web;

ALTER TABLE causas_diferencia
    ADD COLUMN categoria VARCHAR(30) NOT NULL DEFAULT 'OTRA';

UPDATE causas_diferencia SET categoria = 'CONTEO'
WHERE codigo IN ('ERROR_CONTEO', 'UNIDAD_MEDICION');

UPDATE causas_diferencia SET categoria = 'DOCUMENTACION'
WHERE codigo IN ('MOVIMIENTO_NO_REGISTRADO', 'REMITO_PENDIENTE');

UPDATE causas_diferencia SET categoria = 'PRODUCCION'
WHERE codigo IN ('PRODUCCION_NO_REGISTRADA', 'SCRAP_NO_INFORMADO');

UPDATE causas_diferencia SET categoria = 'UBICACION'
WHERE codigo = 'UBICACION_INCORRECTA';

UPDATE causas_diferencia SET categoria = 'SISTEMA'
WHERE codigo = 'ERROR_STOCK_SISTEMA';
