-- Inventarios de medios: desglose físico y modalidad persistente.
ALTER TABLE inventarios
    ADD COLUMN modalidad_conteo VARCHAR(20)
        NOT NULL DEFAULT 'ESTANDAR';

CREATE INDEX ix_inventarios_modalidad
    ON inventarios (modalidad_conteo);

ALTER TABLE inventario_items
    ADD COLUMN conteo_vacios DOUBLE NULL,
    ADD COLUMN conteo_llenos DOUBLE NULL,
    ADD COLUMN conteo_rotos DOUBLE NULL;
