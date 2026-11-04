from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UnifiedPreconciliationUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (ROOT / "app/templates/preconciliation.html").read_text(encoding="utf-8")
        cls.script = (ROOT / "app/static/js/preconciliation.js").read_text(encoding="utf-8")

    def test_global_remittance_registers_are_on_the_analysis_screen(self):
        self.assertIn('id="income-register"', self.template)
        self.assertIn('id="outcome-register"', self.template)
        self.assertIn('id="manual-form"', self.template)
        self.assertNotIn('id="audit-tabs"', self.template)

    def test_piece_rows_include_inline_reconciliation_details(self):
        self.assertIn('class="piece-reconciliation"', self.script)
        self.assertIn('data-scenario-detail=', self.script)
        self.assertIn('movementListHtml("Ingresos considerados"', self.script)
        self.assertIn('movementListHtml("Egresos considerados"', self.script)
        self.assertNotIn('row.scenarios.map(scenarioSummaryHtml)', self.script)
        self.assertNotIn('class="calculation-formula"', self.script)

    def test_saved_analyses_have_a_searchable_separate_home(self):
        self.assertIn('id="analysis-home"', self.template)
        self.assertIn('id="saved-analysis-search"', self.template)
        self.assertIn('id="new-analysis"', self.template)
        self.assertIn('id="analysis-workspace"', self.template)
        self.assertIn('Abrir / editar', self.script)
        self.assertIn('data-delete-analysis=', self.script)

    def test_piece_analysis_uses_horizontal_space_and_highlights_reconciliation(self):
        self.assertIn('class="piece-inline-controls"', self.script)
        self.assertIn('class="inline-observation"', self.script)
        self.assertIn('reconciliation-difference', self.script)
        self.assertNotIn('class="piece-analysis"', self.script)

    def test_manual_movements_search_pieces_and_materials_while_typing(self):
        self.assertIn('id="manual-code-input"', self.template)
        self.assertIn('/api/busqueda/piezas?', self.script)
        self.assertIn('/api/busqueda/materiales?', self.script)
        self.assertIn('scheduleManualCodeSearch', self.script)

    def test_movements_are_grouped_by_remittance_number(self):
        self.assertIn('movement.remito || "SIN REMITO"', self.script)
        self.assertIn('class="remittance-group"', self.script)

    def test_whole_remittance_has_one_save_and_conditional_recalculation(self):
        self.assertIn('data-save-remittance', self.script)
        self.assertIn('data-verify-all', self.script)
        self.assertIn('Guardar remito y recalcular', self.script)
        self.assertIn('sólo cambió la auditoría', self.script)
        self.assertIn('group.rows.some', self.script)
        self.assertIn('recalcular: draft.requiresRecalculation', self.script)
        self.assertNotIn('data-save-movement', self.script)

    def test_triangular_diagnosis_and_system_adjustments_are_visible(self):
        self.assertNotIn('Sistema vs. esperado', self.script)
        self.assertIn('Ajustes del sistema · produc16', self.script)
        self.assertNotIn('Prioridad de reconteo', self.template)
        self.assertIn('Confianza ${row.diagnosis.confidence}', self.script)
        self.assertIn('id="evidence-filter"', self.template)
        self.assertIn('class="validation-checklist"', self.script)
        self.assertIn('Esperado explotado', self.script)
        self.assertIn('Conteo actual explotado', self.script)
        self.assertIn('no forman parte de la fórmula explotada', self.script)

    def test_analysis_opens_with_one_compact_reconciliation_summary(self):
        self.assertIn('data-analysis-view="SUMMARY"', self.template)
        self.assertIn('data-analysis-view="DETAIL"', self.template)
        self.assertIn('data-analysis-view="REMITTANCES"', self.template)
        self.assertIn('id="summary-reliability"', self.template)
        self.assertIn('id="summary-scenario"', self.template)
        self.assertNotIn('id="analysis-indicators"', self.template)
        self.assertNotIn('id="scenario-indicators"', self.template)
        self.assertIn('good * 100 / rows.length', self.script)
        self.assertIn('CONFIABILIDAD DE LA CONCILIACIÓN', self.script)
        self.assertIn('state.activeView = "SUMMARY"', self.script)

    def test_compact_summary_lists_reconciliation_numbers_and_saved_analysis(self):
        self.assertIn('id="summary-table"', self.template)
        self.assertIn('<th>Inicial</th><th>Ingresos</th><th>Egresos</th>', self.script)
        self.assertIn('<th>Esperado</th><th>Conteo actual</th>', self.script)
        self.assertIn('<th>Análisis realizado</th>', self.script)
        self.assertIn('data-open-piece=', self.script)
        self.assertIn('openPieceFromSummary', self.script)

    def test_shared_material_pieces_are_presented_as_one_group(self):
        self.assertIn("row.es_grupo_mp", self.script)
        self.assertIn("MP ${escapeHtml(item.codigo_material)} compartida", self.script)
        self.assertIn('class="shared-piece-codes"', self.script)
        self.assertIn("row.codigos.map", self.script)
        self.assertIn("Resumen por pieza y MP compartida", self.template)
        self.assertIn("function sharedSystemComparisonsHtml", self.script)
        self.assertIn("Control directo por pieza", self.script)
        self.assertIn("Ajustes de esta pieza", self.script)
        self.assertIn("function systemHistoryForCode", self.script)


if __name__ == "__main__":
    unittest.main()
