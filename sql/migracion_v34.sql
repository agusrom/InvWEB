-- Migración puntual desde la versión 0.33.
-- No es necesaria si la aplicación ya arrancó: app/migrations.py la aplica.

USE inventarios_web;

ALTER TABLE plantilla_items
    ADD COLUMN contar_material BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE inventario_items
    ADD COLUMN contar_material BOOLEAN NOT NULL DEFAULT TRUE;
