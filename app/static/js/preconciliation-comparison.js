/* Comparación y revisión: la identificación de material siempre queda a cargo del usuario. */
const comparisonState = { mode: "ACCUMULATED", focus: null, returnFocus: null };

function registerComparisonEvents() {
    $("#comparison-mode").addEventListener("change", (event) => { comparisonState.mode = event.target.value; renderComparison(); });
    $("#comparison-search").addEventListener("input", renderComparison);
    $("#comparison-filter").addEventListener("change", renderComparison);
    $("#comparison-matrix").addEventListener("click", (event) => {
        const cell = event.target.closest("[data-period-code]");
        if (cell) openPeriodEvidence(cell.dataset.periodCode, Number(cell.dataset.periodIndex));
    });
    $("#close-period-evidence").addEventListener("click", () => $("#period-evidence").close());
    $("#period-evidence").addEventListener("close", () => {
        const focus = comparisonState.returnFocus;
        if (focus?.isConnected) focus.focus({ preventScroll: true });
    });
    $("#period-evidence-content").addEventListener("click", (event) => {
        const movement = event.target.closest("[data-evidence-remittance]");
        if (movement) {
            $("#period-evidence").close();
            $("#movement-search").value = movement.dataset.evidenceRemittance;
            $("#movement-scenario").value = "ALL";
            setAnalysisView("REMITTANCES");
            $(movement.dataset.kind === "IN" ? "#income-register" : "#outcome-register").open = true;
            $("#back-to-evidence").classList.remove("hidden");
            $("#movements-panel").scrollIntoView({ block: "start", behavior: "smooth" });
        }
        const piece = event.target.closest("[data-open-piece]");
        if (piece) { $("#period-evidence").close(); openPieceFromSummary(event); }
    });
    $("#back-to-evidence").addEventListener("click", () => {
        setAnalysisView("SUMMARY");
        if (comparisonState.focus) openPeriodEvidence(comparisonState.focus.code, comparisonState.focus.index);
    });
    $("#export-comparison").addEventListener("click", exportComparison);
}

function comparisonPeriods() {
    if (!state.calculation) return [];
    return comparisonState.mode === "CONSECUTIVE"
        ? state.calculation.periodos_consecutivos || []
        : state.calculation.escenarios.map((period) => ({ ...period, final: state.calculation.inventario_final || state.setup.final }));
}

function rowComparable(row) { return Boolean(row) && row.comparable !== false && row.conteo_completo !== false && row.conciliacion_ok !== null; }
function coverageLabel(value) { return ({ CONTADO: "Contado", EXPLOTADO: "Componente explotado", PENDIENTE: "Conteo pendiente", NO_INCLUIDO: "No incluido" })[value] || "Cobertura sin registrar"; }
function periodTitle(period) { return `${period.inicial.codigo} → ${period.final?.codigo || state.setup.final.codigo}`; }
function currentSystemRow(code) { return state.calculation?.escenarios.flatMap((p) => p.filas).find((r) => r.codigo === code) || null; }
function systemComparable(row) { return row && row.comparacion_sistema_disponible !== false && row.sistema_ok !== null; }

function renderComparison() {
    renderSnapshotState();
    const periods = comparisonPeriods();
    const matrix = $("#comparison-matrix");
    const previousScroll = matrix.scrollLeft;
    if (!periods.length) {
        matrix.innerHTML = '<p class="empty">Este análisis guardado todavía no tiene tramos consecutivos. Actualizá el cálculo para incorporarlos.</p>';
        $("#comparison-quality").innerHTML = "";
        return;
    }
    const byCode = new Map();
    periods.forEach((p, index) => p.filas.forEach((r) => {
        if (!byCode.has(r.codigo)) byCode.set(r.codigo, { row: r, cells: [] });
        byCode.get(r.codigo).cells[index] = r;
    }));
    const query = normalize($("#comparison-search").value), filter = $("#comparison-filter").value;
    const records = [...byCode.values()].filter(({ row, cells }) => {
        if (query && !normalize(`${row.codigo} ${row.descripcion} ${(row.codigos || []).join(" ")} ${row.codigo_material || ""}`).includes(query)) return false;
        const note = state.setup.notas[row.codigo] || {};
        if (filter === "DIFFERENCE") return cells.some((r) => rowComparable(r) && !r.conciliacion_ok) || systemComparable(currentSystemRow(row.codigo)) && !currentSystemRow(row.codigo).sistema_ok;
        if (filter === "PENDING") return cells.some((r) => r.conteo_completo === false);
        if (filter === "COVERAGE") return cells.length !== periods.length || periods.some((p, i) => !cells[i] || cells[i].comparable === false && cells[i].conteo_completo !== false);
        if (filter === "UNVERIFIED") return cells.some((r) => [...r.detalle_ingresos, ...r.detalle_egresos].some((d) => !d.verificado));
        if (filter === "OPEN") return note.estado !== "RESUELTO";
        if (filter === "RESOLVED") return note.estado === "RESUELTO";
        return true;
    });
    const urgency = ({ row, cells }) => cells.filter((r) => rowComparable(r) && !r.conciliacion_ok).length + (systemComparable(currentSystemRow(row.codigo)) && !currentSystemRow(row.codigo).sistema_ok ? 1 : 0);
    records.sort((a, b) => urgency(b) - urgency(a) || a.row.codigo.localeCompare(b.row.codigo, "es", { numeric: true }));
    const allRows = periods.flatMap((p) => p.filas), evaluated = allRows.filter(rowComparable), good = evaluated.filter((r) => r.conciliacion_ok).length;
    const movements = new Map();
    allRows.forEach((r) => [...r.detalle_ingresos, ...r.detalle_egresos].forEach((d) => movements.set(d.clave || JSON.stringify(d), d)));
    const verified = [...movements.values()].filter((d) => d.verificado).length;
    $("#comparison-quality").innerHTML = `
        <div><span>Cobertura comparable</span><strong>${evaluated.length}/${byCode.size * periods.length}</strong><small>comparaciones evaluables · ${periods.filter((p) => p.error).length} períodos con error</small></div>
        <div><span>Dentro de tolerancia</span><strong>${evaluated.length ? compactPercentage(good * 100 / evaluated.length) : "—"}</strong><small>${good}/${evaluated.length} evaluadas · no mide certeza del análisis</small></div>
        <div><span>Documentación verificada</span><strong>${verified}/${movements.size}</strong><small>movimientos únicos en los períodos visibles</small></div>`;
    matrix.innerHTML = records.length ? `<table style="min-width:${570 + periods.length * 190}px"><colgroup><col style="width:220px">${periods.map(() => '<col style="width:190px">').join("")}<col style="width:170px"><col style="width:180px"></colgroup><thead><tr><th>Componente / MP</th>${periods.map((p) => `<th>${escapeHtml(periodTitle(p))}<small>${formatDate(p.inicial.fecha)} → ${formatDate(p.final.fecha)}${p.error ? " · Error de período" : ""}</small></th>`).join("")}<th>Sistema actual<small>Control directo · ${escapeHtml(state.setup.final.codigo)}</small></th><th>Revisión</th></tr></thead><tbody>${records.map(({row,cells}) => {
        const current = currentSystemRow(row.codigo), note = state.setup.notas[row.codigo] || {};
        return `<tr><th><strong>${escapeHtml(row.codigo)}</strong><small>${escapeHtml(row.descripcion || "")}</small><em>${escapeHtml(row.unidad_analisis || "Unidad sin registrar")}</em></th>${periods.map((p,i) => {
            const r = cells[i], comparable = rowComparable(r), tone = !comparable ? "pending" : r.conciliacion_ok ? "ok" : "bad";
            return `<td><button type="button" class="period-cell ${tone}" data-period-code="${escapeHtml(row.codigo)}" data-period-index="${i}" aria-label="Revisar ${escapeHtml(row.codigo)} en ${escapeHtml(periodTitle(p))}"><strong>${comparable ? signed(r.diferencia_conciliacion) : r?.conteo_completo === false ? "Pendiente" : !r || r.incluido_inicial === false || r.incluido_final === false ? "Sin cobertura" : "No evaluable"}</strong><small>${comparable ? percentage(r.porcentaje_desvio_conciliacion) : escapeHtml(r?.motivo_no_comparable || p.error || "No incluido en este período")}</small></button></td>`;
        }).join("")}<td><span class="system-cell ${systemComparable(current) ? current.sistema_ok ? "ok" : "bad" : "pending"}">${systemComparable(current) ? signed(current.diferencia_sistema) : "Sin control directo"}</span></td><td><span>${escapeHtml(summaryStatus(note))}</span><small>${escapeHtml(causeLabel(note.causa))}</small></td></tr>`;
    }).join("")}</tbody></table>` : '<p class="empty">No hay componentes para este filtro.</p>';
    matrix.scrollLeft = previousScroll;
    if ($("#period-evidence").open && comparisonState.focus) renderPeriodEvidence();
}

function openPeriodEvidence(code, index) {
    comparisonState.focus = { code, index };
    comparisonState.returnFocus = document.activeElement;
    renderPeriodEvidence();
    if (!$("#period-evidence").open) $("#period-evidence").showModal();
}

function cutCriterionLabel(value) {
    return ({ FECHAS: "Por fechas", REMITOS: "Por remitos", MIXTO_INICIAL_REMITO: "Mixto: remito inicial y fecha final", MIXTO_FINAL_REMITO: "Mixto: fecha inicial y remito final", DIFERENCIA_DE_ACUMULADOS: "Diferencia entre acumulados" })[value] || "Criterio sin registrar";
}
function cutDateLabel(value) { return value ? formatDate(value) + (String(value).length > 10 ? ` ${String(value).slice(11)}` : "") : "sin registrar"; }

function cutHtml(cut) {
    if (!cut) return "Sin datos de corte en esta fotografía";
    const origins = cut.corte_inicio ? `<small>Criterios de origen: ${cutCriterionLabel(cut.corte_inicio.criterio)} / ${cutCriterionLabel(cut.corte_fin?.criterio)}</small>` : "";
    return `${origins}${cutCriterionLabel(cut.criterio)} · desde ${escapeHtml(cutDateLabel(cut.desde))} (excluido) hasta ${escapeHtml(cutDateLabel(cut.hasta))} (incluido)${cut.remito_inicial || cut.remito_final ? `<small>Remitos informados: ${escapeHtml(cut.remito_inicial || "—")} → ${escapeHtml(cut.remito_final || "—")}</small>` : ""}`;
}

function evidenceMovements(label, rows, kind) {
    return `<details class="evidence-movements" open><summary>${label} · ${rows.length} ${rows.length === 1 ? "renglón" : "renglones"}</summary>${rows.length ? rows.map((d) => `<article><button type="button" data-evidence-remittance="${escapeHtml(d.remito || "")}" data-kind="${kind}">${escapeHtml(d.remito || "Sin número")}</button><span>${formatDate(d.fecha)} · ${escapeHtml(d.codigo_material || d.pieza_origen || d.codigo || "")}</span><strong>${number(kind === "IN" ? d.cantidad : d.cantidad_equivalente)}</strong><small>${d.verificado ? "Verificado" : "Sin verificar"}${kind === "OUT" ? ` · ${number(d.cantidad_pieza)} × uso ${number(d.uso)}` : ""}</small></article>`).join("") : '<p>Sin movimientos aplicados.</p>'}</details>`;
}

function renderPeriodEvidence() {
    const focus = comparisonState.focus, period = comparisonPeriods()[focus.index];
    if (!period) { $("#period-evidence").close(); return; }
    const row = period.filas.find((r) => r.codigo === focus.code), current = currentSystemRow(focus.code);
    $("#period-evidence-title").textContent = `${focus.code} · ${periodTitle(period)}`;
    $("#period-evidence-content").innerHTML = `
        <p>${formatDate(period.inicial.fecha)} → ${formatDate(period.final.fecha)} · tolerancia ±${number(state.calculation.tolerancia)}%</p>
        <section class="evidence-control"><h3>Control directo contra sistema actual</h3><p>Conteo directo y stock del sistema del inventario ${escapeHtml(state.setup.final.codigo)}. Su base es independiente de la explosión del período.</p><dl><div><dt>Conteo directo</dt><dd>${systemComparable(current) ? number(current.conteo_actual) : "Sin control comparable"}</dd></div><div><dt>Sistema</dt><dd>${systemComparable(current) ? number(current.sistema_actual) : "—"}</dd></div><div><dt>Diferencia</dt><dd>${systemComparable(current) ? signed(current.diferencia_sistema) : "—"}</dd></div></dl>${current?.es_grupo_mp ? `<details><summary>Integrantes de la MP compartida</summary>${(current.detalle_piezas || []).map((p) => `<p>${escapeHtml(p.codigo)} · ${p.comparacion_sistema_disponible === false ? "Sin control directo comparable" : `conteo ${number(p.conteo_actual)} · sistema ${number(p.sistema_actual)} · Δ ${signed(p.diferencia_sistema)}`}</p>`).join("")}</details>` : ""}</section>
        <section class="evidence-control"><h3>Evolución física del período</h3>${row ? `<p>${escapeHtml(row.unidad_analisis || "Unidad sin registrar")} · ${coverageLabel(row.cobertura_inicial)} → ${coverageLabel(row.cobertura_final)}</p>${!rowComparable(row) ? `<p class="evidence-warning">${escapeHtml(row.motivo_no_comparable || "Comparación pendiente")}. No se interpreta un dato ausente como cero.</p>` : ""}<dl>${[["Inicial explotado",row.fisico_inicial],["Ingresos",row.ingresos],["Egresos",row.egresos],["Scrap",row.scrap],["Esperado",row.esperado],["Final explotado",row.conteo_explotado_actual],["Diferencia",row.diferencia_conciliacion]].map(([label,value]) => `<div><dt>${label}</dt><dd>${number(value)}</dd></div>`).join("")}</dl><details><summary>Trazabilidad de la explosión</summary><p>Inicial: ${escapeHtml(row.detalle_explosion_inicial || "Sin traza registrada")}</p><p>Final: ${escapeHtml(row.detalle_explosion_final || "Sin traza registrada")}</p></details>` : '<p class="evidence-warning">Este componente no está incluido en el período seleccionado.</p>'}</section>
        <section class="evidence-control"><h3>Cortes del período</h3><p>Ingresos: ${cutHtml(period.cortes?.ingreso)}</p><p>Egresos: ${cutHtml(period.cortes?.egreso)}</p>${period.metodo ? '<p>Tramo derivado por diferencia entre acumulados. Conserva sus correcciones y exclusiones.</p>' : ""}</section>
        ${typeof period.diagnostico_egresos?.fuente_configurada === "boolean" ? `<p class="movement-source-status">${period.diagnostico_egresos.fuente_configurada === false ? "No se consultó la fuente de movimientos: revisá la conexión productiva." : `Despachos encontrados: ${number(period.diagnostico_egresos.despachos_encontrados)} · aplicados a componentes del análisis: ${number(period.diagnostico_egresos.despachos_aplicados)}`}</p>` : ""}
        ${row ? evidenceMovements("Ingresos",row.detalle_ingresos,"IN") + evidenceMovements("Egresos",row.detalle_egresos,"OUT") : ""}
        ${(period.advertencias || []).length ? `<details class="evidence-warnings"><summary>Advertencias del período (${period.advertencias.length})</summary>${period.advertencias.map((w) => `<p>${escapeHtml(w)}</p>`).join("")}</details>` : ""}
        ${state.rows.some((r) => r.codigo === focus.code) ? `<button type="button" class="evidence-review-button" data-open-piece="${escapeHtml(focus.code)}">Abrir revisión: recontar, verificar remitos o revisar sistema</button>` : ""}`;
}

function renderSnapshotState() {
    if (!state.calculation) return;
    const pending = state.timers.size || noteSavesPending || [...failedNoteSaves].some((key) => key.startsWith(`${inventoryId}:`)) || document.querySelector(".remittance-group.dirty");
    const obsoleteMovements = Number(state.calculation.version_movimientos || 0) < 2;
    const unavailableMovements = state.calculation.escenarios.some((p) => p.diagnostico_egresos?.fuente_configurada === false);
    $("#analysis-snapshot-state").classList.toggle("dirty", Boolean(state.snapshotDirty || pending || obsoleteMovements || unavailableMovements));
    const selectionChanged = !sameNumbers(selectedIds(), state.calculation.escenarios.map((p) => p.inicial.id));
    const recalcular = Number(state.calculation.version_movimientos || 0) < 2 ? "Cálculo de despachos anterior: usá Actualizar inventario final para recalcular los movimientos. " : "";
    const sourceWarning = unavailableMovements ? "No se consultó la fuente productiva de movimientos: revisá la conexión antes de interpretar los resultados. " : "";
    const status = `${recalcular}${sourceWarning}${selectionChanged ? "Selección modificada: recalculá para aplicar. " : ""}${pending ? "Ediciones pendientes. " : ""}${state.snapshotDirty ? "Cambios sin guardar" : state.analysisId ? "Guardado" : "Análisis sin guardar"}`;
    $("#analysis-snapshot-state").textContent = `${status} · Cálculo: ${state.calculation.calculado_en ? formatDateTime(state.calculation.calculado_en) : "sin fecha"} · Guardado: ${state.savedAt ? formatDateTime(state.savedAt) : "pendiente"}`;

}

async function exportComparison() {
    if (state.busy || mutationPending || state.timers.size || noteSavesPending) return toast("Esperá a que terminen los cambios antes de exportar", true);
    const button = $("#export-comparison"); button.disabled = true;
    try {
        const response = await fetch(`/api/inventarios/${inventoryId}/preconciliacion/exportar`, { method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({inventarios_iniciales:state.calculation.escenarios.map((s)=>s.inicial.id),vista:"COMPARACION",analisis_id:state.snapshotDirty ? null : state.analysisId}) });
        if (!response.ok) throw Error("No se pudo exportar la comparación");
        const blob=await response.blob(), link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download=`comparacion_${state.setup.final.codigo}.xlsx`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
        toast(state.snapshotDirty ? "Comparación exportada con los datos actualmente guardados en inventarios y auditoría" : "Comparación exportada");
    } catch(error) { toast(error.message,true); } finally { button.disabled=false; }
}
