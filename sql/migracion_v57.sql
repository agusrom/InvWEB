USE inventarios_web;

ALTER TABLE formato_versiones
    ADD COLUMN nombre VARCHAR(120) NULL AFTER numero;

UPDATE formato_versiones
SET nombre = CASE
    WHEN numero = 1 THEN 'Predeterminada'
    ELSE CONCAT('Versión ', numero)
END
WHERE nombre IS NULL OR TRIM(nombre) = '';

ALTER TABLE formato_versiones
    MODIFY COLUMN nombre VARCHAR(120) NOT NULL;
