-- Clasificación estructural histórica de piezas.
ALTER TABLE plantilla_items
    ADD COLUMN tipo_estructura VARCHAR(20)
        NOT NULL DEFAULT 'INDEPENDIENTE';

ALTER TABLE inventario_items
    ADD COLUMN tipo_estructura VARCHAR(20)
        NOT NULL DEFAULT 'INDEPENDIENTE';

CREATE INDEX ix_inventario_items_tipo_estructura
    ON inventario_items (tipo_estructura);
