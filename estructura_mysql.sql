SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
CREATE TABLE catalogos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tipo VARCHAR(30) NOT NULL, 
	codigo VARCHAR(30) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	activo BOOL NOT NULL, 
	orden INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_catalogo_tipo_codigo UNIQUE (tipo, codigo)
);
CREATE INDEX ix_catalogos_tipo ON catalogos (tipo);
CREATE TABLE configuraciones (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	clave VARCHAR(60) NOT NULL, 
	valor VARCHAR(255) NOT NULL, 
	descripcion VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (clave)
);
CREATE TABLE declaraciones (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	numero VARCHAR(30), 
	fecha DATE NOT NULL, 
	sector_declara VARCHAR(40) NOT NULL, 
	unidad_gestion VARCHAR(120), 
	celula_detecta VARCHAR(80) NOT NULL, 
	celula_codigo_equipos VARCHAR(80), 
	legajo_declara VARCHAR(30) NOT NULL, 
	turno_id INTEGER, 
	turno VARCHAR(80), 
	equipo VARCHAR(80) NOT NULL, 
	equipo_descripcion VARCHAR(160), 
	cliente VARCHAR(100), 
	lugar_detectado VARCHAR(120) NOT NULL, 
	observaciones TEXT, 
	estado VARCHAR(30) NOT NULL, 
	legajo_calidad VARCHAR(30), 
	fecha_validacion DATETIME, 
	observaciones_calidad TEXT, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_declaraciones_numero ON declaraciones (numero);
CREATE TABLE grupos_motivo (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(20) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	activo BOOL NOT NULL, 
	orden INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);
CREATE TABLE piezas_control_logistica (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(50) NOT NULL, 
	descripcion VARCHAR(255), 
	activo BOOL NOT NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_piezas_control_logistica_codigo ON piezas_control_logistica (codigo);
CREATE TABLE unidades_gestion (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(30) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	activo BOOL NOT NULL, 
	orden INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	UNIQUE (nombre)
);
CREATE TABLE usuarios (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario VARCHAR(40) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	rol VARCHAR(20) NOT NULL, 
	clave_hash VARCHAR(255) NOT NULL, 
	activo BOOL NOT NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_usuarios_usuario ON usuarios (usuario);
CREATE TABLE versiones_esquema (
	version INTEGER NOT NULL AUTO_INCREMENT, 
	descripcion VARCHAR(255) NOT NULL, 
	aplicado_en DATETIME NOT NULL, 
	PRIMARY KEY (version)
);
CREATE TABLE celulas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(30) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	codigo_equipos VARCHAR(80) NOT NULL, 
	unidad_gestion_id INTEGER NOT NULL, 
	activo BOOL NOT NULL, 
	orden INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	UNIQUE (nombre), 
	UNIQUE (codigo_equipos), 
	FOREIGN KEY(unidad_gestion_id) REFERENCES unidades_gestion (id)
);
CREATE INDEX ix_celulas_unidad_gestion_id ON celulas (unidad_gestion_id);
CREATE TABLE motivos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(10) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	activo BOOL NOT NULL, 
	tipo_accion VARCHAR(20) NOT NULL, 
	grupo_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	FOREIGN KEY(grupo_id) REFERENCES grupos_motivo (id)
);
CREATE INDEX ix_motivos_grupo_id ON motivos (grupo_id);
CREATE TABLE declaracion_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	declaracion_id INTEGER NOT NULL, 
	tipo_material VARCHAR(30) NOT NULL, 
	codigo_padre VARCHAR(50), 
	codigo_pieza VARCHAR(50) NOT NULL, 
	codigo_cliente VARCHAR(50), 
	material VARCHAR(80), 
	descripcion VARCHAR(255), 
	trazabilidad VARCHAR(6) NOT NULL, 
	operacion_codigo VARCHAR(30), 
	operacion_descripcion VARCHAR(160), 
	unidad VARCHAR(10) NOT NULL, 
	uso_estructura NUMERIC(12, 4), 
	cantidad_detectada NUMERIC(12, 3) NOT NULL, 
	cantidad_scrap_directo NUMERIC(12, 3) NOT NULL, 
	cantidad_a_retrabajo NUMERIC(12, 3) NOT NULL, 
	cantidad_liberada NUMERIC(12, 3) NOT NULL, 
	motivo_id INTEGER NOT NULL, 
	sector_origen VARCHAR(40) NOT NULL, 
	celula_origen VARCHAR(80) NOT NULL, 
	operacion_origen VARCHAR(120) NOT NULL, 
	legajo_origen VARCHAR(30), 
	tipo_imputacion VARCHAR(20) NOT NULL, 
	tipo_origen VARCHAR(20) NOT NULL, 
	proveedor_numero VARCHAR(30), 
	proveedor VARCHAR(120), 
	remito VARCHAR(80), 
	afectado_tipo VARCHAR(20), 
	afectado_codigo VARCHAR(80), 
	afectado_descripcion VARCHAR(255), 
	afectado_componente_codigo VARCHAR(50), 
	responsabilidad_estado VARCHAR(24) NOT NULL, 
	responsable_tipo VARCHAR(20), 
	responsable_sector VARCHAR(40), 
	responsable_celula VARCHAR(80), 
	responsable_operacion VARCHAR(120), 
	responsable_legajo VARCHAR(30), 
	responsable_proveedor_numero VARCHAR(30), 
	responsable_proveedor VARCHAR(120), 
	observacion_calidad VARCHAR(255), 
	observacion VARCHAR(255), 
	requiere_validacion_logistica BOOL NOT NULL, 
	cantidad_scrap_validada_logistica NUMERIC(12, 3), 
	legajo_logistica VARCHAR(30), 
	fecha_validacion_logistica DATETIME, 
	observacion_logistica VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(declaracion_id) REFERENCES declaraciones (id), 
	FOREIGN KEY(motivo_id) REFERENCES motivos (id)
);
CREATE INDEX ix_declaracion_items_declaracion_id ON declaracion_items (declaracion_id);
CREATE TABLE retrabajo_intervenciones (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	item_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	operacion VARCHAR(120) NOT NULL, 
	celula VARCHAR(80) NOT NULL, 
	legajo VARCHAR(30) NOT NULL, 
	minutos INTEGER NOT NULL, 
	cantidad_personas INTEGER NOT NULL, 
	cantidad_ok NUMERIC(12, 3) NOT NULL, 
	cantidad_scrap NUMERIC(12, 3) NOT NULL, 
	motivo_scrap_id INTEGER, 
	observaciones VARCHAR(255), 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(item_id) REFERENCES declaracion_items (id), 
	FOREIGN KEY(motivo_scrap_id) REFERENCES motivos (id)
);
CREATE INDEX ix_retrabajo_intervenciones_item_id ON retrabajo_intervenciones (item_id);
SET FOREIGN_KEY_CHECKS=1;
