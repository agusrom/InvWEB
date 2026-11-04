-- SISTEMA DE INVENTARIOS v1.16 - ETAPA 1. Ejecutar SOLO por el administrador.
-- Seleccionar primero la base DE GESTION (la de DATABASE_URL).
-- No ejecutar sobre la base productiva ni con el servidor de inventarios activo.
-- Requiere respaldo restaurable. Los DDL hacen commit implicito: no hay rollback.
-- Por defecto SOLO muestra el plan; no borra tablas ni actualiza registros.
-- Para aplicar: cambiar aplicar a 1, escribir el nombre EXACTO de la base y
-- establecer respaldo_verificado=1 despues de comprobar el respaldo.
-- No crea indices ni tablas persistentes. Usa un procedimiento transitorio y
-- tablas TEMPORARY sin indices. No desactiva FOREIGN_KEY_CHECKS.
-- Ejecutar como script completo (Workbench/mysql; respetar DELIMITER).

SET @invweb_e1_aplicar = 0;
SET @invweb_e1_base_confirmada = 'REEMPLAZAR_POR_BASE_DE_GESTION';
SET @invweb_e1_respaldo_verificado = 0;

DROP PROCEDURE IF EXISTS invweb_migracion_etapa1_retirar_pruebas;
DELIMITER $$
CREATE PROCEDURE invweb_migracion_etapa1_retirar_pruebas()
SQL SECURITY INVOKER
BEGIN
    DECLARE v_db VARCHAR(64);
    DECLARE v_count BIGINT DEFAULT 0;
    DECLARE v_done INT DEFAULT 0;
    DECLARE v_order INT DEFAULT 0;
    DECLARE v_apply_index INT DEFAULT 1;
    DECLARE v_name VARCHAR(64);
    DECLARE v_command TEXT;
    DECLARE v_keys CURSOR FOR
        SELECT DISTINCT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'analisis_stock'
          AND COLUMN_NAME = 'conciliacion_legacy_id'
          AND REFERENCED_TABLE_SCHEMA = DATABASE()
          AND REFERENCED_TABLE_NAME = 'conciliaciones'
        ORDER BY CONSTRAINT_NAME;
    DECLARE v_legacy CURSOR FOR
        SELECT TABLE_NAME FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
          AND TABLE_NAME IN ('conciliacion_remito_items','conciliacion_ingresos_control',
              'conciliacion_egresos_control','conciliacion_items_excluidos',
              'conciliacion_remitos','conciliacion_items','conciliaciones')
        ORDER BY FIELD(TABLE_NAME,'conciliacion_remito_items','conciliacion_ingresos_control',
              'conciliacion_egresos_control','conciliacion_items_excluidos',
              'conciliacion_remitos','conciliacion_items','conciliaciones');
    DECLARE v_protected CURSOR FOR
        SELECT TABLE_NAME FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
          AND TABLE_NAME IN ('inventarios','inventario_items','plantillas','plantilla_items',
              'programaciones_inventario','conteo_cajas','conteo_bases','conteo_revisiones',
              'inventarios_relaciones','inventario_cierres','programacion_cierres','inventario_programaciones')
        ORDER BY TABLE_NAME;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        DROP TEMPORARY TABLE IF EXISTS invweb_e1_plan;
        DROP TEMPORARY TABLE IF EXISTS invweb_e1_conteos;
        RESIGNAL;
    END;

    SET v_db = DATABASE();
    IF v_db IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Seleccionar primero la base de gestion.';
    END IF;
    IF @@FOREIGN_KEY_CHECKS <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'FOREIGN_KEY_CHECKS debe estar activo. No se ejecuto la limpieza.';
    END IF;
    IF COALESCE(@invweb_e1_aplicar,0) NOT IN (0,1) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'aplicar debe valer 0 (plan) o 1 (aplicar).';
    END IF;
    IF COALESCE(@invweb_e1_aplicar,0) = 1 AND
       (BINARY COALESCE(@invweb_e1_base_confirmada,'') <> BINARY v_db OR COALESCE(@invweb_e1_respaldo_verificado,0) <> 1) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Confirmar nombre exacto de base y respaldo verificado antes de aplicar.';
    END IF;
    SELECT COUNT(*) INTO v_count FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = v_db AND TABLE_TYPE = 'BASE TABLE'
          AND TABLE_NAME IN ('inventarios','inventario_items');
    IF v_count <> 2 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La base seleccionada no tiene las tablas de inventarios esperadas.';
    END IF;

    -- Examinar TODAS las dependencias antes del primer UPDATE/DROP/ALTER.
    SELECT COUNT(*) INTO v_count FROM information_schema.KEY_COLUMN_USAGE k
    WHERE k.REFERENCED_TABLE_SCHEMA = v_db
      AND k.REFERENCED_TABLE_NAME IN ('conciliacion_remito_items','conciliacion_ingresos_control',
          'conciliacion_egresos_control','conciliacion_items_excluidos',
          'conciliacion_remitos','conciliacion_items','conciliaciones')
      AND NOT (
        (k.TABLE_SCHEMA = v_db AND k.TABLE_NAME IN ('conciliacion_remito_items','conciliacion_ingresos_control',
          'conciliacion_egresos_control','conciliacion_items_excluidos',
          'conciliacion_remitos','conciliacion_items','conciliaciones')
         AND FIELD(k.TABLE_NAME,'conciliacion_remito_items','conciliacion_ingresos_control',
          'conciliacion_egresos_control','conciliacion_items_excluidos',
          'conciliacion_remitos','conciliacion_items','conciliaciones') <
             FIELD(k.REFERENCED_TABLE_NAME,'conciliacion_remito_items','conciliacion_ingresos_control',
          'conciliacion_egresos_control','conciliacion_items_excluidos',
          'conciliacion_remitos','conciliacion_items','conciliaciones'))
        OR
        (k.TABLE_SCHEMA = v_db AND k.TABLE_NAME = 'analisis_stock'
         AND k.COLUMN_NAME = 'conciliacion_legacy_id' AND k.REFERENCED_TABLE_NAME = 'conciliaciones'
         AND EXISTS (SELECT 1 FROM information_schema.COLUMNS c WHERE c.TABLE_SCHEMA = v_db
                     AND c.TABLE_NAME = 'analisis_stock' AND c.COLUMN_NAME = 'conciliacion_legacy_id'
                     AND c.IS_NULLABLE = 'YES')
         AND (SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE ck
              WHERE ck.TABLE_SCHEMA = k.TABLE_SCHEMA AND ck.TABLE_NAME = k.TABLE_NAME
                AND ck.CONSTRAINT_NAME = k.CONSTRAINT_NAME) = 1)
      );
    IF v_count <> 0 THEN
        SELECT k.TABLE_SCHEMA,k.TABLE_NAME,k.CONSTRAINT_NAME,k.COLUMN_NAME,k.REFERENCED_TABLE_NAME
        FROM information_schema.KEY_COLUMN_USAGE k WHERE k.REFERENCED_TABLE_SCHEMA = v_db
          AND k.REFERENCED_TABLE_NAME IN ('conciliacion_remito_items','conciliacion_ingresos_control',
          'conciliacion_egresos_control','conciliacion_items_excluidos',
          'conciliacion_remitos','conciliacion_items','conciliaciones');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Dependencia u orden de claves no previsto. Revisar el esquema; no se ejecuto la limpieza.';
    END IF;

    DROP TEMPORARY TABLE IF EXISTS invweb_e1_plan;
    DROP TEMPORARY TABLE IF EXISTS invweb_e1_conteos;
    CREATE TEMPORARY TABLE invweb_e1_plan (orden INT NOT NULL, sentencia TEXT NOT NULL);
    CREATE TEMPORARY TABLE invweb_e1_conteos (tabla VARCHAR(64) NOT NULL, antes BIGINT NOT NULL, despues BIGINT NULL);

    OPEN v_keys;
    keys_loop: LOOP
        FETCH v_keys INTO v_name;
        IF v_done = 1 THEN LEAVE keys_loop; END IF;
        IF v_order = 0 THEN
            SET v_order = v_order + 1;
            INSERT INTO invweb_e1_plan VALUES (v_order,
                'UPDATE `analisis_stock` SET `conciliacion_legacy_id` = NULL WHERE `conciliacion_legacy_id` IS NOT NULL');
        END IF;
        SET v_order = v_order + 1;
        INSERT INTO invweb_e1_plan VALUES (v_order,CONCAT('ALTER TABLE `analisis_stock` DROP FOREIGN KEY `',REPLACE(v_name,'`','``'),'`'));
    END LOOP;
    CLOSE v_keys;
    SET v_done = 0;
    OPEN v_legacy;
    legacy_loop: LOOP
        FETCH v_legacy INTO v_name;
        IF v_done = 1 THEN LEAVE legacy_loop; END IF;
        SET v_order = v_order + 1;
        INSERT INTO invweb_e1_plan VALUES (v_order,CONCAT('DROP TABLE `',REPLACE(v_name,'`','``'),'`'));
    END LOOP;
    CLOSE v_legacy;

    SELECT v_db AS base_gestion, VERSION() AS version_servidor, COALESCE(@invweb_e1_aplicar,0) AS aplicar;
    SELECT orden, CONCAT(sentencia,';') AS sql_previsto FROM invweb_e1_plan ORDER BY orden;
    IF COALESCE(@invweb_e1_aplicar,0) = 1 THEN
        SET v_done = 0;
        OPEN v_protected;
        before_loop: LOOP
            FETCH v_protected INTO v_name;
            IF v_done = 1 THEN LEAVE before_loop; END IF;
            SET @invweb_e1_sql = CONCAT('SELECT COUNT(*) INTO @invweb_e1_count FROM `',REPLACE(v_name,'`','``'),'`');
            PREPARE invweb_e1_stmt FROM @invweb_e1_sql;
            EXECUTE invweb_e1_stmt;
            DEALLOCATE PREPARE invweb_e1_stmt;
            INSERT INTO invweb_e1_conteos VALUES (v_name,@invweb_e1_count,NULL);
        END LOOP;
        CLOSE v_protected;
        -- No mantener un cursor abierto durante DDL con commit implicito.
        WHILE v_apply_index <= v_order DO
            SELECT sentencia INTO v_command FROM invweb_e1_plan WHERE orden = v_apply_index;
            SET @invweb_e1_sql = v_command;
            PREPARE invweb_e1_stmt FROM @invweb_e1_sql;
            EXECUTE invweb_e1_stmt;
            DEALLOCATE PREPARE invweb_e1_stmt;
            SET v_apply_index = v_apply_index + 1;
        END WHILE;
        SET v_done = 0;
        OPEN v_protected;
        after_loop: LOOP
            FETCH v_protected INTO v_name;
            IF v_done = 1 THEN LEAVE after_loop; END IF;
            SET @invweb_e1_sql = CONCAT('SELECT COUNT(*) INTO @invweb_e1_count FROM `',REPLACE(v_name,'`','``'),'`');
            PREPARE invweb_e1_stmt FROM @invweb_e1_sql;
            EXECUTE invweb_e1_stmt;
            DEALLOCATE PREPARE invweb_e1_stmt;
            UPDATE invweb_e1_conteos SET despues = @invweb_e1_count WHERE tabla = v_name;
        END LOOP;
        CLOSE v_protected;
        SELECT tabla,antes,despues FROM invweb_e1_conteos ORDER BY tabla;
        SELECT COUNT(*) INTO v_count FROM invweb_e1_conteos WHERE antes <> despues OR despues IS NULL;
        IF v_count <> 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cambio de cantidad en tablas protegidas. Detenerse y revisar el respaldo.';
        END IF;
        SELECT 'Limpieza terminada. Cantidades de inventarios y tablas protegidas conservadas.' AS resultado;
    ELSE
        SELECT 'Solo plan: no se borraron tablas ni se actualizaron datos.' AS resultado;
    END IF;
    DROP TEMPORARY TABLE invweb_e1_plan;
    DROP TEMPORARY TABLE invweb_e1_conteos;
END$$
DELIMITER ;
CALL invweb_migracion_etapa1_retirar_pruebas();
DROP PROCEDURE invweb_migracion_etapa1_retirar_pruebas;
