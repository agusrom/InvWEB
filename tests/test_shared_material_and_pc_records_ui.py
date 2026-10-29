from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SharedMaterialAndPcRecordsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desktop = (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")
        cls.mobile = (ROOT / "app/static/js/mobile_count.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "app/static/css/styles.css").read_text(encoding="utf-8")
        cls.template = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
        cls.api = (ROOT / "app/routers/api.py").read_text(encoding="utf-8")

    def test_shared_material_is_grouped_and_not_duplicated(self):
        self.assertIn("es_material_compartido: true", self.desktop)
        self.assertIn("MP compartida", self.desktop)
        self.assertIn("actualizar_filas_material_compartido", self.api)
        self.assertIn("lotes_asignados", self.api)
        self.assertIn("item.stock_sistema = 0", self.api)
        self.assertIn('class="shared-material-cell"', self.desktop)
        self.assertIn('rowspan="${piezas.length}"', self.desktop)
        self.assertIn("data-piece-member", self.desktop)
        self.assertIn("shared-result-content", self.desktop)
        self.assertIn(".productive-total.shared-result-cell", self.styles)
        self.assertIn("display: table-cell !important", self.styles)

    def test_material_lots_are_hidden_behind_records(self):
        self.assertIn("function celdaMaterialResumen", self.desktop)
        self.assertIn("data-count-material", self.desktop)
        self.assertIn("function abrirDetalleLotesMaterial", self.desktop)
        self.assertIn("material-lot-card", self.desktop)

    def test_mobile_has_the_same_shared_material_group(self):
        self.assertIn('key: `shared:${materialCode}', self.mobile)
        self.assertIn('COMPARTIDA: "MP compartida"', self.mobile)
        self.assertIn("shared-mobile-codes", self.mobile)
        self.assertIn("function routeMaterialGroups", self.mobile)
        self.assertIn("function routeMaterialSummaryCardHtml", self.mobile)
        self.assertIn("data-route-toggle-material", self.mobile)

    def test_pc_records_form_uses_the_mobile_records_endpoint(self):
        self.assertIn('id="form-count-records-add"', self.template)
        self.assertIn('id="count-record-quantity"', self.template)
        self.assertIn('id="count-record-count"', self.template)
        self.assertIn("async function agregarRegistrosDesdePC", self.desktop)
        self.assertIn("conteo-movil/cajas`,", self.desktop)
        self.assertIn('dispositivo: "PC"', self.desktop)

    def test_pc_can_delete_individual_records(self):
        self.assertIn("data-delete-count-record", self.desktop)
        self.assertIn("async function eliminarRegistroConteoDesdePC", self.desktop)
        self.assertIn("conteo-movil/cajas/${cajaId}", self.desktop)
        self.assertIn('{ method: "DELETE" }', self.desktop)
        self.assertIn('"inventario": inventario_dict', self.api)

    def test_pc_can_confirm_zero_for_any_material_lot_without_records(self):
        self.assertIn('id="btn-confirm-count-zero"', self.template)
        self.assertIn("async function confirmarConteoCeroDesdePC", self.desktop)
        self.assertIn('item.etapa === "MATERIAL"', self.desktop)
        zero_condition = self.desktop[self.desktop.index("const puedeConfirmarCero"):]
        zero_condition = zero_condition[:zero_condition.index("const botonCero")]
        self.assertNotIn("!item.lote", zero_condition)
        self.assertNotIn("item.stock_sistema", zero_condition)
        self.assertIn("detalle.cajas.length === 0", zero_condition)
        self.assertIn("conteo.conteo_fisico = 0", self.desktop)

    def test_without_lot_is_not_counted_as_a_real_lot(self):
        self.assertIn("function cantidadLotesMaterial(lineas)", self.desktop)
        self.assertIn('String(linea.lote || "").trim() !== ""', self.desktop)
        self.assertIn("${cantidadLotesMaterial(lineas)}", self.desktop)
        self.assertNotIn("${gruposLote.length}", self.desktop)


if __name__ == "__main__":
    unittest.main()
