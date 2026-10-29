-- Estado y fecha de actualización de plantillas.
ALTER TABLE plantillas
    ADD COLUMN actualizada_en DATETIME NULL;

UPDATE plantillas
SET actualizada_en = creada_en
WHERE actualizada_en IS NULL;

ALTER TABLE plantillas
    MODIFY COLUMN actualizada_en DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP;
