-- Seguimiento de diferencias ajustadas en el sistema.
ALTER TABLE inventario_items
    ADD COLUMN ajustado_sistema BOOLEAN
        NOT NULL DEFAULT FALSE;

ALTER TABLE inventario_items
    ADD COLUMN ajustado_sistema_en DATETIME NULL;

CREATE INDEX ix_inventario_items_ajustado_sistema
    ON inventario_items (ajustado_sistema);
