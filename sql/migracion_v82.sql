-- v0.82.0 - almacenes auxiliares locales migrados a MySQL.
-- Idempotente: puede ejecutarse nuevamente sin borrar ni duplicar datos.

CREATE TABLE IF NOT EXISTS inventario_cierres (
    inventario_id BIGINT NOT NULL PRIMARY KEY,
    mes_cierre DATE NOT NULL,
    KEY ix_inventario_cierres_mes (mes_cierre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS programacion_cierres (
    programacion_id BIGINT NOT NULL PRIMARY KEY,
    mes_cierre_proximo DATE NOT NULL,
    KEY ix_programacion_cierres_mes (mes_cierre_proximo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inventario_programaciones (
    inventario_id BIGINT NOT NULL PRIMARY KEY,
    programacion_id BIGINT NOT NULL,
    KEY ix_inventario_programaciones_programacion (programacion_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conteo_cajas (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    cliente_uid VARCHAR(191) NOT NULL UNIQUE,
    inventario_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    cantidad DOUBLE NOT NULL,
    observacion VARCHAR(2000) NOT NULL DEFAULT '',
    dispositivo VARCHAR(255) NOT NULL DEFAULT '',
    capturado_en VARCHAR(40) NOT NULL,
    creado_en VARCHAR(40) NOT NULL,
    KEY ix_conteo_cajas_inventario (inventario_id),
    KEY ix_conteo_cajas_item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conteo_bases (
    inventario_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    conteo_base DOUBLE NOT NULL DEFAULT 0,
    PRIMARY KEY (inventario_id, item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conteo_revisiones (
    inventario_id BIGINT NOT NULL PRIMARY KEY,
    revision VARCHAR(40) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conciliacion_remitos (
    conciliacion_id BIGINT NOT NULL PRIMARY KEY,
    remitos_ingreso_json LONGTEXT NOT NULL,
    remitos_egreso_json LONGTEXT NOT NULL,
    advertencias_json LONGTEXT NOT NULL,
    criterio_ingreso VARCHAR(30) NOT NULL DEFAULT 'REMITOS',
    criterio_egreso VARCHAR(30) NOT NULL DEFAULT 'REMITOS',
    calculados_en VARCHAR(40) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conciliacion_remito_items (
    conciliacion_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    codigo VARCHAR(100) NOT NULL,
    ingresos_calculados DOUBLE NOT NULL DEFAULT 0,
    egresos_calculados DOUBLE NOT NULL DEFAULT 0,
    scrap DOUBLE NOT NULL DEFAULT 0,
    detalle_ingresos_json LONGTEXT NOT NULL,
    detalle_egresos_json LONGTEXT NOT NULL,
    PRIMARY KEY (conciliacion_id, item_id),
    KEY ix_conciliacion_remito_items_codigo (conciliacion_id, codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conciliacion_ingresos_control (
    conciliacion_id BIGINT NOT NULL,
    movimiento_clave VARCHAR(255)
        CHARACTER SET latin1
        COLLATE latin1_bin
        NOT NULL,
    item_id BIGINT NOT NULL,
    codigo VARCHAR(100) NOT NULL,
    codigo_material VARCHAR(100) NOT NULL DEFAULT '',
    remito VARCHAR(100) NOT NULL DEFAULT '',
    fecha VARCHAR(20) NOT NULL DEFAULT '',
    cantidad_original DOUBLE NOT NULL DEFAULT 0,
    cantidad_editada DOUBLE NULL,
    verificado TINYINT(1) NOT NULL DEFAULT 0,
    observacion VARCHAR(2000) NOT NULL DEFAULT '',
    manual TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (conciliacion_id, movimiento_clave),
    KEY ix_conciliacion_ingresos_codigo (conciliacion_id, codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conciliacion_egresos_control (
    conciliacion_id BIGINT NOT NULL,
    movimiento_clave VARCHAR(255)
        CHARACTER SET latin1
        COLLATE latin1_bin
        NOT NULL,
    remito VARCHAR(100) NOT NULL DEFAULT '',
    remito_numero BIGINT NOT NULL DEFAULT 0,
    fecha VARCHAR(20) NOT NULL DEFAULT '',
    codigo_pieza VARCHAR(100) NOT NULL DEFAULT '',
    cantidad_original DOUBLE NOT NULL DEFAULT 0,
    cantidad_editada DOUBLE NULL,
    verificado TINYINT(1) NOT NULL DEFAULT 0,
    observacion VARCHAR(2000) NOT NULL DEFAULT '',
    manual TINYINT(1) NOT NULL DEFAULT 0,
    componentes_json LONGTEXT NOT NULL,
    PRIMARY KEY (conciliacion_id, movimiento_clave),
    KEY ix_conciliacion_egresos_remito (conciliacion_id, remito)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conciliacion_items_excluidos (
    conciliacion_id BIGINT NOT NULL,
    codigo VARCHAR(100) NOT NULL,
    excluido_en VARCHAR(40) NOT NULL,
    PRIMARY KEY (conciliacion_id, codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inventarios_relaciones (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    inventario_origen_id BIGINT NOT NULL,
    inventario_reconteo_id BIGINT NOT NULL UNIQUE,
    numero_reconteo INT NOT NULL,
    tipo ENUM('COMPLETO', 'PARCIAL') NOT NULL,
    stock_referencia ENUM('ORIGINAL', 'ACTUALIZADO') NOT NULL,
    creado_en VARCHAR(40) NOT NULL,
    UNIQUE KEY uq_relacion_numero (inventario_origen_id, numero_reconteo),
    KEY ix_relaciones_origen (inventario_origen_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
