-- Versión 0.52: reglas configurables de indicadores.

CREATE TABLE IF NOT EXISTS configuracion_sistema (
    clave VARCHAR(80) PRIMARY KEY,
    valor VARCHAR(255) NOT NULL,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    actualizada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO configuracion_sistema
    (clave, valor, descripcion)
VALUES
    (
        'tolerancia_pct',
        '5.0',
        'Desvío porcentual máximo para considerar correcto un renglón.'
    ),
    (
        'objetivo_confiabilidad_pct',
        '90.0',
        'Meta general de confiabilidad utilizada en reportes.'
    ),
    (
        'alerta_cliente_pct',
        '85.0',
        'Confiabilidad por debajo de la cual se genera una alerta.'
    ),
    (
        'minimo_renglones_alerta',
        '3',
        'Muestra mínima por cliente para emitir una alerta.'
    )
ON DUPLICATE KEY UPDATE clave = VALUES(clave);
