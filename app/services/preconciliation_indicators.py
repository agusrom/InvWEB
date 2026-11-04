"""Indicadores comparables para los análisis de stock guardados o en curso."""

from __future__ import annotations

from typing import Any


def _porcentaje(buenas: int, total: int) -> float | None:
    return round(buenas * 100 / total, 1) if total else None


def _metrica(buenas: int, total: int) -> dict:
    return {
        "buenas": buenas,
        "malas": max(total - buenas, 0),
        "total": total,
        "porcentaje": _porcentaje(buenas, total),
    }


def calcular_indicadores_preconciliacion(
    calculation: dict,
    notes: dict[str, dict] | None = None,
) -> dict:
    """Calcula calidad, documentación y avance sin modificar el análisis."""
    notes = notes or {}
    scenarios = [
        scenario for scenario in calculation.get("escenarios", [])
        if not scenario.get("error")
    ]
    rows_by_code: dict[str, list[dict]] = {}
    for scenario in scenarios:
        for row in scenario.get("filas", []):
            rows_by_code.setdefault(str(row.get("codigo", "")), []).append(row)

    total = len(rows_by_code)
    expected_scenarios = len(scenarios)
    system_good = sum(
        1 for rows in rows_by_code.values()
        if rows and bool(rows[0].get("sistema_ok"))
    )
    reconciliation_good = sum(
        1 for rows in rows_by_code.values()
        if len(rows) == expected_scenarios
        and rows
        and all(bool(row.get("conciliacion_ok")) for row in rows)
    )
    integral_good = sum(
        1 for rows in rows_by_code.values()
        if len(rows) == expected_scenarios
        and rows
        and bool(rows[0].get("sistema_ok"))
        and all(bool(row.get("conciliacion_ok")) for row in rows)
    )

    scenario_metrics = []
    for scenario in scenarios:
        rows = scenario.get("filas", [])
        good = sum(1 for row in rows if bool(row.get("conciliacion_ok")))
        scenario_metrics.append({
            "id": scenario.get("inicial", {}).get("id"),
            "codigo": scenario.get("inicial", {}).get("codigo", ""),
            "fecha": scenario.get("inicial", {}).get("fecha", ""),
            **_metrica(good, len(rows)),
        })
    worst = min(
        scenario_metrics,
        key=lambda item: item["porcentaje"] if item["porcentaje"] is not None else 101,
        default=None,
    )

    movements = [
        item for item in calculation.get("movimientos", [])
        if item.get("escenarios")
    ]
    verified = sum(1 for item in movements if bool(item.get("verificado")))

    review_codes = {
        code for code, rows in rows_by_code.items()
        if not (
            len(rows) == expected_scenarios
            and rows
            and bool(rows[0].get("sistema_ok"))
            and all(bool(row.get("conciliacion_ok")) for row in rows)
        )
    }
    causes = sum(
        1 for code in review_codes
        if str(notes.get(code, {}).get("causa", "")).strip()
    )
    managed = sum(
        1 for code in review_codes
        if str(notes.get(code, {}).get("estado", "PENDIENTE")) != "PENDIENTE"
    )
    resolved = sum(
        1 for code in review_codes
        if str(notes.get(code, {}).get("estado", "")) == "RESUELTO"
    )

    system_bad_codes = {
        code for code, rows in rows_by_code.items()
        if rows and not bool(rows[0].get("sistema_ok"))
    }
    system_differences_with_adjustments = sum(
        1 for code in system_bad_codes
        if any(bool(row.get("ajustes_sistema")) for row in rows_by_code[code])
    )

    return {
        "tolerancia": calculation.get("tolerancia", 5),
        "total_piezas": total,
        "sistema": _metrica(system_good, total),
        "conciliacion_integral": _metrica(reconciliation_good, total),
        "consistencia_integral": _metrica(integral_good, total),
        "peor_escenario": worst,
        "escenarios": scenario_metrics,
        "auditoria_documental": _metrica(verified, len(movements)),
        "cobertura_causas": _metrica(causes, len(review_codes)),
        "avance_analisis": _metrica(managed, len(review_codes)),
        "resolucion": _metrica(resolved, len(review_codes)),
        "diferencias_con_ajustes": _metrica(
            system_differences_with_adjustments,
            len(system_bad_codes),
        ),
    }
