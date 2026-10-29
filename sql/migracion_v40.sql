-- Versión 0.40: registra si el inventario nació de plantilla, cíclico o manual.
-- Los inventarios históricos se consideran originados desde plantilla.

ALTER TABLE inventarios
    ADD COLUMN origen VARCHAR(20) NOT NULL DEFAULT 'PLANTILLA'
    AFTER codigo;

CREATE INDEX ix_inventarios_origen ON inventarios (origen);
