USE inventarios_web;

ALTER TABLE inventario_items
    ADD COLUMN stock_asignado DOUBLE NOT NULL DEFAULT 0
    AFTER stock_sistema;
