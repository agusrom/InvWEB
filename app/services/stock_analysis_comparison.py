"""Períodos consecutivos derivados de acumulados con la misma auditoría."""
from copy import deepcopy
from datetime import datetime, timezone


def _restar_detalles(anteriores, posteriores, campo):
    """Diferencia por origen; nunca duplica un remito compartido entre acumulados."""
    def index(rows):
        result = {}
        for row in rows:
            key = row.get('clave') or repr((row.get('remito'), row.get('fecha'), row.get('codigo_material'), row.get('pieza_origen')))
            if key not in result:
                result[key] = [deepcopy(row), 0.0]
            result[key][1] += float(row.get(campo, 0) or 0)
        return result
    left, right = index(anteriores), index(posteriores)
    result, valid = [], True
    for key in left.keys() | right.keys():
        quantity = left.get(key, [None, 0])[1] - right.get(key, [None, 0])[1]
        if quantity < -1e-8:
            valid = False
        if abs(quantity) <= 1e-8:
            continue
        detail = deepcopy((left.get(key) or right[key])[0])
        detail[campo] = quantity
        if campo == 'cantidad_equivalente':
            use = float(detail.get('uso', 1) or 1)
            detail['cantidad_pieza'] = quantity / use
        result.append(detail)
    return sorted(result, key=lambda d: (str(d.get('fecha', '')), str(d.get('remito', '')))), valid


def construir_periodos_consecutivos(escenarios, final, tolerancia, dentro):
    ordered = sorted(escenarios, key=lambda s: (s['inicial']['fecha'], s['inicial']['id']))
    periods = []
    for index, start in enumerate(ordered):
        end = ordered[index + 1] if index + 1 < len(ordered) else None
        end_info = end['inicial'] if end else final
        period = dict(inicial=start['inicial'], final=end_info, filas=[], advertencias=[],
                      clave=f"{start['inicial']['id']}:{end_info['id']}")
        if not end:
            period.update(deepcopy(start))
            period['final'] = final
            periods.append(period)
            continue
        period['metodo'] = 'DIFERENCIA_DE_ACUMULADOS'
        period['cortes'] = {kind: {'criterio': 'DIFERENCIA_DE_ACUMULADOS',
            'desde': start.get('cortes', {}).get(kind, {}).get('desde'),
            'hasta': end.get('cortes', {}).get(kind, {}).get('desde'),
            'corte_inicio': start.get('cortes', {}).get(kind, {}),
            'corte_fin': end.get('cortes', {}).get(kind, {})} for kind in ('ingreso', 'egreso')}
        if start.get('error') or end.get('error') or start['inicial']['fecha'] >= end_info['fecha']:
            period['error'] = 'No se puede separar este tramo: revisá fechas y errores de los acumulados.'
            period['advertencias'].append(period['error'])
            periods.append(period)
            continue
        cuts_valid = True
        for kind in ('ingreso', 'egreso'):
            a_cut, b_cut = start.get('cortes', {}).get(kind, {}), end.get('cortes', {}).get(kind, {})
            a_from, b_from = a_cut.get('desde'), b_cut.get('desde')
            a_to, b_to = a_cut.get('hasta'), b_cut.get('hasta')
            if a_from and b_from and a_to and b_to:
                cuts_valid &= a_from <= b_from <= a_to and a_to == b_to
        left = {r['codigo']: r for r in start['filas']}
        right = {r['codigo']: r for r in end['filas']}
        for code in sorted(left.keys() | right.keys()):
            a, b = left.get(code), right.get(code)
            row = deepcopy(a or b)
            row['sistema_ok'] = None  # El control directo actual se presenta por separado.
            row['comparacion_sistema_disponible'] = False
            reason = ''
            same_members = a and b and sorted(a.get('codigos', [code])) == sorted(b.get('codigos', [code]))
            if not same_members or not a.get('incluido_inicial', True) or not b.get('incluido_inicial', True):
                reason = 'Componente o composición de grupo sin cobertura comparable en ambos iniciales.'
            elif a.get('unidad_compatible') is False or b.get('unidad_compatible') is False or a.get('unidad_analisis') != b.get('unidad_analisis'):
                reason = 'Las unidades de los acumulados no coinciden.'
            incomes, in_valid = _restar_detalles(a.get('detalle_ingresos', []) if a else [], b.get('detalle_ingresos', []) if b else [], 'cantidad')
            outcomes, out_valid = _restar_detalles(a.get('detalle_egresos', []) if a else [], b.get('detalle_egresos', []) if b else [], 'cantidad_equivalente')
            scrap = float((a or {}).get('scrap', 0)) - float((b or {}).get('scrap', 0))
            if not cuts_valid or not in_valid or not out_valid or scrap < -1e-8:
                reason = 'Cortes, exclusiones o scrap no anidados: revisá los dos acumulados antes de evaluar el tramo.'
            row.update(detalle_ingresos=incomes, detalle_egresos=outcomes,
                       ingresos=sum(d['cantidad'] for d in incomes),
                       egresos=sum(d['cantidad_equivalente'] for d in outcomes), scrap=scrap,
                       incluido_inicial=bool(a and a.get('incluido_inicial', True)),
                       incluido_final=bool(b and b.get('incluido_inicial', True)),
                       cobertura_inicial=(a or {}).get('cobertura_inicial', 'NO_INCLUIDO'),
                       cobertura_final=(b or {}).get('cobertura_inicial', 'NO_INCLUIDO'),
                       conteo_completo=True, comparable=not reason, motivo_no_comparable=reason,
                       fisico_inicial=(a or {}).get('fisico_inicial'),
                       conteo_explotado_actual=(b or {}).get('fisico_inicial'),
                       fisico_actual=(b or {}).get('fisico_inicial'),
                       detalle_explosion_final=(b or {}).get('detalle_explosion_inicial', ''))
            if reason:
                row.update(esperado=None, diferencia_conciliacion=None,
                           porcentaje_desvio_conciliacion=None, conciliacion_ok=None)
                period['advertencias'].append(f'{code}: {reason}')
            else:
                expected = row['fisico_inicial'] + row['ingresos'] - row['egresos'] - scrap
                actual = row['fisico_actual']
                row.update(esperado=expected, diferencia_conciliacion=actual - expected,
                           porcentaje_desvio_conciliacion=(actual - expected) * 100 / expected if expected else (0 if actual == 0 else None),
                           conciliacion_ok=dentro(actual, expected, tolerancia))
            period['filas'].append(row)
        periods.append(period)
    return periods


def fecha_calculo():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
