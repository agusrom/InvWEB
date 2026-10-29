-- Sistema de Inventarios v1.30
-- Migración completa de almacenes auxiliares y análisis unificado a MySQL.
--
-- IMPORTANTE:
-- Las tablas principales de esta instalación fueron importadas desde SQLite y
-- sus identificadores se almacenan como BIGINT. Todas las columnas relacionadas
-- se declaran también BIGINT para que MySQL pueda crear las claves foráneas.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS inventario_cierres (
    inventario_id BIGINT NOT NULL,
    mes_cierre DATE NOT NULL,
    PRIMARY KEY (inventario_id),
    INDEX ix_inventario_cierres_mes (mes_cierre),
    CONSTRAINT fk_inventario_cierres_inventario
        FOREIGN KEY (inventario_id) REFERENCES inventarios(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS programacion_cierres (
    programacion_id BIGINT NOT NULL,
    mes_cierre_proximo DATE NOT NULL,
    PRIMARY KEY (programacion_id),
    INDEX ix_programacion_cierres_mes (mes_cierre_proximo),
    CONSTRAINT fk_programacion_cierres_programacion
        FOREIGN KEY (programacion_id) REFERENCES programaciones_inventario(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS inventario_programaciones (
    inventario_id BIGINT NOT NULL,
    programacion_id BIGINT NOT NULL,
    PRIMARY KEY (inventario_id),
    INDEX ix_inventario_programaciones_programacion (programacion_id),
    CONSTRAINT fk_inventario_programaciones_inventario
        FOREIGN KEY (inventario_id) REFERENCES inventarios(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_inventario_programaciones_programacion
        FOREIGN KEY (programacion_id) REFERENCES programaciones_inventario(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conteo_bases (
    inventario_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    conteo_base DOUBLE NOT NULL DEFAULT 0,
    PRIMARY KEY (inventario_id, item_id),
    CONSTRAINT fk_conteo_bases_inventario
        FOREIGN KEY (inventario_id) REFERENCES inventarios(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_conteo_bases_item
        FOREIGN KEY (item_id) REFERENCES inventario_items(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conteo_cajas (
    id BIGINT NOT NULL AUTO_INCREMENT,
    cliente_uid VARCHAR(255) NOT NULL,
    inventario_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    cantidad DOUBLE NOT NULL,
    observacion TEXT NOT NULL,
    dispositivo VARCHAR(255) NOT NULL DEFAULT '',
    capturado_en DATETIME(6) NOT NULL,
    creado_en DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_conteo_cajas_cliente_uid (cliente_uid),
    INDEX ix_conteo_cajas_inventario (inventario_id),
    INDEX ix_conteo_cajas_item (item_id),
    CONSTRAINT fk_conteo_cajas_inventario
        FOREIGN KEY (inventario_id) REFERENCES inventarios(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_conteo_cajas_item
        FOREIGN KEY (item_id) REFERENCES inventario_items(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conteo_revisiones (
    inventario_id BIGINT NOT NULL,
    revision VARCHAR(40) NOT NULL,
    PRIMARY KEY (inventario_id),
    CONSTRAINT fk_conteo_revisiones_inventario
        FOREIGN KEY (inventario_id) REFERENCES inventarios(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conciliacion_remitos (
    conciliacion_id BIGINT NOT NULL,
    remitos_ingreso_json LONGTEXT NOT NULL,
    remitos_egreso_json LONGTEXT NOT NULL,
    advertencias_json LONGTEXT NOT NULL,
    criterio_ingreso VARCHAR(30) NOT NULL DEFAULT 'REMITOS',
    criterio_egreso VARCHAR(30) NOT NULL DEFAULT 'REMITOS',
    calculados_en DATETIME(6) NOT NULL,
    PRIMARY KEY (conciliacion_id),
    CONSTRAINT fk_conciliacion_remitos_conciliacion
        FOREIGN KEY (conciliacion_id) REFERENCES conciliaciones(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conciliacion_remito_items (
    conciliacion_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    codigo VARCHAR(80) NOT NULL,
    ingresos_calculados DOUBLE NOT NULL DEFAULT 0,
    egresos_calculados DOUBLE NOT NULL DEFAULT 0,
    detalle_ingresos_json LONGTEXT NOT NULL,
    detalle_egresos_json LONGTEXT NOT NULL,
    scrap DOUBLE NOT NULL DEFAULT 0,
    PRIMARY KEY (conciliacion_id, item_id),
    INDEX ix_conciliacion_remito_items_codigo (conciliacion_id, codigo),
    CONSTRAINT fk_conciliacion_remito_items_cabecera
        FOREIGN KEY (conciliacion_id)
        REFERENCES conciliacion_remitos(conciliacion_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_conciliacion_remito_items_item
        FOREIGN KEY (item_id) REFERENCES conciliacion_items(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conciliacion_ingresos_control (
    conciliacion_id BIGINT NOT NULL,
    movimiento_clave VARCHAR(255)
        CHARACTER SET latin1 COLLATE latin1_bin NOT NULL,
    item_id BIGINT NOT NULL,
    codigo VARCHAR(80) NOT NULL,
    codigo_material VARCHAR(80) NOT NULL DEFAULT '',
    remito VARCHAR(80) NOT NULL DEFAULT '',
    fecha DATE NULL,
    cantidad_original DOUBLE NOT NULL DEFAULT 0,
    cantidad_editada DOUBLE NULL,
    verificado BOOLEAN NOT NULL DEFAULT 0,
    observacion TEXT NOT NULL,
    manual BOOLEAN NOT NULL DEFAULT 0,
    PRIMARY KEY (conciliacion_id, movimiento_clave),
    INDEX ix_conciliacion_ingresos_codigo (conciliacion_id, codigo),
    CONSTRAINT fk_conciliacion_ingresos_cabecera
        FOREIGN KEY (conciliacion_id)
        REFERENCES conciliacion_remitos(conciliacion_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_conciliacion_ingresos_item
        FOREIGN KEY (item_id) REFERENCES conciliacion_items(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conciliacion_egresos_control (
    conciliacion_id BIGINT NOT NULL,
    movimiento_clave VARCHAR(255)
        CHARACTER SET latin1 COLLATE latin1_bin NOT NULL,
    remito VARCHAR(80) NOT NULL DEFAULT '',
    remito_numero BIGINT NOT NULL DEFAULT 0,
    fecha DATE NULL,
    codigo_pieza VARCHAR(80) NOT NULL DEFAULT '',
    cantidad_original DOUBLE NOT NULL DEFAULT 0,
    cantidad_editada DOUBLE NULL,
    verificado BOOLEAN NOT NULL DEFAULT 0,
    observacion TEXT NOT NULL,
    manual BOOLEAN NOT NULL DEFAULT 0,
    componentes_json LONGTEXT NOT NULL,
    PRIMARY KEY (conciliacion_id, movimiento_clave),
    INDEX ix_conciliacion_egresos_remito (conciliacion_id, remito),
    CONSTRAINT fk_conciliacion_egresos_cabecera
        FOREIGN KEY (conciliacion_id)
        REFERENCES conciliacion_remitos(conciliacion_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conciliacion_items_excluidos (
    conciliacion_id BIGINT NOT NULL,
    codigo VARCHAR(80) NOT NULL,
    excluido_en DATETIME(6) NOT NULL,
    PRIMARY KEY (conciliacion_id, codigo),
    CONSTRAINT fk_conciliacion_excluidos_conciliacion
        FOREIGN KEY (conciliacion_id) REFERENCES conciliaciones(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS inventarios_relaciones (
    id BIGINT NOT NULL AUTO_INCREMENT,
    inventario_origen_id BIGINT NOT NULL,
    inventario_reconteo_id BIGINT NOT NULL,
    numero_reconteo INT NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    stock_referencia VARCHAR(20) NOT NULL,
    creado_en DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_inventarios_relaciones_reconteo (inventario_reconteo_id),
    UNIQUE KEY uq_inventarios_relaciones_numero
        (inventario_origen_id, numero_reconteo),
    INDEX ix_relaciones_origen (inventario_origen_id),
    CONSTRAINT fk_relaciones_inventario_origen
        FOREIGN KEY (inventario_origen_id) REFERENCES inventarios(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_relaciones_inventario_reconteo
        FOREIGN KEY (inventario_reconteo_id) REFERENCES inventarios(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS analisis_stock (
    id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    inventario_final_id BIGINT NOT NULL,
    firma_iniciales CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    iniciales_json TEXT NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    origen VARCHAR(30) NOT NULL DEFAULT 'NUEVO',
    conciliacion_legacy_id BIGINT NULL,
    creado_en DATETIME(6) NOT NULL,
    actualizado_en DATETIME(6) NOT NULL,
    calculo_json LONGTEXT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_analisis_stock_escenario
        (inventario_final_id, firma_iniciales),
    UNIQUE KEY uq_analisis_stock_legacy (conciliacion_legacy_id),
    INDEX ix_analisis_stock_final (inventario_final_id),
    INDEX ix_analisis_stock_actualizado (actualizado_en),
    CONSTRAINT fk_analisis_stock_final
        FOREIGN KEY (inventario_final_id) REFERENCES inventarios(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_analisis_stock_legacy
        FOREIGN KEY (conciliacion_legacy_id) REFERENCES conciliaciones(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS analisis_stock_iniciales (
    analisis_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    inventario_inicial_id BIGINT NOT NULL,
    orden INT NOT NULL DEFAULT 0,
    PRIMARY KEY (analisis_id, inventario_inicial_id),
    INDEX ix_analisis_inicial_inventario (inventario_inicial_id),
    CONSTRAINT fk_analisis_iniciales_analisis
        FOREIGN KEY (analisis_id) REFERENCES analisis_stock(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_analisis_iniciales_inventario
        FOREIGN KEY (inventario_inicial_id) REFERENCES inventarios(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS analisis_stock_auditoria (
    inventario_final_id BIGINT NOT NULL,
    datos_json LONGTEXT NOT NULL,
    actualizado_en DATETIME(6) NOT NULL,
    PRIMARY KEY (inventario_final_id),
    CONSTRAINT fk_analisis_auditoria_inventario
        FOREIGN KEY (inventario_final_id) REFERENCES inventarios(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS analisis_stock_notas (
    inventario_final_id BIGINT NOT NULL,
    codigo VARCHAR(80) NOT NULL,
    causa_codigo VARCHAR(50) NULL,
    observacion TEXT NOT NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE',
    controles_json TEXT NOT NULL,
    actualizado_en DATETIME(6) NOT NULL,
    PRIMARY KEY (inventario_final_id, codigo),
    INDEX ix_analisis_notas_estado (estado),
    CONSTRAINT fk_analisis_notas_inventario
        FOREIGN KEY (inventario_final_id) REFERENCES inventarios(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Respaldo MySQL del reconteo experimental de v0.81.0. Estas tablas no son
-- usadas por la interfaz actual, pero evitan dejar registros únicamente en
-- reconteos.db.
CREATE TABLE IF NOT EXISTS inventario_reconteos_legacy (
    id BIGINT NOT NULL,
    inventario_id BIGINT NOT NULL,
    numero INT NOT NULL,
    tipo VARCHAR(20) NOT NULL DEFAULT 'PARCIAL',
    stock_referencia VARCHAR(20) NOT NULL DEFAULT 'ORIGINAL',
    estado VARCHAR(20) NOT NULL DEFAULT 'ABIERTO',
    responsable VARCHAR(120) NOT NULL DEFAULT '',
    observaciones TEXT NOT NULL,
    creado_en DATETIME(6) NOT NULL,
    stock_capturado_en DATETIME(6) NULL,
    cerrado_en DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_reconteos_legacy_numero (inventario_id, numero),
    CONSTRAINT fk_reconteos_legacy_inventario
        FOREIGN KEY (inventario_id) REFERENCES inventarios(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS inventario_reconteo_items_legacy (
    id BIGINT NOT NULL,
    reconteo_id BIGINT NOT NULL,
    inventario_item_id BIGINT NOT NULL,
    stock_sistema DOUBLE NOT NULL DEFAULT 0,
    conteo_fisico DOUBLE NULL,
    causa_diferencia_codigo VARCHAR(50) NULL,
    ajustado_sistema BOOLEAN NOT NULL DEFAULT 0,
    observaciones TEXT NOT NULL,
    guardado_en DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_reconteo_items_legacy
        (reconteo_id, inventario_item_id),
    CONSTRAINT fk_reconteo_items_legacy_reconteo
        FOREIGN KEY (reconteo_id) REFERENCES inventario_reconteos_legacy(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_reconteo_items_legacy_item
        FOREIGN KEY (inventario_item_id) REFERENCES inventario_items(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
