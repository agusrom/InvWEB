from io import BytesIO
import unittest

from openpyxl import Workbook

from app.services.stock_excel import leer_reporte_stock


def workbook_bytes(rows):
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


class StockExcelLotTests(unittest.TestCase):
    def test_mp_report_is_grouped_by_material_and_lot(self):
        report = leer_reporte_stock(workbook_bytes([
            ["lote", "cmat", "descr", "undad", "cant"],
            [123, "MP-01", "Acero laminado", "KG", 10],
            [123, "MP-01", "Acero laminado", "KG", 2.5],
            [124, "MP-01", "Acero laminado", "KG", 7],
        ]), "MP")

        self.assertEqual(set(report.mp["MP-01"]), {"00123", "00124"})
        self.assertEqual(report.mp["MP-01"]["00123"].cantidad, 12.5)
        self.assertEqual(report.mp["MP-01"]["00123"].descripcion, "Acero laminado")
        self.assertEqual(report.mp["MP-01"]["00123"].unidad, "KG")

    def test_mp_report_rejects_missing_or_invalid_lot(self):
        content = workbook_bytes([
            ["lote", "cmat", "descr", "undad", "cant"],
            ["ABC", "MP-01", "Acero", "KG", 10],
        ])
        with self.assertRaisesRegex(ValueError, "Lote inválido"):
            leer_reporte_stock(content, "MP")


if __name__ == "__main__":
    unittest.main()
