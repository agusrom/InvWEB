import json
import time
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from app import (
    Celula,
    Configuracion,
    Declaracion,
    DeclaracionItem,
    PiezaControlLogistica,
    RetrabajoIntervencion,
    UnidadGestion,
    actualizar_control_logistica,
    actualizar_estado,
    create_app,
    db,
    numero_declaracion,
)


def crear_app_prueba():
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "PRODUCTIVE_DEMO_MODE": True,
            "AUXILIARY_DEMO_MODE": True,
            "SECRET_KEY": "test",
            "AUTH_DISABLED": True,
        }
    )


def test_textos_visibles_no_exponen_nombres_tecnicos():
    raiz = Path(__file__).resolve().parents[1]
    nombres_tecnicos = {
        "produc01",
        "produc10",
        "produc21",
        "controlo",
        "controlt",
        "tablaequipos",
        "mtprim01",
        "mtprim05",
        "mysql",
    }
    archivos_visibles = [
        *raiz.joinpath("templates").glob("*.html"),
        *raiz.joinpath("static", "js").glob("*.js"),
    ]
    for archivo in archivos_visibles:
        contenido = archivo.read_text(encoding="utf-8").lower()
        encontrados = {nombre for nombre in nombres_tecnicos if nombre in contenido}
        assert not encontrados, f"{archivo.name} expone: {sorted(encontrados)}"


def test_selector_buscable_muestra_todas_las_opciones_al_abrirse():
    raiz = Path(__file__).resolve().parents[1]
    contenido = raiz.joinpath("static", "js", "searchable-select.js").read_text(
        encoding="utf-8"
    )
    inicio = contenido.index('input.addEventListener("focus"')
    fin = contenido.index('input.addEventListener("input"', inicio)
    controlador_focus = contenido[inicio:fin]

    assert "input.select();" in controlador_focus
    assert 'render("");' in controlador_focus
    assert "render(input.value)" not in controlador_focus


def test_reporte_scrap_explota_al_ultimo_nivel_y_exporta_excel():
    app = crear_app_prueba()
    client = app.test_client()
    with app.app_context():
        motivo_id = db.session.execute(
            db.text("SELECT id FROM motivos ORDER BY id LIMIT 1")
        ).scalar_one()
        declaracion = Declaracion(
            numero="DNC-009001",
            fecha=date(2026, 10, 15),
            sector_declara="Producción",
            unidad_gestion="Producción",
            celula_detecta="Célula 0001",
            legajo_declara="123",
            turno="Mañana",
            equipo="101",
            cliente="Cliente reporte",
            lugar_detectado="Célula 0001",
            estado="CERRADA",
            fecha_validacion=datetime(2026, 10, 15, 10, 0),
        )
        item = DeclaracionItem(
            tipo_material="PIEZA_TERMINADA",
            codigo_pieza="CONJ-1000",
            descripcion="Conjunto de prueba",
            trazabilidad="123456",
            unidad="PZS",
            cantidad_detectada=5,
            cantidad_scrap_directo=2,
            cantidad_a_retrabajo=1,
            cantidad_liberada=2,
            motivo_id=motivo_id,
            sector_origen="Producción",
            celula_origen="Célula 0001",
            operacion_origen="Soldadura",
            tipo_imputacion="INTERNA",
        )
        item.intervenciones.append(RetrabajoIntervencion(
            fecha=date(2026, 10, 16),
            operacion="Retrabajo",
            celula="Retrabajo",
            legajo="456",
            minutos=20,
            cantidad_personas=1,
            cantidad_ok=0,
            cantidad_scrap=1,
        ))
        declaracion.items.append(item)
        db.session.add(declaracion)
        db.session.commit()

    query = "desde=2026-10-01&hasta=2026-10-31&cliente=Cliente%20reporte"
    pagina = client.get(f"/reportes/scrap?{query}")
    assert pagina.status_code == 200
    html = pagina.get_data(as_text=True)
    assert "Scrap por componente final" in html
    assert "CH-1110" in html
    assert "CH-1120" in html
    assert "TUB-1130" in html
    assert "SUB-1100" not in html
    assert ">6.000<" in html  # tubo: 3 piezas scrap x uso 2

    excel = client.get(f"/reportes/scrap/excel?{query}")
    assert excel.status_code == 200
    libro = load_workbook(BytesIO(excel.data), data_only=True)
    assert libro.sheetnames == [
        "Resumen por componente", "Detalle trazable", "Filtros aplicados"
    ]
    resumen = list(libro["Resumen por componente"].values)
    filas = {fila[0]: fila for fila in resumen[1:]}
    assert filas["CH-1110"][6] == 3
    assert filas["TUB-1130"][6] == 6


def test_reporte_scrap_considera_una_pieza_sin_estructura_como_componente_final():
    app = crear_app_prueba()
    client = app.test_client()
    with app.app_context():
        motivo_id = db.session.execute(
            db.text("SELECT id FROM motivos ORDER BY id LIMIT 1")
        ).scalar_one()
        declaracion = Declaracion(
            numero="DNC-009002", fecha=date(2026, 10, 20),
            sector_declara="Producción", celula_detecta="Recepción",
            legajo_declara="123", equipo="401", lugar_detectado="Recepción",
            estado="CERRADA",
        )
        declaracion.items.append(DeclaracionItem(
            tipo_material="COMPONENTE", codigo_pieza="CH-1110",
            descripcion="Chapa izquierda", trazabilidad="654321", unidad="PZS",
            cantidad_detectada=4, cantidad_scrap_directo=4,
            cantidad_a_retrabajo=0, cantidad_liberada=0, motivo_id=motivo_id,
            sector_origen="Proveedor", celula_origen="Recepción",
            operacion_origen="Ingreso", tipo_imputacion="PROVEEDOR",
        ))
        db.session.add(declaracion)
        db.session.commit()
    html = client.get(
        "/reportes/scrap?desde=2026-10-01&hasta=2026-10-31&pieza=CH-1110"
    ).get_data(as_text=True)
    assert "CH-1110" in html
    assert ">4.000<" in html


def test_produccion_puede_consultar_e_imprimir_declaraciones():
    app = crear_app_prueba()
    client = app.test_client()
    with app.app_context():
        motivo_id = db.session.execute(
            db.text("SELECT id FROM motivos ORDER BY id LIMIT 1")
        ).scalar_one()
        declaracion = Declaracion(
            numero="DEC-2026-009999",
            fecha=date(2026, 8, 3),
            sector_declara="Producción",
            unidad_gestion="Producción",
            celula_detecta="Célula 0001",
            legajo_declara="123",
            turno="Mañana",
            equipo="101",
            lugar_detectado="Célula 0001",
            estado="PENDIENTE_CALIDAD",
        )
        declaracion.items.append(DeclaracionItem(
            tipo_material="PIEZA_TERMINADA",
            codigo_pieza="CONJ-1000",
            descripcion="Conjunto de prueba",
            trazabilidad="123456",
            unidad="PZS",
            cantidad_detectada=2,
            cantidad_scrap_directo=0,
            cantidad_a_retrabajo=0,
            cantidad_liberada=0,
            motivo_id=motivo_id,
            sector_origen="No determinado",
            celula_origen="No determinada",
            operacion_origen="No determinada",
            tipo_imputacion="NO_DETERMINADA",
        ))
        db.session.add(declaracion)
        db.session.commit()
        declaracion_id = declaracion.id

    historial = client.get("/produccion/declaraciones")
    historial_html = historial.get_data(as_text=True)
    assert historial.status_code == 200
    assert "DEC-2026-009999" in historial_html
    assert "CONJ-1000" in historial_html
    assert "Imprimir" in historial_html

    detalle = client.get(f"/produccion/declaraciones/{declaracion_id}")
    assert detalle.status_code == 200
    assert "DECLARACIÓN DE MATERIAL NO CONFORME" in detalle.get_data(as_text=True)

    impresion = client.get(
        f"/produccion/declaraciones/{declaracion_id}?imprimir=1"
    )
    impresion_html = impresion.get_data(as_text=True)
    assert "window.print()" in impresion_html
    assert "AVISO INICIAL · PRODUCCIÓN" in impresion_html
    assert "Material informado y disposición" in impresion_html
    assert "RENGLÓN 1" in impresion_html
    assert "CANTIDAD INFORMADA" in impresion_html
    assert "PROBLEMA INFORMADO POR PRODUCCIÓN" in impresion_html
    assert "DECISIÓN E INDICACIÓN DE CALIDAD" in impresion_html
    assert 'class="print-operation-value"' in impresion_html
    assert 'class="print-hcp-value"' in impresion_html
    assert 'class="print-piece-state"' in impresion_html
    css_impresion = Path(__file__).resolve().parents[1].joinpath(
        "static", "css", "app.css"
    ).read_text(encoding="utf-8")
    assert "@page { size: A4 portrait;" in css_impresion
    assert ".print-piece-card { min-height: 40mm;" in css_impresion

    historial_calidad = client.get("/calidad/declaraciones")
    assert historial_calidad.status_code == 200
    assert "DEC-2026-009999" in historial_calidad.get_data(as_text=True)
    detalle_calidad = client.get(f"/calidad/declaraciones/{declaracion_id}")
    assert detalle_calidad.status_code == 200

    historial_logistica = client.get("/logistica/declaraciones")
    assert historial_logistica.status_code == 200
    assert "DEC-2026-009999" in historial_logistica.get_data(as_text=True)
    detalle_logistica = client.get(f"/logistica/declaraciones/{declaracion_id}")
    assert detalle_logistica.status_code == 200

    exito = client.get(f"/produccion/listo/{declaracion_id}")
    exito_html = exito.get_data(as_text=True)
    assert "window.open(" in exito_html
    assert f"/produccion/declaraciones/{declaracion_id}?imprimir=1" in exito_html


def test_admin_puede_editar_y_eliminar_declaracion_completa():
    app = crear_app_prueba()
    client = app.test_client()
    with app.app_context():
        motivo_id = db.session.execute(
            db.text("SELECT id FROM motivos ORDER BY id LIMIT 1")
        ).scalar_one()
        declaracion = Declaracion(
            numero="DNC-000777",
            fecha=date(2026, 8, 5),
            sector_declara="Producción",
            unidad_gestion="UAP",
            celula_detecta="Célula 0001",
            legajo_declara="123",
            turno="Mañana",
            equipo="101",
            lugar_detectado="Célula 0001",
            estado="PENDIENTE_RETRABAJO",
            fecha_validacion=datetime(2026, 8, 5, 10, 0),
            legajo_calidad="900",
        )
        item = DeclaracionItem(
            tipo_material="PIEZA_TERMINADA",
            codigo_pieza="CONJ-1000",
            descripcion="Descripción original",
            trazabilidad="123456",
            operacion_codigo="030",
            operacion_descripcion="Soldadura",
            unidad="PZS",
            cantidad_detectada=5,
            cantidad_scrap_directo=3,
            cantidad_a_retrabajo=2,
            cantidad_liberada=0,
            motivo_id=motivo_id,
            sector_origen="Producción",
            celula_origen="Soldadura",
            operacion_origen="030",
            tipo_imputacion="CONFIRMADA",
            tipo_origen="INTERNO",
            responsabilidad_estado="CONFIRMADA",
            observacion_calidad="Retrabajar dos piezas",
        )
        item.intervenciones.append(RetrabajoIntervencion(
            fecha=date(2026, 8, 5),
            operacion="Reparación parcial",
            celula="Retrabajo",
            legajo="321",
            minutos=10,
            cantidad_personas=1,
            cantidad_ok=1,
            cantidad_scrap=0,
        ))
        declaracion.items.append(item)
        db.session.add(declaracion)
        db.session.commit()
        declaracion_id = declaracion.id
        item_id = item.id
        intervencion_id = item.intervenciones[0].id

    pagina = client.get(f"/declaraciones/{declaracion_id}/editar")
    pagina_html = pagina.get_data(as_text=True)
    assert pagina.status_code == 200
    assert "Guardar modificaciones" in pagina_html
    assert "Eliminar declaración" in pagina_html
    assert "CONJ-1000" in pagina_html

    respuesta = client.post(
        f"/declaraciones/{declaracion_id}/editar",
        data={
            "fecha": "2026-08-06",
            "sector_declara": "Producción corregida",
            "unidad_gestion": "UAP corregida",
            "celula_detecta": "Célula corregida",
            "legajo_declara": "456",
            "turno": "Tarde",
            "equipo": "202",
            "equipo_descripcion": "Equipo corregido",
            "cliente": "Cliente corregido",
            "legajo_calidad": "901",
            "observaciones": "Observación corregida",
            "observaciones_calidad": "Calidad corregida",
            f"item_{item_id}_tipo_material": "PIEZA_TERMINADA",
            f"item_{item_id}_codigo_pieza": "CONJ-1000",
            f"item_{item_id}_descripcion": "Descripción corregida",
            f"item_{item_id}_operacion_codigo": "030",
            f"item_{item_id}_operacion_descripcion": "Soldadura corregida",
            f"item_{item_id}_trazabilidad": "654321",
            f"item_{item_id}_unidad": "PZS",
            f"item_{item_id}_cantidad_detectada": "5",
            f"item_{item_id}_cantidad_scrap_directo": "3",
            f"item_{item_id}_cantidad_a_retrabajo": "2",
            f"item_{item_id}_cantidad_liberada": "0",
            f"item_{item_id}_motivo_id": str(motivo_id),
            f"item_{item_id}_afectado_tipo": "",
            f"item_{item_id}_afectado_codigo": "",
            f"item_{item_id}_afectado_descripcion": "",
            f"item_{item_id}_afectado_componente_codigo": "",
            f"item_{item_id}_observacion": "Producción corregida",
            f"item_{item_id}_observacion_calidad": "Retrabajar dos piezas",
            f"item_{item_id}_tipo_origen": "INTERNO",
            f"item_{item_id}_tipo_imputacion": "CONFIRMADA",
            f"item_{item_id}_sector_origen": "Producción",
            f"item_{item_id}_celula_origen": "Soldadura",
            f"item_{item_id}_operacion_origen": "030",
            f"item_{item_id}_legajo_origen": "111",
            f"item_{item_id}_proveedor_numero": "",
            f"item_{item_id}_proveedor": "",
            f"item_{item_id}_remito": "",
            f"item_{item_id}_responsabilidad_estado": "CONFIRMADA",
            f"item_{item_id}_responsable_tipo": "INTERNO",
            f"item_{item_id}_responsable_sector": "Producción",
            f"item_{item_id}_responsable_celula": "Soldadura",
            f"item_{item_id}_responsable_operacion": "030",
            f"item_{item_id}_responsable_legajo": "111",
            f"item_{item_id}_responsable_proveedor_numero": "",
            f"item_{item_id}_responsable_proveedor": "",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert "actualizada correctamente" in respuesta.get_data(as_text=True)
    with app.app_context():
        actualizada = db.session.get(Declaracion, declaracion_id)
        item_actualizado = db.session.get(DeclaracionItem, item_id)
        assert actualizada.numero == "DNC-000777"
        assert actualizada.fecha == date(2026, 8, 6)
        assert actualizada.celula_detecta == "Célula corregida"
        assert item_actualizado.descripcion == "Descripción corregida"
        assert item_actualizado.trazabilidad == "654321"
        assert item_actualizado.cantidad_a_retrabajo == 2

    rechazo = client.post(
        f"/declaraciones/{declaracion_id}/eliminar",
        data={"confirmacion": "INCORRECTA"},
    )
    assert rechazo.status_code == 400
    borrado = client.post(
        f"/declaraciones/{declaracion_id}/eliminar",
        data={"confirmacion": "DNC-000777"},
        follow_redirects=True,
    )
    assert borrado.status_code == 200
    assert "fue eliminada" in borrado.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Declaracion, declaracion_id) is None
        assert db.session.get(DeclaracionItem, item_id) is None
        assert db.session.get(RetrabajoIntervencion, intervencion_id) is None


def test_codificacion_declaracion_configurable():
    app = crear_app_prueba()
    with app.app_context():
        declaracion = Declaracion(
            fecha=date(2026, 8, 4),
            sector_declara="Producción",
            celula_detecta="Célula 0001",
            legajo_declara="123",
            equipo="101",
            lugar_detectado="Célula 0001",
        )
        db.session.add(declaracion)
        db.session.flush()
        assert numero_declaracion(declaracion) == "DNC-000001"

        db.session.execute(
            db.update(Configuracion)
            .where(Configuracion.clave == "PREFIJO_DECLARACION")
            .values(valor="NC")
        )
        db.session.execute(
            db.update(Configuracion)
            .where(Configuracion.clave == "DIGITOS_DECLARACION")
            .values(valor="8")
        )
        db.session.flush()
        assert numero_declaracion(declaracion) == "NC-00000001"


def test_logistica_valida_solo_piezas_configuradas():
    app = crear_app_prueba()
    client = app.test_client()

    alta = client.post(
        "/gestion/piezas-control-logistica",
        data={"codigo": "CONJ-1000"},
        follow_redirects=True,
    )
    assert alta.status_code == 200
    assert "CONJ-1000" in alta.get_data(as_text=True)

    configuracion = client.get("/gestion/piezas-control-logistica")
    assert configuracion.headers["Cache-Control"] == "no-store"
    assert "1 código guardado" in configuracion.get_data(as_text=True)
    consulta_logistica = client.get("/logistica/piezas-control")
    assert consulta_logistica.status_code == 200
    assert "CONJ-1000" in consulta_logistica.get_data(as_text=True)

    with app.app_context():
        pieza_configurada = db.session.execute(
            db.select(PiezaControlLogistica).where(
                PiezaControlLogistica.codigo == "CONJ-1000"
            )
        ).scalar_one()
        assert pieza_configurada.activo is True
        pieza_configurada_id = pieza_configurada.id
        motivo_id = db.session.execute(
            db.text("SELECT id FROM motivos ORDER BY id LIMIT 1")
        ).scalar_one()
        declaracion = Declaracion(
            numero="DNC-000010",
            fecha=date(2026, 8, 4),
            sector_declara="Producción",
            celula_detecta="Célula 0001",
            legajo_declara="123",
            equipo="101",
            lugar_detectado="Célula 0001",
            estado="PENDIENTE_CALIDAD",
            fecha_validacion=datetime(2026, 8, 4, 10, 0),
        )
        configurado = DeclaracionItem(
            tipo_material="PIEZA_TERMINADA",
            codigo_pieza="CONJ-1000",
            descripcion="Conjunto de prueba",
            trazabilidad="123456",
            unidad="PZS",
            cantidad_detectada=3,
            cantidad_scrap_directo=3,
            cantidad_a_retrabajo=0,
            cantidad_liberada=0,
            motivo_id=motivo_id,
            sector_origen="No determinado",
            celula_origen="No determinada",
            operacion_origen="No determinada",
            tipo_imputacion="NO_DETERMINADA",
            observacion_calidad="Enviar tres piezas a scrap",
        )
        no_configurado = DeclaracionItem(
            tipo_material="PIEZA_TERMINADA",
            codigo_pieza="CH-1110",
            descripcion="Componente sin control",
            trazabilidad="654321",
            unidad="PZS",
            cantidad_detectada=2,
            cantidad_scrap_directo=2,
            cantidad_a_retrabajo=0,
            cantidad_liberada=0,
            motivo_id=motivo_id,
            sector_origen="No determinado",
            celula_origen="No determinada",
            operacion_origen="No determinada",
            tipo_imputacion="NO_DETERMINADA",
            observacion_calidad="Enviar dos piezas a scrap",
        )
        declaracion.items.extend([configurado, no_configurado])
        db.session.add(declaracion)
        db.session.flush()
        actualizar_control_logistica(configurado)
        actualizar_control_logistica(no_configurado)
        actualizar_estado(declaracion)
        db.session.commit()
        item_id = configurado.id
        declaracion_id = declaracion.id
        assert configurado.requiere_validacion_logistica is True
        assert no_configurado.requiere_validacion_logistica is False
        assert declaracion.estado == "PENDIENTE_LOGISTICA"

    client.post(
        f"/gestion/piezas-control-logistica/{pieza_configurada_id}/alternar"
    )
    reactivada = client.post(
        "/gestion/piezas-control-logistica",
        data={"codigo": "conj-1000"},
        follow_redirects=True,
    )
    assert "Pieza reactivada" in reactivada.get_data(as_text=True)
    with app.app_context():
        configuradas = db.session.execute(
            db.select(PiezaControlLogistica).where(
                PiezaControlLogistica.codigo == "CONJ-1000"
            )
        ).scalars().all()
        assert len(configuradas) == 1
        assert configuradas[0].activo is True

    bandeja = client.get("/logistica")
    bandeja_html = bandeja.get_data(as_text=True)
    assert bandeja.status_code == 200
    assert "CONJ-1000" in bandeja_html
    assert "CH-1110" not in bandeja_html
    assert "Enviar tres piezas a scrap" in bandeja_html
    assert "pieza configurada" in bandeja_html
    assert ">1</b>" in bandeja_html

    diferencia_sin_comentario = client.post(
        f"/logistica/validaciones/{item_id}",
        data={"cantidad": "2", "legajo": "321", "observacion": ""},
    )
    assert diferencia_sin_comentario.status_code == 400

    validacion = client.post(
        f"/logistica/validaciones/{item_id}",
        data={"cantidad": "3", "legajo": "321", "observacion": ""},
        follow_redirects=True,
    )
    assert validacion.status_code == 200
    validacion_html = validacion.get_data(as_text=True)
    assert "Cantidad de CONJ-1000 validada" in validacion_html
    assert "window.open(" in validacion_html
    assert f"/logistica/declaraciones/{declaracion_id}?imprimir=1" in validacion_html

    impresion = client.get(
        f"/logistica/declaraciones/{declaracion_id}?imprimir=1"
    )
    impresion_html = impresion.get_data(as_text=True)
    assert "VALIDACIÓN DE LOGÍSTICA COMPLETA" in impresion_html
    assert "Logística: 3 PZS" in impresion_html
    with app.app_context():
        item = db.session.get(DeclaracionItem, item_id)
        declaracion = db.session.get(Declaracion, declaracion_id)
        assert item.cantidad_scrap_validada_logistica == 3
        assert item.legajo_logistica == "321"
        assert item.fecha_validacion_logistica is not None
        assert declaracion.estado == "CERRADA"


def test_configuracion_logistica_persiste_entre_reinicios(tmp_path):
    database_uri = f"sqlite:///{tmp_path / 'persistencia-logistica.db'}"
    configuracion = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "PRODUCTIVE_DEMO_MODE": True,
        "AUXILIARY_DEMO_MODE": True,
        "SECRET_KEY": "persistencia",
        "AUTH_DISABLED": True,
    }
    primera_app = create_app(configuracion)
    alta = primera_app.test_client().post(
        "/gestion/piezas-control-logistica",
        data={"codigo": "CONJ-1000"},
        follow_redirects=True,
    )
    assert alta.status_code == 200
    with primera_app.app_context():
        assert db.session.execute(
            db.select(PiezaControlLogistica).where(
                PiezaControlLogistica.codigo == "CONJ-1000"
            )
        ).scalar_one().activo is True
        db.session.remove()
        db.engine.dispose()

    segunda_app = create_app(configuracion)
    consulta = segunda_app.test_client().get(
        "/gestion/piezas-control-logistica"
    )
    assert consulta.status_code == 200
    assert "CONJ-1000" in consulta.get_data(as_text=True)
    with segunda_app.app_context():
        filas = db.session.execute(db.select(PiezaControlLogistica)).scalars().all()
        assert [(fila.codigo, fila.activo) for fila in filas] == [
            ("CONJ-1000", True)
        ]


def test_inicio_seguro_y_aviso_de_modo_demostracion():
    raiz = Path(__file__).resolve().parents[1]
    inicio = raiz.joinpath("run.bat").read_text(encoding="utf-8")
    assert "if not exist .env" in inicio
    assert "copy .env.example .env" not in inicio
    assert raiz.joinpath("migrar_desde_version_anterior.bat").exists()
    assert raiz.joinpath("migrar_a_mysql.bat").exists()
    assert raiz.joinpath("migrar_a_mysql.py").exists()
    assert raiz.joinpath("estructura_mysql.sql").exists()
    assert not raiz.joinpath("run_demo.bat").exists()

    app = crear_app_prueba()
    pagina = app.test_client().get("/produccion/alerta").get_data(as_text=True)
    assert "Modo de prueba activo" in pagina
    assert "Los códigos, turnos, equipos y proveedores son datos de ejemplo" in pagina


def test_acceso_por_cuentas_de_sector():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "PRODUCTIVE_DEMO_MODE": True,
            "SECRET_KEY": "test-auth",
            "AUTH_DISABLED": False,
        }
    )
    client = app.test_client()

    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(minutes=5)
    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is False
    assert app.config["SESSION_MAX_AGE_SECONDS"] == 300

    sin_sesion = client.get("/produccion")
    assert sin_sesion.status_code == 302
    assert "/login" in sin_sesion.headers["Location"]
    clave_incorrecta = client.post(
        "/login", data={"usuario": "produccion", "clave": "incorrecta"}
    )
    assert clave_incorrecta.status_code == 401

    ingreso = client.post(
        "/login",
        data={"usuario": "produccion", "clave": "produccion"},
        follow_redirects=True,
    )
    assert ingreso.status_code == 200
    assert "Material no conforme" in ingreso.get_data(as_text=True)
    assert client.get("/produccion/alerta").status_code == 200
    assert client.get("/produccion/retrabajos").status_code == 200
    assert client.get("/produccion/declaraciones").status_code == 200
    assert client.get("/declaraciones/1/editar").status_code == 403
    assert client.get("/reportes/scrap").status_code == 403
    assert client.post(
        "/declaraciones/1/eliminar", data={"confirmacion": "DNC-000001"}
    ).status_code == 403
    inicio_actualizable = client.get("/produccion/inicio/contenido")
    assert inicio_actualizable.status_code == 200
    assert inicio_actualizable.headers["Cache-Control"] == "no-store"
    assert "production-live-snapshot" in inicio_actualizable.get_data(as_text=True)
    assert client.get("/calidad").status_code == 403
    assert client.get("/logistica").status_code == 403
    assert client.get("/gestion").status_code == 403

    with client.session_transaction() as sesion:
        sesion["sesion_iniciada_en"] = time.time() - 301
    vencida = client.get("/produccion")
    assert vencida.status_code == 302
    assert "/login" in vencida.headers["Location"]
    client.post("/login", data={"usuario": "produccion", "clave": "produccion"})

    client.post("/logout")
    client.post("/login", data={"usuario": "calidad", "clave": "calidad"})
    assert client.get("/calidad").status_code == 200
    assert client.get("/calidad/declaraciones").status_code == 200
    assert client.get("/declaraciones/1/editar").status_code == 403
    assert client.get("/reportes/scrap").status_code == 403
    assert client.get("/produccion").status_code == 403
    assert client.get("/gestion").status_code == 403

    client.post("/logout")
    client.post("/login", data={"usuario": "logistica", "clave": "logistica"})
    assert client.get("/logistica").status_code == 200
    assert client.get("/logistica/informe").status_code == 200
    assert client.get("/logistica/piezas-control").status_code == 200
    assert client.get("/logistica/declaraciones").status_code == 200
    assert client.get("/declaraciones/1/editar").status_code == 403
    assert client.get("/reportes/scrap").status_code == 403
    assert client.get("/produccion").status_code == 403
    assert client.get("/calidad").status_code == 403

    client.post("/logout")
    client.post("/login", data={"usuario": "admin", "clave": "admin"})
    assert client.get("/gestion").status_code == 200
    usuarios = client.get("/gestion/usuarios")
    assert usuarios.status_code == 200
    assert "Usuarios y accesos" in usuarios.get_data(as_text=True)
    assert client.get("/produccion").status_code == 200
    assert client.get("/calidad").status_code == 200
    assert client.get("/logistica").status_code == 200
    assert client.get("/reportes/scrap").status_code == 200

    with app.app_context():
        produccion_id = db.session.execute(
            db.text("SELECT id FROM usuarios WHERE usuario = 'produccion'")
        ).scalar_one()
    cambio = client.post(
        f"/gestion/usuarios/{produccion_id}/clave",
        data={"clave": "nuevo-pin", "confirmacion": "nuevo-pin"},
        follow_redirects=True,
    )
    assert cambio.status_code == 200
    assert "actualizada" in cambio.get_data(as_text=True)
    client.post("/logout")
    assert client.post(
        "/login", data={"usuario": "produccion", "clave": "produccion"}
    ).status_code == 401
    assert client.post(
        "/login", data={"usuario": "produccion", "clave": "nuevo-pin"}
    ).status_code == 302


def test_flujo_mixto_y_retrabajo():
    app = crear_app_prueba()
    client = app.test_client()

    assert client.get("/").status_code == 302
    assert client.get("/produccion").status_code == 200
    assert client.get("/gestion").status_code == 200
    piezas = client.get("/api/piezas?q=conj").get_json()
    assert piezas[0]["codigo"] == "CONJ-1000"
    estructura = client.get("/api/estructura/CONJ-1000").get_json()
    assert len(estructura["componentes"]) == 4
    componentes = {item["codigo"]: item for item in estructura["componentes"]}
    assert componentes["CH-1110"]["material"] == "CHAPA-2MM"
    assert componentes["TUB-1130"]["material"] == "TUBO-25"
    operaciones = client.get("/api/operaciones?q=sold").get_json()
    assert operaciones[0]["titulo"] == "SOLDADURA"
    operaciones_pieza = client.get(
        "/api/piezas/CONJ-1000/operaciones"
    ).get_json()
    assert any(x["codigo"] == "030" for x in operaciones_pieza)
    assert client.get(
        "/api/piezas/CH-1110/operaciones"
    ).get_json() == []
    hcp = client.get(
        "/api/hcp/validar",
        query_string={
            "codigo": "CONJ-1000",
            "operacion": "030",
            "hcp": "123456",
            "tipo_material": "PIEZA_TERMINADA",
        },
    ).get_json()
    assert hcp["valido"] is True
    hcp_operacion_invalida = client.get(
        "/api/hcp/validar",
        query_string={
            "codigo": "CONJ-1000",
            "operacion": "999",
            "hcp": "123456",
            "tipo_material": "PIEZA_TERMINADA",
        },
    ).get_json()
    assert hcp_operacion_invalida["valido"] is False

    with app.app_context():
        motivo_id = db.session.execute(
            db.text("SELECT id FROM motivos ORDER BY id LIMIT 1")
        ).scalar_one()

    respuesta = client.post(
        "/declaraciones/nueva",
        data={
            "fecha": "2026-07-28",
            "sector_declara": "Producción",
            "celula_detecta": "0001",
            "legajo_declara": "1234",
            "equipo": "A",
            "cliente": "Cliente prueba",
            "lugar_detectado": "Control final",
            "items_json": json.dumps(
                [
                    {
                        "tipo_material": "COMPONENTE",
                        "codigo_padre": "CONJ-1000",
                        "codigo": "CH-1110",
                        "codigo_cliente": "",
                        "material": "CHAPA-2MM",
                        "descripcion": "CHAPA LATERAL IZQUIERDA",
                        "trazabilidad": "123456",
                        "unidad": "PZS",
                        "uso": 1,
                        "cantidad_detectada": 10,
                        "cantidad_scrap_directo": 2,
                        "cantidad_a_retrabajo": 8,
                        "motivo_id": motivo_id,
                        "sector_origen": "Producción",
                        "celula_origen": "Soldadura",
                        "operacion_origen": "30 · SOLDADURA",
                        "legajo_origen": "4321",
                        "tipo_imputacion": "CONFIRMADA",
                        "observacion": "",
                    }
                ]
            ),
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert b"DNC-000001" in respuesta.data
    assert b"123456" in respuesta.data

    with app.app_context():
        item_id = db.session.execute(db.select(DeclaracionItem.id)).scalar_one()

    respuesta = client.post(
        f"/retrabajos/{item_id}/registrar",
        data={
            "fecha": "2026-07-29",
            "operacion": "030 · SOLDADURA",
            "celula": "Retrabajo",
            "legajo": "7777",
            "minutos": "45",
            "cantidad_personas": "2",
            "cantidad_ok": "6",
            "cantidad_scrap": "2",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert b"RETRABAJO CERRADO" in respuesta.data

    with app.app_context():
        declaracion = db.session.execute(db.select(Declaracion)).scalar_one()
        item = db.session.execute(db.select(DeclaracionItem)).scalar_one()
        assert declaracion.estado == "CERRADA"
        assert float(item.cantidad_recuperada) == 6
        assert float(item.cantidad_scrap_total) == 4
        assert item.intervenciones[0].horas_hombre == 1.5
        assert item.intervenciones[0].motivo_scrap_id == item.motivo_id

    historial = client.get("/produccion/retrabajos/historial")
    assert historial.status_code == 200
    historial_html = historial.get_data(as_text=True)
    assert "Trabajos realizados" in historial_html
    assert "030 · SOLDADURA" in historial_html
    assert "CH-1110" in historial_html
    assert "123456" in historial_html
    assert "1.5" in historial_html


def test_rechaza_trazabilidad_invalida():
    app = crear_app_prueba()
    client = app.test_client()
    respuesta = client.post(
        "/declaraciones/nueva",
        data={
            "fecha": "2026-07-28",
            "sector_declara": "Producción",
            "celula_detecta": "1",
            "legajo_declara": "2",
            "equipo": "A",
            "lugar_detectado": "Línea",
            "items_json": json.dumps(
                [
                    {
                        "tipo_material": "COMPONENTE",
                        "codigo": "CH-1110",
                        "trazabilidad": "123",
                        "cantidad_detectada": 1,
                        "cantidad_scrap_directo": 1,
                        "cantidad_a_retrabajo": 0,
                        "motivo_id": 1,
                        "sector_origen": "Producción",
                        "celula_origen": "1",
                        "operacion_origen": "Corte",
                        "tipo_imputacion": "CONFIRMADA",
                    }
                ]
            ),
        },
    )
    assert respuesta.status_code == 400
    assert "exactamente 6 números" in respuesta.get_data(as_text=True)


def test_retrabajo_realizado_en_la_declaracion():
    app = crear_app_prueba()
    client = app.test_client()
    pagina = client.get("/declaraciones/nueva").get_data(as_text=True)
    assert "Origen común" in pagina
    assert "Enviar a retrabajo" in pagina

    respuesta = client.post(
        "/declaraciones/nueva",
        data={
            "fecha": "2026-07-28",
            "sector_declara": "Producción",
            "celula_detecta": "Soldadura",
            "legajo_declara": "1000",
            "equipo": "A",
            "lugar_detectado": "Línea",
            "items_json": json.dumps(
                [
                    {
                        "tipo_material": "PIEZA_TERMINADA",
                        "codigo": "CONJ-1000",
                        "descripcion": "CONJUNTO SOPORTE MOTOR",
                        "trazabilidad": "654321",
                        "unidad": "PZS",
                        "uso": 1,
                        "cantidad_detectada": 10,
                        "cantidad_scrap_directo": 0,
                        "cantidad_a_retrabajo": 10,
                        "motivo_id": 1,
                        "sector_origen": "Producción",
                        "celula_origen": "Soldadura",
                        "operacion_origen": "30 · SOLDADURA",
                        "tipo_imputacion": "CONFIRMADA",
                        "retrabajo_estado": "REALIZADO",
                        "fecha_retrabajo": "2026-07-28",
                        "operacion_retrabajo": "Corrección de soldadura",
                        "celula_retrabajo": "Retrabajo",
                        "legajo_retrabajo": "2000",
                        "minutos_retrabajo": 50,
                        "personas_retrabajo": 2,
                        "cantidad_ok": 8,
                        "cantidad_scrap_retrabajo": 2,
                        "motivo_scrap_retrabajo_id": 1,
                    }
                ]
            ),
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert b"RETRABAJO CERRADO" in respuesta.data
    assert b"50 min" in respuesta.data

    with app.app_context():
        declaracion = db.session.execute(db.select(Declaracion)).scalar_one()
        item = db.session.execute(db.select(DeclaracionItem)).scalar_one()
        assert declaracion.estado == "CERRADA"
        assert float(item.cantidad_recuperada) == 8
        assert float(item.cantidad_scrap_retrabajo) == 2
        assert item.intervenciones[0].horas_hombre == 50 * 2 / 60


def test_produccion_declara_material_de_proveedor():
    app = crear_app_prueba()
    client = app.test_client()
    pagina = client.get("/produccion/nueva/SCRAP").get_data(as_text=True)
    assert "¿Quién encontró el problema?" in pagina
    assert "¿Qué material tiene el problema?" in pagina
    assert "¿A quién corresponde el problema?" in pagina
    assert "de 4" in pagina
    assert pagina.index("Agregá las piezas") < pagina.index("El mismo para todas")
    assert 'id="responsibility-items"' in pagina
    assert "El mismo para todas" in pagina
    assert "Definir pieza por pieza" in pagina
    assert "Buscar proveedor" in pagina
    assert "controlt" not in pagina.lower()

    respuesta = client.post(
        "/produccion/nueva/SCRAP",
        data={
            "fecha": "2026-07-28",
                "sector_declara": "Recepción",
                "celula_detecta": "Recepción",
                "legajo_declara": "5000",
                "turno_id": "1",
                "equipo": "401",
            "lugar_detectado": "Recepción",
            "items_json": json.dumps(
                [
                    {
                        "tipo_material": "MATERIA_PRIMA",
                        "codigo": "MP-PRUEBA",
                        "descripcion": "Material recibido",
                        "trazabilidad": "112233",
                        "unidad": "PZS",
                        "uso": 1,
                        "cantidad_detectada": 5,
                        "cantidad_scrap_directo": 5,
                        "cantidad_a_retrabajo": 0,
                        "motivo_id": 2,
                        "afectado_tipo": "MATERIA_PRIMA",
                        "afectado_codigo": "CHAPA-2MM",
                        "afectado_descripcion": "MP de CH-1110",
                        "afectado_componente_codigo": "CH-1110",
                        "tipo_origen": "PROVEEDOR",
                        "sector_origen": "Proveedor",
                        "celula_origen": "Proveedor de prueba",
                        "operacion_origen": "Material recibido no conforme",
                        "tipo_imputacion": "CONFIRMADA",
                        "proveedor_numero": "1001",
                        "proveedor": "Descripción manipulada",
                        "remito": "R-9988",
                    }
                ]
            ),
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert b"DECLARACI" in respuesta.data
    with app.app_context():
        item = db.session.execute(db.select(DeclaracionItem)).scalar_one()
        assert item.tipo_origen == "PROVEEDOR"
        assert item.proveedor_numero == "1001"
        assert item.proveedor == "Proveedor de prueba"
        assert item.remito == "R-9988"
        assert item.afectado_tipo == "MATERIA_PRIMA"
        assert item.afectado_codigo == "CHAPA-2MM"
    assert client.get("/api/proveedores/1001").get_json() == {
        "descripcion": "Proveedor de prueba",
        "numero": "1001",
        "valido": True,
    }
    assert client.get("/api/proveedores/999999").status_code == 404
    assert client.get("/api/proveedores?q=acero").get_json() == [
        {"descripcion": "Acero Demo S.A.", "numero": "2040"}
    ]


def test_gestion_administra_catalogos_y_configuracion():
    app = crear_app_prueba()
    client = app.test_client()
    respuesta = client.post(
        "/gestion/catalogos/LUGAR",
        data={"codigo": "NUEVO", "nombre": "Lugar nuevo"},
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert "Lugar nuevo" in respuesta.get_data(as_text=True)
    respuesta = client.get("/gestion/configuracion/parametros")
    assert respuesta.status_code == 200
    assert "Prefijo Declaracion" in respuesta.get_data(as_text=True)
    with app.app_context():
        motivo_id = db.session.execute(
            db.text("SELECT id FROM motivos WHERE codigo = 'D1'")
        ).scalar_one()
    respuesta = client.post(
        f"/gestion/motivos/{motivo_id}/accion",
        data={"tipo_accion": "COMPONENTE"},
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert "Pedir componente afectado" in respuesta.get_data(as_text=True)


def test_unidades_de_gestion_no_permiten_repetir_celulas():
    app = crear_app_prueba()
    client = app.test_client()
    pagina = client.get("/gestion/unidades-gestion")
    assert pagina.status_code == 200
    assert "Producción" in pagina.get_data(as_text=True)
    assert "Célula 0001" in pagina.get_data(as_text=True)

    client.post(
        "/gestion/unidades-gestion",
        data={"codigo": "UG-NUEVA", "nombre": "Unidad nueva"},
    )
    with app.app_context():
        unidad = db.session.execute(
            db.select(UnidadGestion).where(UnidadGestion.codigo == "UG-NUEVA")
        ).scalar_one()
        unidad_id = unidad.id
        produccion_id = db.session.execute(
            db.select(UnidadGestion.id).where(UnidadGestion.codigo == "UG-PROD")
        ).scalar_one()

    respuesta = client.post(
        f"/gestion/unidades-gestion/{unidad_id}/celulas",
        data={
            "codigo": "CEL-X",
            "nombre": "Célula exclusiva",
            "codigo_equipos": "EQ-CEL-X",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    respuesta = client.post(
        f"/gestion/unidades-gestion/{produccion_id}/celulas",
        data={
            "codigo": "CEL-Y",
            "nombre": "Célula exclusiva",
            "codigo_equipos": "EQ-CEL-Y",
        },
        follow_redirects=True,
    )
    assert "ya está usado por Célula exclusiva" in respuesta.get_data(as_text=True)
    with app.app_context():
        assert db.session.execute(
            db.select(db.func.count(Celula.id)).where(
                Celula.nombre == "Célula exclusiva"
            )
        ).scalar_one() == 1
        celula_id = db.session.execute(
            db.select(Celula.id).where(Celula.nombre == "Célula exclusiva")
        ).scalar_one()

    respuesta = client.post(
        f"/gestion/unidades-gestion/{unidad_id}/eliminar",
        follow_redirects=True,
    )
    assert "todavía tiene células" in respuesta.get_data(as_text=True)
    client.post(f"/gestion/celulas/{celula_id}/eliminar")
    client.post(f"/gestion/unidades-gestion/{unidad_id}/eliminar")
    with app.app_context():
        assert db.session.get(Celula, celula_id) is None
        assert db.session.get(UnidadGestion, unidad_id) is None


def test_turnos_y_equipos_se_consultan_y_filtran_por_celula():
    app = crear_app_prueba()
    client = app.test_client()
    turnos = client.get("/api/turnos").get_json()
    assert turnos[0] == {"id": 1, "turno": "Mañana"}
    equipos = client.get(
        "/api/equipos?codigo_celula=Célula%200001"
    ).get_json()
    assert {x["equipo"] for x in equipos} == {"101", "102"}
    assert client.get(
        "/api/equipos?codigo_celula=Recepción"
    ).get_json()[0]["equipo"] == "401"

    pagina = client.get("/produccion/alerta").get_data(as_text=True)
    assert 'id="prod-celula"' in pagina
    assert 'id="prod-equipo"' in pagina
    assert "data-searchable required disabled" in pagina
    assert "tablaequipos" not in pagina.lower()
    assert ">Sector<" not in pagina
    assert "Lugar donde se encontró" not in pagina
    assert "searchable-select.js" in pagina
    assert "legajos.js" in pagina
    assert 'data-legajo' in pagina
    assert 'id="review-items-body"' in pagina
    assert "Material informado" in pagina
    assert "OPERACIÓN Y HCP" in pagina
    assert "RESPONSABILIDAD" in pagina
    produccion_js = client.get("/static/js/produccion.js").get_data(as_text=True)
    assert "materiasDisponibles(item)" in produccion_js
    assert "MP disponible" in produccion_js
    assert "autocompletarMateriaPrimaUnica" not in produccion_js
    assert 'min="1" step="1"' in produccion_js
    assert "Number.isInteger(numero(item.cantidad))" in produccion_js

    cantidad_decimal = client.post(
        "/produccion/alerta",
        data={
            "fecha": "2026-07-30",
            "celula_detecta": "Célula 0001",
            "legajo_declara": "100",
            "turno_id": "1",
            "equipo": "101",
            "items_json": json.dumps([{"cantidad_detectada": 1.5}]),
        },
    )
    assert cantidad_decimal.status_code == 400
    assert "número entero" in cantidad_decimal.get_data(as_text=True)

    respuesta = client.post(
        "/produccion/alerta",
        data={
            "fecha": "2026-07-30",
            "sector_declara": "Producción",
            "celula_detecta": "Célula 0001",
            "legajo_declara": "100",
            "turno_id": "1",
            "equipo": "401",
            "lugar_detectado": "Línea / proceso",
            "items_json": json.dumps([{}]),
        },
    )
    assert respuesta.status_code == 400
    assert "no pertenece a Célula 0001" in respuesta.get_data(as_text=True)

    legajo_invalido = client.post(
        "/produccion/alerta",
        data={
            "fecha": "2026-07-30",
            "celula_detecta": "Célula 0001",
            "legajo_declara": "123456",
            "turno_id": "1",
            "equipo": "101",
            "items_json": json.dumps([{}]),
        },
    )
    assert legajo_invalido.status_code == 400
    assert "solamente números y hasta 5 dígitos" in legajo_invalido.get_data(
        as_text=True
    )


def test_produccion_puede_abrir_retrabajo_pendiente():
    app = crear_app_prueba()
    client = app.test_client()
    client.post(
        "/produccion/nueva/RETRABAJO",
        data={
            "fecha": "2026-07-28",
                "sector_declara": "Producción",
                "celula_detecta": "Célula 0001",
                "legajo_declara": "100",
                "turno_id": "1",
                "equipo": "101",
            "lugar_detectado": "Línea / proceso",
            "items_json": json.dumps(
                [{
                    "tipo_material": "PIEZA_TERMINADA", "codigo": "CONJ-1000",
                    "descripcion": "Conjunto", "trazabilidad": "123456",
                    "operacion_codigo": "030",
                    "unidad": "PZS", "uso": 1, "cantidad_detectada": 3,
                    "cantidad_scrap_directo": 0, "cantidad_a_retrabajo": 3,
                    "motivo_id": 1, "tipo_origen": "INTERNO",
                    "sector_origen": "Producción", "celula_origen": "Célula 0001",
                    "operacion_origen": "Misma célula",
                    "tipo_imputacion": "CONFIRMADA", "retrabajo_estado": "PENDIENTE",
                }]
            ),
        },
    )
    with app.app_context():
        item_id = db.session.execute(db.select(DeclaracionItem.id)).scalar_one()
    assert client.get("/produccion/retrabajos").status_code == 200
    pagina = client.get(f"/produccion/retrabajos/{item_id}/registrar")
    assert pagina.status_code == 200
    html = pagina.get_data(as_text=True)
    assert "Completar retrabajo" in html
    assert 'name="celula" data-searchable required' in html
    assert 'name="cantidad_ok" min="0" step="1"' in html
    assert 'name="cantidad_scrap" min="0" step="1"' in html
    assert "Definir el motivo del scrap" not in html
    assert html.count('name="operacion"') == 1
    assert "retrabajo.js" in html
    assert "DATOS DEL PROBLEMA ORIGINAL" in html
    assert "DEFECTO INFORMADO" in html
    assert "INDICACIÓN DE CALIDAD" in html
    assert "123456" in html

    celula_invalida = client.post(
        f"/produccion/retrabajos/{item_id}/registrar",
        data={
            "fecha": "2026-07-30",
            "operacion": "Corrección",
            "celula": "Celula inventada",
            "legajo": "100",
            "minutos": "1",
            "cantidad_personas": "1",
            "cantidad_ok": "3",
            "cantidad_scrap": "0",
        },
    )
    assert celula_invalida.status_code == 400
    assert "célula válida" in celula_invalida.get_data(as_text=True)

    suma_invalida = client.post(
        f"/produccion/retrabajos/{item_id}/registrar",
        data={
            "fecha": "2026-07-30",
            "operacion": "Corrección",
            "celula": "Retrabajo",
            "legajo": "100",
            "minutos": "1",
            "cantidad_personas": "1",
            "cantidad_ok": "2",
            "cantidad_scrap": "0",
        },
    )
    assert suma_invalida.status_code == 400
    assert "debe ser igual" in suma_invalida.get_data(as_text=True)

    decimal_invalido = client.post(
        f"/produccion/retrabajos/{item_id}/registrar",
        data={
            "fecha": "2026-07-30",
            "operacion": "Corrección",
            "celula": "Retrabajo",
            "legajo": "100",
            "minutos": "1",
            "cantidad_personas": "1",
            "cantidad_ok": "2.5",
            "cantidad_scrap": "0.5",
        },
    )
    assert decimal_invalido.status_code == 400
    assert "número entero" in decimal_invalido.get_data(as_text=True)

    sin_observaciones = client.post(
        f"/produccion/retrabajos/{item_id}/registrar",
        data={
            "fecha": "2026-07-30",
            "operacion": "",
            "celula": "Retrabajo",
            "legajo": "100",
            "minutos": "1",
            "cantidad_personas": "1",
            "cantidad_ok": "3",
            "cantidad_scrap": "0",
        },
    )
    assert sin_observaciones.status_code == 400
    assert "trabajo efectuado" in sin_observaciones.get_data(as_text=True)

    trabajo_libre = client.post(
        f"/produccion/retrabajos/{item_id}/registrar",
        data={
            "fecha": "2026-07-30",
            "operacion": "Se repasó el agujero y quedó dentro de medida",
            "celula": "Retrabajo",
            "legajo": "100",
            "minutos": "1",
            "cantidad_personas": "1",
            "cantidad_ok": "3",
            "cantidad_scrap": "0",
        },
        follow_redirects=True,
    )
    assert trabajo_libre.status_code == 200


def test_misma_pieza_admite_causas_y_responsables_por_renglon():
    app = crear_app_prueba()
    client = app.test_client()
    with app.app_context():
        motivos = {
            codigo: motivo_id
            for motivo_id, codigo in db.session.execute(
                db.text("SELECT id, codigo FROM motivos WHERE codigo IN ('D2', 'D11')")
            )
        }

    base = {
        "tipo_material": "PIEZA_TERMINADA",
        "codigo_padre": "CONJ-1000",
        "codigo": "CONJ-1000",
        "descripcion": "CONJUNTO SOPORTE MOTOR",
        "trazabilidad": "778899",
        "operacion_codigo": "030",
        "unidad": "PZS",
        "uso": 1,
        "cantidad_detectada": 2,
        "cantidad_scrap_directo": 2,
        "cantidad_a_retrabajo": 0,
    }
    items = [
        {
            **base,
            "motivo_id": motivos["D11"],
            "afectado_tipo": "COMPONENTE",
            "afectado_codigo": "CH-1110",
            "afectado_descripcion": "CHAPA LATERAL IZQUIERDA",
            "afectado_componente_codigo": "CH-1110",
            "tipo_origen": "INTERNO",
            "sector_origen": "Producción",
            "celula_origen": "Soldadura",
            "operacion_origen": "30 · SOLDADURA",
            "legajo_origen": "111",
            "tipo_imputacion": "CONFIRMADA",
        },
        {
            **base,
            "motivo_id": motivos["D2"],
            "afectado_tipo": "MATERIA_PRIMA",
            "afectado_codigo": "CHAPA-2MM",
            "afectado_descripcion": "MP de CH-1120",
            "afectado_componente_codigo": "CH-1120",
            "tipo_origen": "DESCONOCIDO",
            "sector_origen": "No determinado",
            "celula_origen": "No determinada",
            "operacion_origen": "No determinada",
            "tipo_imputacion": "NO_DETERMINADA",
        },
    ]
    respuesta = client.post(
        "/produccion/nueva/SCRAP",
        data={
            "fecha": "2026-07-29",
                "sector_declara": "Producción",
                "celula_detecta": "Célula 0001",
                "legajo_declara": "500",
                "turno_id": "1",
                "equipo": "101",
            "lugar_detectado": "Línea / proceso",
            "items_json": json.dumps(items),
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    with app.app_context():
        guardados = db.session.execute(
            db.select(DeclaracionItem).order_by(DeclaracionItem.id)
        ).scalars().all()
        assert len(guardados) == 2
        assert guardados[0].codigo_pieza == guardados[1].codigo_pieza
        assert guardados[0].afectado_codigo == "CH-1110"
        assert guardados[0].celula_origen == "Soldadura"
        assert guardados[1].afectado_codigo == "CHAPA-2MM"
        assert guardados[1].tipo_imputacion == "NO_DETERMINADA"


def test_produccion_exige_dato_adicional_segun_motivo():
    app = crear_app_prueba()
    client = app.test_client()
    with app.app_context():
        motivo_d11 = db.session.execute(
            db.text("SELECT id FROM motivos WHERE codigo = 'D11'")
        ).scalar_one()
    respuesta = client.post(
        "/produccion/nueva/SCRAP",
        data={
            "fecha": "2026-07-29",
                "sector_declara": "Producción",
                "celula_detecta": "Célula 0001",
                "legajo_declara": "500",
                "turno_id": "1",
                "equipo": "101",
            "lugar_detectado": "Línea / proceso",
            "items_json": json.dumps([{
                "tipo_material": "PIEZA_TERMINADA",
                "codigo": "CONJ-1000",
                "trazabilidad": "123456",
                "operacion_codigo": "030",
                "unidad": "PZS",
                "uso": 1,
                "cantidad_detectada": 1,
                "cantidad_scrap_directo": 1,
                "cantidad_a_retrabajo": 0,
                "motivo_id": motivo_d11,
                "tipo_origen": "DESCONOCIDO",
                "sector_origen": "No determinado",
                "celula_origen": "No determinada",
                "operacion_origen": "No determinada",
                "tipo_imputacion": "NO_DETERMINADA",
            }]),
        },
    )
    assert respuesta.status_code == 400
    assert "Elegí el componente afectado" in respuesta.get_data(as_text=True)


def test_alerta_pasa_a_calidad_y_calidad_divide_disposicion():
    app = crear_app_prueba()
    client = app.test_client()
    with app.app_context():
        motivo_preliminar = db.session.execute(
            db.text("SELECT id FROM motivos WHERE codigo = 'D3'")
        ).scalar_one()
        motivo_detallado = db.session.execute(
            db.text("SELECT id FROM motivos WHERE codigo = 'D3-POR'")
        ).scalar_one()
    respuesta = client.post(
        "/produccion/alerta",
        data={
            "fecha": "2026-07-29",
            "celula_detecta": "Célula 0001",
                "legajo_declara": "123",
                "turno_id": "1",
                "equipo": "101",
            "items_json": json.dumps([{
                "tipo_material": "PIEZA_TERMINADA",
                "codigo": "CONJ-1000",
                "descripcion": "Conjunto",
                "trazabilidad": "123456",
                "operacion_codigo": "030",
                "unidad": "PZS",
                "uso": 1,
                "cantidad_detectada": 10,
                "cantidad_scrap_directo": 0,
                "cantidad_a_retrabajo": 0,
                "observacion": "Componente con rajaduras informado por Producción",
                "motivo_id": motivo_preliminar,
                "tipo_origen": "DESCONOCIDO",
                "sector_origen": "No determinado",
                "celula_origen": "No determinada",
                "operacion_origen": "No determinada",
                "tipo_imputacion": "NO_DETERMINADA",
            }]),
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert "ALERTA ENVIADA A CALIDAD" in respuesta.get_data(as_text=True)
    with app.app_context():
        declaracion = db.session.execute(db.select(Declaracion)).scalar_one()
        item = db.session.execute(db.select(DeclaracionItem)).scalar_one()
        assert declaracion.estado == "PENDIENTE_CALIDAD"
        assert declaracion.sector_declara == "Producción"
        assert declaracion.lugar_detectado == "Célula 0001"
        assert declaracion.unidad_gestion == "Producción"
        assert declaracion.celula_codigo_equipos == "Célula 0001"
        assert declaracion.turno_id == 1
        assert declaracion.turno == "Mañana"
        assert declaracion.equipo == "101"
        assert declaracion.equipo_descripcion == "Línea principal"
        assert item.observacion == "Componente con rajaduras informado por Producción"
        declaracion_id = declaracion.id
        declaracion_numero = declaracion.numero
        item_id = item.id

    bandeja = client.get("/calidad")
    assert bandeja.status_code == 200
    assert "Actualización automática" in bandeja.get_data(as_text=True)
    assert "calidad-bandeja.js" in bandeja.get_data(as_text=True)
    assert "CONJ-1000" not in bandeja.get_data(as_text=True)
    contenido = client.get("/calidad/bandeja/contenido")
    assert contenido.status_code == 200
    assert contenido.headers["Cache-Control"] == "no-store"
    assert 'data-alert-count="1"' in contenido.get_data(as_text=True)
    assert declaracion_numero in contenido.get_data(as_text=True)
    detalle_calidad = client.get(f"/calidad/{declaracion_id}/validar")
    detalle_html = detalle_calidad.get_data(as_text=True)
    assert detalle_calidad.status_code == 200
    assert "HCP" in detalle_html
    assert "Indicación de Calidad" in detalle_html
    assert "Obligatoria" in detalle_html
    assert "retrabajar agujero a Ø10 mm" in detalle_html
    assert "Componente con rajaduras informado por Producción" in detalle_html
    assert "INFORMADO POR PRODUCCIÓN" in detalle_html
    assert "Modificar motivo" in detalle_html
    assert "Aplicar corrección" in detalle_html
    assert 'data-quality-cause-editor' in detalle_html
    assert 'data-quality-row-details' in detalle_html
    assert "Ver detalle" in detalle_html
    assert 'data-row-destination>Todo scrap' in detalle_html
    assert detalle_html.index("data-quality-item-comment") < detalle_html.index(
        "data-quality-row-details"
    )
    scrap_input = detalle_html.index(f'name="scrap_{item_id}"')
    assert 'value="10"' in detalle_html[scrap_input:scrap_input + 180]
    liberar_input = detalle_html.index(f'name="liberada_{item_id}"')
    assert 'value="0"' in detalle_html[liberar_input:liberar_input + 180]
    assert f'name="hcp_{item_id}"' not in detalle_html
    assert f'name="operacion_codigo_{item_id}"' not in detalle_html

    legajo_calidad_invalido = client.post(
        f"/calidad/{declaracion_id}/validar",
        data={
            "legajo_calidad": "A900",
            f"grupo_{item_id}": motivo_preliminar,
            f"motivo_{item_id}": motivo_preliminar,
            f"scrap_{item_id}": "2",
            f"retrabajo_{item_id}": "8",
            f"liberada_{item_id}": "0",
            f"obs_item_{item_id}": "Retrabajar soldadura y descartar dos piezas",
            f"resp_estado_{item_id}": "PENDIENTE",
        },
        follow_redirects=True,
    )
    assert "legajo de Calidad debe contener solamente números" in (
        legajo_calidad_invalido.get_data(as_text=True)
    )

    respuesta = client.post(
        f"/calidad/{declaracion_id}/validar",
        data={
            "legajo_calidad": "900",
            f"hcp_{item_id}": "654321",
            f"operacion_codigo_{item_id}": "999",
            f"motivo_{item_id}": motivo_detallado,
            f"scrap_{item_id}": "2",
            f"retrabajo_{item_id}": "8",
            f"liberada_{item_id}": "0",
            f"obs_item_{item_id}": "Componente con rajaduras",
            "observaciones_calidad": "Poros confirmados",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    respuesta_html = respuesta.get_data(as_text=True)
    assert "window.open(" in respuesta_html
    assert f"/calidad/declaraciones/{declaracion_id}?imprimir=1" in respuesta_html
    impresion_calidad = client.get(
        f"/calidad/declaraciones/{declaracion_id}?imprimir=1"
    )
    impresion_calidad_html = impresion_calidad.get_data(as_text=True)
    assert "VALIDADO POR CALIDAD" in impresion_calidad_html
    assert "Componente con rajaduras" in impresion_calidad_html
    with app.app_context():
        declaracion = db.session.get(Declaracion, declaracion_id)
        item = db.session.get(DeclaracionItem, item_id)
        assert declaracion.estado == "PENDIENTE_RETRABAJO"
        assert declaracion.legajo_calidad == "900"
        assert float(item.cantidad_scrap_directo) == 2
        assert float(item.cantidad_a_retrabajo) == 8
        assert item.motivo.codigo == "D3-POR"
        assert item.trazabilidad == "123456"
        assert item.operacion_codigo == "030"
        assert item.observacion == "Componente con rajaduras informado por Producción"
        assert item.observacion_calidad == "Componente con rajaduras"


def test_calidad_resuelve_material_y_puede_investigar_responsabilidad_despues():
    app = crear_app_prueba()
    client = app.test_client()
    with app.app_context():
        motivo, grupo_id = db.session.execute(
            db.text(
                "SELECT id, grupo_id FROM motivos WHERE codigo = 'D3-POR'"
            )
        ).one()

    client.post(
        "/produccion/alerta",
        data={
            "fecha": "2026-07-29",
                "sector_declara": "Producción",
                "celula_detecta": "Célula 0001",
                "legajo_declara": "123",
                "turno_id": "1",
                "equipo": "101",
            "lugar_detectado": "Línea / proceso",
            "items_json": json.dumps([{
                "tipo_material": "PIEZA_TERMINADA",
                "codigo": "CONJ-1000",
                "descripcion": "Conjunto",
                "trazabilidad": "123456",
                "operacion_codigo": "030",
                "unidad": "PZS",
                "uso": 1,
                "cantidad_detectada": 4,
                "cantidad_scrap_directo": 0,
                "cantidad_a_retrabajo": 0,
                "grupo_id": grupo_id,
                "motivo_id": motivo,
                "tipo_origen": "INTERNO",
                "sector_origen": "Producción",
                "celula_origen": "Soldadura",
                "operacion_origen": "30 · SOLDADURA",
                "tipo_imputacion": "PRESUNTA",
            }]),
        },
    )
    with app.app_context():
        declaracion = db.session.execute(db.select(Declaracion)).scalar_one()
        item = db.session.execute(db.select(DeclaracionItem)).scalar_one()
        declaracion_id, item_id = declaracion.id, item.id
        assert item.responsabilidad_estado == "PENDIENTE"

    pagina_calidad = client.get(f"/calidad/{declaracion_id}/validar")
    assert pagina_calidad.status_code == 200
    assert "Confirmar defecto" in pagina_calidad.get_data(as_text=True)
    assert "Investigar después" in pagina_calidad.get_data(as_text=True)

    sin_comentario = client.post(
        f"/calidad/{declaracion_id}/validar",
        data={
            "legajo_calidad": "900",
            f"grupo_{item_id}": grupo_id,
            f"motivo_{item_id}": motivo,
            f"scrap_{item_id}": "0",
            f"retrabajo_{item_id}": "4",
            f"liberada_{item_id}": "0",
            f"resp_estado_{item_id}": "PENDIENTE",
        },
        follow_redirects=True,
    )
    assert "Escribí la indicación de Calidad" in sin_comentario.get_data(as_text=True)

    respuesta = client.post(
        f"/calidad/{declaracion_id}/validar",
        data={
            "legajo_calidad": "900",
            f"grupo_{item_id}": grupo_id,
            f"motivo_{item_id}": motivo,
            f"scrap_{item_id}": "4",
            f"retrabajo_{item_id}": "0",
            f"liberada_{item_id}": "0",
            f"resp_estado_{item_id}": "PENDIENTE",
            f"obs_item_{item_id}": "Oxidación confirmada; material no recuperable",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert "Investigaciones pendientes" in respuesta.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Declaracion, declaracion_id).estado == "PENDIENTE_INVESTIGACION"

    respuesta = client.post(
        f"/calidad/{declaracion_id}/validar",
        data={
            "legajo_calidad": "901",
            f"grupo_{item_id}": grupo_id,
            f"motivo_{item_id}": motivo,
            f"scrap_{item_id}": "4",
            f"retrabajo_{item_id}": "0",
            f"liberada_{item_id}": "0",
            f"resp_estado_{item_id}": "CONFIRMADA",
            f"resp_tipo_{item_id}": "PROVEEDOR",
            f"resp_proveedor_numero_{item_id}": "2040",
            f"obs_item_{item_id}": "Oxidación confirmada; material no recuperable",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    with app.app_context():
        declaracion = db.session.get(Declaracion, declaracion_id)
        item = db.session.get(DeclaracionItem, item_id)
        assert declaracion.estado == "CERRADA"
        assert item.responsabilidad_estado == "CONFIRMADA"
        assert item.responsable_proveedor_numero == "2040"
        assert item.responsable_proveedor == "Acero Demo S.A."
