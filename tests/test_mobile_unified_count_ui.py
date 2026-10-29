from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "app/templates/mobile_count.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "app/static/js/mobile_count.js").read_text(encoding="utf-8")
STYLES = (ROOT / "app/static/css/mobile_count.css").read_text(encoding="utf-8")
API = (ROOT / "app/routers/api.py").read_text(encoding="utf-8")
DESKTOP_TEMPLATE = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
DESKTOP_SCRIPT = (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")


def test_mobile_count_exposes_one_counting_surface():
    assert "count-mode-tabs" not in TEMPLATE
    assert "Conteo rápido" in TEMPLATE
    assert "El orden no cambia" in TEMPLATE


def test_mobile_route_keeps_physical_location_and_optional_note():
    assert "Ubicación y etapa de la próxima carga" in TEMPLATE
    assert '[${mobileState.routeContext.physical}]' in SCRIPT
    assert "data-route-note" in SCRIPT
    assert "observationDisplay" in SCRIPT


def test_mobile_route_has_inline_history_and_structure_roles():
    assert "route-detail-summary" in SCRIPT
    assert "Registros cargados" in SCRIPT
    assert "data-delete-box" in SCRIPT
    for role in ("role-padre", "role-subconjunto", "role-hijo", "role-material"):
        assert role in STYLES
    assert "obtener_cajas_item_movil" in API


def test_mobile_order_and_cache_are_stable():
    assert "itemOrderKey" in SCRIPT
    assert "stableItemOrderMap" in SCRIPT
    assert "if (cached)" in SCRIPT
    assert "await loadInventory();\n    } catch" not in SCRIPT


def test_mobile_can_delete_a_complete_batch():
    assert "data-route-delete-selected" in SCRIPT
    assert "selectSameRouteBatch" in SCRIPT
    assert 'kind: "DELETE_BATCH"' in SCRIPT
    assert "eliminar_cajas_movil" in API


def test_desktop_can_explain_the_accumulated_count():
    assert 'id="modal-detalle-registros"' in DESKTOP_TEMPLATE
    assert "data-count-records" in DESKTOP_SCRIPT
    assert "abrirDetalleRegistrosConteo" in DESKTOP_SCRIPT
    assert "Base / edición PC" in DESKTOP_SCRIPT


def test_piece_count_cards_do_not_overlap_the_material_column():
    assert 'data-count-records="${linea.id}">Registros</button>' in DESKTOP_SCRIPT
    assert ".piece-count-table th:nth-child(2) { width: 13%; }" in (
        ROOT / "app/static/css/styles.css"
    ).read_text(encoding="utf-8")
    assert "grid-template-columns: 76px;" in (
        ROOT / "app/static/css/styles.css"
    ).read_text(encoding="utf-8")


def test_piece_count_card_titles_are_short_and_stay_on_one_line():
    styles = (ROOT / "app/static/css/styles.css").read_text(encoding="utf-8")
    assert "function tituloEtapaConteoCorto(linea)" in DESKTOP_SCRIPT
    assert 'return "MP";' in DESKTOP_SCRIPT
    assert 'return "PT";' in DESKTOP_SCRIPT
    assert '`Proceso ${linea.operacion}`' in DESKTOP_SCRIPT
    assert ".stage-line > div:first-child > small" in styles
    assert "white-space: nowrap;" in styles
    assert "grid-template-columns: minmax(0,1fr) auto auto;" in styles


def test_piece_group_total_includes_material_process_and_finished_stock():
    assert 'const material = grupo.items.filter((item) => item.etapa === "MATERIAL");' in DESKTOP_SCRIPT
    assert "const comparables = [...material, ...proceso, ...terminadas];" in DESKTOP_SCRIPT
    assert "const comparables = inputs;" in DESKTOP_SCRIPT
    assert "Total general correcto" in DESKTOP_SCRIPT
    assert "<th>Total general</th>" in DESKTOP_TEMPLATE
