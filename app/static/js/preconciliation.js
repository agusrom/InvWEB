let inventoryId = Number(document.body.dataset.inventoryId);
const standalone = document.body.dataset.standalone === "true";
const initialParams = new URLSearchParams(location.search);
const requestedInventoryId = Number(initialParams.get("inventario"));
const requestedAnalysisId = initialParams.get("analisis");
const state = { setup: null, calculation: null, analysisId: null, analysisName: "", savedAnalyses: [], rows: [], timers: new Map(), selectedScenario: null, activeView: "SUMMARY", busy: false };
const $ = (selector) => document.querySelector(selector);
let manualSearchTimer = null;
let manualSearchController = null;

document.addEventListener("DOMContentLoaded", async () => {
    registerEvents();
    await loadSavedAnalyses();
    if (requestedAnalysisId) {
        await loadSavedAnalysis(requestedAnalysisId);
    } else if (Number.isFinite(inventoryId) && inventoryId > 0) {
        showAnalysisWorkspace();
        await loadSetup();
    } else if (Number.isFinite(requestedInventoryId) && requestedInventoryId > 0) {
        showAnalysisWorkspace();
        await loadInventoryOptions(requestedInventoryId);
    } else {
        showAnalysisHome();
    }
});

function registerEvents() {
    $("#final-inventory-picker").addEventListener("change", async (event) => {
        inventoryId = Number(event.target.value);
        history.replaceState({}, "", `/analisis-stock?inventario=${inventoryId}`);
        await changeFinalInventory();
    });
    $("#new-analysis").addEventListener("click", startNewAnalysis);
    $("#back-to-analyses").addEventListener("click", showAnalysisHome);
    $("#saved-analysis-search").addEventListener("input", renderSavedAnalyses);
    $("#manual-code-input").addEventListener("input", scheduleManualCodeSearch);
    $("#manual-code-results").addEventListener("click", chooseManualCode);
    ["#movement-search", "#movement-scenario"].forEach((id) => $(id).addEventListener(id === "#movement-search" ? "input" : "change", renderMovements));
    $("#manual-form").addEventListener("submit", addManual);
    $("#movements-panel").addEventListener("click", movementAction);
    $("#movements-panel").addEventListener("input", movementDraftChanged);
    $("#movements-panel").addEventListener("change", movementDraftChanged);
    $("#export-excel").addEventListener("click", exportExcel);
    $("#save-analysis").addEventListener("click", saveAnalysis);
    $("#export-scenario").addEventListener("change", (event) => {
        state.selectedScenario = Number(event.target.value);
        $("#summary-scenario").value = String(state.selectedScenario);
        renderSummaryView();
    });
    $(".analysis-view-tabs").addEventListener("click", (event) => {
        const button = event.target.closest("[data-analysis-view]");
        if (button) setAnalysisView(button.dataset.analysisView);
    });
    $("#summary-scenario").addEventListener("change", (event) => {
        state.selectedScenario = Number(event.target.value);
        $("#export-scenario").value = String(state.selectedScenario);
        renderSummaryView();
    });
    ["#summary-search", "#summary-status", "#summary-sort"].forEach((id) => $(id).addEventListener(id === "#summary-search" ? "input" : "change", renderSummaryTable));
    $("#summary-table").addEventListener("click", openPieceFromSummary);
    $("#conciliation-diffusion").addEventListener("click", openConciliationDiffusion);
    $("#print-view").addEventListener("click", printCurrentView);
    $("#calculate").addEventListener("click", calculate);
    $("#initial-options").addEventListener("change", limitSelection);
    $("#search").addEventListener("input", renderRows);
    $("#diagnosis-filter").addEventListener("change", renderRows);
    $("#evidence-filter").addEventListener("change", renderRows);
    $("#priority-sort").addEventListener("change", renderRows);
    $("#piece-results").addEventListener("change", handleAnalysisChange);
    $("#piece-results").addEventListener("input", handleAnalysisInput);
    $("#piece-results").addEventListener("click", handlePieceClick);
    $("#saved-analysis-list").addEventListener("click", savedAnalysisAction);
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".manual-code-field")) hideManualCodeResults();
    });
}

async function exportExcel() {
    const button = $("#export-excel");
    const scenarioId = Number($("#export-scenario").value || state.selectedScenario || state.calculation.escenarios[0]?.inicial.id);
    const scenarioIds = [scenarioId];
    button.disabled = true;
    button.textContent = "Generando Excel…";
    try {
        const response = await fetch(`/api/inventarios/${inventoryId}/preconciliacion/exportar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ inventarios_iniciales: scenarioIds, vista: "CONCILIACION", analisis_id: state.analysisId }),
        });
        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.detail || "No se pudo generar el Excel");
        }
        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition") || "";
        const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || "analisis_stock.xlsx";
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        toast("Excel generado");
    } catch (error) {
        toast(error.message, true);
    } finally {
        button.disabled = false;
        button.textContent = "⇩ Exportar Excel";
    }
}

async function saveAnalysis() {
    if (!state.calculation) return toast("Primero calculá los escenarios", true);
    const ids = state.calculation.escenarios.map((scenario) => scenario.inicial.id);
    const dates = state.calculation.escenarios.map((scenario) => formatDate(scenario.inicial.fecha)).join(", ");
    const suggested = state.analysisName || `${state.setup.final.codigo} · desde ${dates}`;
    const name = window.prompt(state.analysisId ? "Nombre del análisis a actualizar" : "Nombre del análisis", suggested)?.trim();
    if (!name) return;
    const button = $("#save-analysis");
    button.disabled = true;
    button.textContent = "Guardando…";
    try {
        const saved = await api(`/api/inventarios/${inventoryId}/preconciliacion/guardar`, {
            method: "POST",
            body: JSON.stringify({ inventarios_iniciales: ids, nombre: name }),
        });
        state.analysisId = saved.id;
        state.analysisName = name;
        state.calculation = saved.calculo;
        buildRows();
        renderAll();
        await loadSavedAnalyses();
        toast("Análisis guardado");
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; renderSaveButton(); }
}

function printCurrentView() {
    const details = [...document.querySelectorAll("#results details:not(.hidden)")];
    const previouslyOpen = new Set(details.filter((detail) => detail.open));
    details.forEach((detail) => { detail.open = true; });
    const restore = () => details.forEach((detail) => { detail.open = previouslyOpen.has(detail); });
    window.addEventListener("afterprint", restore, { once: true });
    window.print();
}

function showAnalysisHome() {
    if (!standalone) {
        window.location.href = "/analisis-stock";
        return;
    }
    $("#analysis-home").classList.remove("hidden");
    $("#analysis-workspace").classList.add("hidden");
    $("#draft-badge").classList.add("hidden");
    $("#analysis-title").textContent = "Análisis de stock";
    $("#final-description").textContent = "Abrí un análisis existente o iniciá uno nuevo.";
    document.title = "Análisis de stock";
    history.replaceState({}, "", "/analisis-stock");
    renderSavedAnalyses();
}

function showAnalysisWorkspace() {
    $("#analysis-home").classList.add("hidden");
    $("#analysis-workspace").classList.remove("hidden");
    $("#draft-badge").classList.remove("hidden");
}

async function startNewAnalysis() {
    showAnalysisWorkspace();
    state.analysisId = null;
    state.analysisName = "";
    state.activeView = "SUMMARY";
    renderSaveButton();
    await loadInventoryOptions();
}

async function loadInventoryOptions(preferredId = null) {
    try {
        const inventories = await api("/api/preconciliacion/inventarios-disponibles");
        if (!inventories.length) throw new Error("No hay inventarios contados disponibles para analizar");
        const requested = Number(preferredId || new URLSearchParams(location.search).get("inventario"));
        const chosen = inventories.some((item) => item.id === requested) ? requested : inventories[0].id;
        $("#final-inventory-picker").innerHTML = inventories.map((item) => `<option value="${item.id}" ${item.id === chosen ? 'selected' : ''}>${escapeHtml(item.codigo)} · ${formatDate(item.fecha)} · ${escapeHtml(item.cliente)} · ${escapeHtml(item.estado)}</option>`).join("");
        inventoryId = chosen;
        await changeFinalInventory();
    } catch (error) {
        $("#selector-message").textContent = error.message;
        $("#selector-message").classList.add("error");
    }
}

async function changeFinalInventory() {
    state.setup = null;
    state.calculation = null;
    state.analysisId = null;
    state.analysisName = "";
    state.rows = [];
    state.selectedScenario = null;
    state.activeView = "SUMMARY";
    $("#results").classList.add("hidden");
    $("#initial-options").innerHTML = '<p class="empty">Cargando períodos comparables…</p>';
    renderSaveButton();
    await loadSetup();
}

async function loadSavedAnalyses() {
    try {
        state.savedAnalyses = await api("/api/preconciliacion/analisis-guardados");
        renderSavedAnalyses();
    } catch (error) {
        $("#saved-analysis-list").innerHTML = `<p class="message error">${escapeHtml(error.message)}</p>`;
    }
}

function renderSavedAnalyses() {
    const query = normalize($("#saved-analysis-search").value);
    const analyses = state.savedAnalyses.filter((item) => !query || normalize(`${item.nombre} ${item.final_codigo || ''} ${(item.iniciales_codigos || []).join(' ')}`).includes(query));
    $("#saved-analysis-list").innerHTML = analyses.length ? analyses.map((item) => `
        <article class="saved-analysis-row">
            <div class="saved-analysis-identity"><strong>${escapeHtml(item.nombre)}</strong><span>Inventario final: <b>${escapeHtml(item.final_codigo || `#${item.final_id}`)}</b></span></div>
            <div class="saved-analysis-periods"><small>Períodos iniciales</small><span>${(item.iniciales_codigos || []).length ? item.iniciales_codigos.map(escapeHtml).join(' · ') : `${item.inventarios_iniciales.length} seleccionado(s)`}</span></div>
            ${savedIndicatorsHtml(item.indicadores)}
            <div class="saved-analysis-updated"><small>Última actualización</small><span>${formatDateTime(item.actualizado_en)}</span></div>
            <div class="saved-analysis-actions"><button type="button" data-open-analysis="${item.id}">Abrir / editar</button><button type="button" class="danger" data-delete-analysis="${item.id}" data-analysis-name="${escapeHtml(item.nombre)}">Eliminar</button></div>
        </article>`).join("") : `<p class="empty">${query ? 'No hay análisis que coincidan con la búsqueda.' : 'Todavía no hay análisis guardados.'}</p>`;
}

function savedIndicatorsHtml(indicators = {}) {
    const reconciliation = indicators.peor_escenario?.porcentaje;
    return `<div class="saved-analysis-indicators"><small>Confiabilidad de conciliación</small><span><b>${compactPercentage(reconciliation)}</b></span></div>`;
}

async function savedAnalysisAction(event) {
    const deleteButton = event.target.closest("[data-delete-analysis]");
    if (deleteButton) {
        const name = deleteButton.dataset.analysisName || "este análisis";
        if (!confirm(`¿Eliminar “${name}”?\n\nSe elimina el análisis guardado, pero no los inventarios ni la auditoría de remitos.`)) return;
        deleteButton.disabled = true;
        try {
            await api(`/api/preconciliacion/analisis-guardados/${deleteButton.dataset.deleteAnalysis}`, { method: "DELETE" });
            state.savedAnalyses = state.savedAnalyses.filter((item) => item.id !== deleteButton.dataset.deleteAnalysis);
            renderSavedAnalyses();
            toast("Análisis eliminado");
        } catch (error) {
            deleteButton.disabled = false;
            toast(error.message, true);
        }
        return;
    }
    const openButton = event.target.closest("[data-open-analysis]");
    if (openButton) await loadSavedAnalysis(openButton.dataset.openAnalysis);
}

async function loadSavedAnalysis(analysisId) {
    try {
        showAnalysisWorkspace();
        const saved = await api(`/api/preconciliacion/analisis-guardados/${analysisId}`);
        inventoryId = Number(saved.final_id);
        if (standalone) await loadInventoryOptions(inventoryId);
        else await loadSetup();
        const selected = new Set(saved.inventarios_iniciales.map(Number));
        document.querySelectorAll("#initial-options input").forEach((input) => { input.checked = selected.has(Number(input.value)); });
        state.calculation = saved.calculo;
        if (state.calculation.notas_guardadas) state.setup.notas = state.calculation.notas_guardadas;
        state.analysisId = saved.id;
        state.analysisName = saved.nombre;
        state.selectedScenario = state.calculation.escenarios[0]?.inicial.id || null;
        state.activeView = "SUMMARY";
        buildRows();
        renderAll();
        $("#results").classList.remove("hidden");
        renderSaveButton();
        history.replaceState({}, "", `/analisis-stock?inventario=${inventoryId}&analisis=${saved.id}`);
        $("#results").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) { toast(error.message, true); }
}

function renderSaveButton() {
    const button = $("#save-analysis");
    if (!button) return;
    button.textContent = state.analysisId ? "Actualizar análisis" : "Guardar análisis";
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "No se pudo completar la operación");
    return body;
}

async function loadSetup() {
    try {
        state.setup = await api(`/api/inventarios/${inventoryId}/preconciliacion`);
        const final = state.setup.final;
        document.title = `Análisis de stock · ${final.codigo}`;
        $("#analysis-title").textContent = `Análisis de stock · ${final.codigo}`;
        $("#final-description").textContent = `${final.cliente} · ${formatDate(final.fecha)} · ${final.contados}/${final.total} códigos completos · ${final.estado}`;
        $("#draft-badge").textContent = final.estado === "Cerrado" ? "INVENTARIO CERRADO" : "PROVISORIA";
        renderOptions();
    } catch (error) {
        $("#selector-message").textContent = error.message;
        $("#selector-message").classList.add("error");
    }
}

function renderOptions() {
    const options = state.setup.iniciales;
    $("#initial-options").innerHTML = options.length ? options.map((item, index) => `
        <label class="initial-card">
            <input type="checkbox" value="${item.id}" ${index < 2 ? "checked" : ""}>
            <span><strong>${escapeHtml(item.codigo)}</strong><small>${formatDate(item.fecha)} · ${escapeHtml(item.estado)}</small></span>
        </label>
    `).join("") : '<p class="empty">No hay inventarios anteriores completos y comparables.</p>';
}

function selectedIds() {
    return [...document.querySelectorAll("#initial-options input:checked")].map((input) => Number(input.value));
}

function limitSelection(event) {
    const selected = selectedIds();
    if (selected.length > 4) {
        event.target.checked = false;
        toast("Podés comparar hasta cuatro inventarios iniciales");
    }
}

async function calculate(refresh = false) {
    if (state.busy) return;
    const ids = refresh === true ? state.calculation.escenarios.map((s) => s.inicial.id) : selectedIds();
    if (!ids.length) return toast("Elegí al menos un inventario inicial", true);
    const button = $("#calculate");
    state.busy = true;
    button.disabled = true;
    button.textContent = "Calculando movimientos…";
    try {
        state.calculation = await api(`/api/inventarios/${inventoryId}/preconciliacion/calcular`, {
            method: "POST",
            body: JSON.stringify({ inventarios_iniciales: ids }),
        });
        if (refresh !== true) {
            state.analysisId = null;
            state.analysisName = "";
            state.activeView = "SUMMARY";
        }
        buildRows();
        renderAll();
        renderSaveButton();
        $("#results").classList.remove("hidden");
        if (refresh !== true) $("#results").scrollIntoView({ behavior: "smooth", block: "start" });
        await loadSavedAnalyses();
        return true;
    } catch (error) {
        toast(error.message, true);
    } finally {
        state.busy = false;
        button.disabled = false;
        button.textContent = "Calcular escenarios";
    }
}

function buildRows() {
    const map = new Map();
    state.calculation.escenarios.forEach((scenario) => scenario.filas.forEach((row) => {
        if (!map.has(row.codigo)) map.set(row.codigo, {
            codigo: row.codigo,
            codigo_cliente: row.codigo_cliente || "",
            codigo_material: row.codigo_material || "",
            codigos: row.codigos || [row.codigo],
            codigos_cliente: row.codigos_cliente || {},
            es_grupo_mp: Boolean(row.es_grupo_mp),
            descripcion: row.descripcion,
            scenarios: [],
        });
        map.get(row.codigo).scenarios.push({ initial: scenario.inicial, ...row });
    }));
    state.rows = [...map.values()].map((row) => ({ ...row, diagnosis: diagnose(row) }));
    const rank = { SYSTEM: 0, MOVEMENTS: 1, LOCATED: 2, REVIEW: 3, OK: 4 };
    state.rows.sort((a, b) => (rank[a.diagnosis.key] - rank[b.diagnosis.key]) || a.codigo.localeCompare(b.codigo, "es", { numeric: true }));
}

function diagnose(row) {
    const scenarios = row.scenarios;
    if (scenarios.length !== state.calculation.escenarios.length) return diagnosis("REVIEW", "Comparación incompleta", "Faltan resultados de uno o más escenarios; revisá las advertencias.", "Baja", "Completar los escenarios antes de decidir", "REVISAR_MOVIMIENTOS");
    const systemOk = scenarios[0]?.sistema_ok ?? false;
    const reconciliationOk = scenarios.map((item) => item.conciliacion_ok);
    const allReconciliationOk = reconciliationOk.length > 0 && reconciliationOk.every(Boolean);
    const anyReconciliationOk = reconciliationOk.some(Boolean);
    const hasSystemAdjustments = scenarios.some((item) => (item.ajustes_sistema || []).length);
    const closedPeriods = reconciliationOk.filter(Boolean).length;
    if (systemOk && allReconciliationOk) return diagnosis("OK", "Ambos controles correctos", "El control directo contra sistema y la conciliación explotada están dentro de tolerancia, cada uno en su propia base.", "Alta", "Validar y cerrar el análisis", "RESUELTO");
    if (!systemOk && allReconciliationOk && hasSystemAdjustments) return diagnosis("SYSTEM", "Revisar ajustes del sistema", "La conciliación explotada cierra y el control directo tiene diferencia; produc16 aporta ajustes para investigar, sin compararlos contra el esperado explotado.", "Media", "Validar el motivo y la imputación de los ajustes", "AJUSTAR_SISTEMA");
    if (!systemOk && allReconciliationOk) return diagnosis("SYSTEM", "Revisar gestión del sistema", "La conciliación explotada cierra desde todos los iniciales, pero el control directo contra sistema tiene diferencia.", "Alta", "Revisar ajustes e imputaciones del sistema", "AJUSTAR_SISTEMA");
    if (systemOk && !allReconciliationOk) return diagnosis("MOVEMENTS", "Revisar documentación", "El control directo contra sistema cierra, pero los movimientos no explican la evolución explotada.", "Alta", "Validar remitos, scrap y estructura", "REVISAR_MOVIMIENTOS");
    if (anyReconciliationOk) return diagnosis("LOCATED", "Desvío localizado", `La conciliación cierra en ${closedPeriods} de ${scenarios.length} períodos; el origen puede ubicarse entre inventarios.`, "Media", "Revisar el primer período que deja de cerrar", "REVISAR_MOVIMIENTOS");
    return diagnosis("REVIEW", "Revisión completa", `Fallan los dos controles independientes${hasSystemAdjustments ? " y hay ajustes del sistema para revisar" : ""}; no alcanza para atribuir automáticamente la causa.`, "Baja", "Confirmar conteo directo y después revisar documentación", "REVISAR_MOVIMIENTOS");
}

function diagnosis(key, label, detail, confidence, action, status) { return { key, label, detail, confidence, action, status }; }

function renderAll() {
    renderRows();
    renderUnifiedControls();
    renderSummaryView();
    setAnalysisView(state.activeView);
}

function compactPercentage(value) {
    return value === null || value === undefined ? "—" : `${new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 }).format(value)}%`;
}

function selectedSummaryScenario() {
    return state.calculation?.escenarios.find((scenario) => scenario.inicial.id === state.selectedScenario) || state.calculation?.escenarios[0] || null;
}

function setAnalysisView(view) {
    const allowed = new Set(["SUMMARY", "DETAIL", "REMITTANCES"]);
    state.activeView = allowed.has(view) ? view : "SUMMARY";
    document.querySelectorAll("[data-analysis-view]").forEach((button) => button.classList.toggle("active", button.dataset.analysisView === state.activeView));
    $("#analysis-summary-view").classList.toggle("hidden", state.activeView !== "SUMMARY");
    $("#cross-panel").classList.toggle("hidden", state.activeView === "SUMMARY");
    $("#analysis-detail-view").classList.toggle("hidden", state.activeView !== "DETAIL");
    $("#movements-panel").classList.toggle("hidden", state.activeView !== "REMITTANCES");
    if (state.activeView === "REMITTANCES" && state.calculation) renderMovements();
}

function renderSummaryView() {
    const scenario = selectedSummaryScenario();
    const rows = scenario?.filas || [];
    const good = rows.filter((item) => item.conciliacion_ok).length;
    const reliability = rows.length ? good * 100 / rows.length : null;
    const tolerance = state.calculation?.tolerancia ?? state.setup?.tolerancia ?? 5;
    const tone = reliability === null ? "neutral" : reliability >= 95 ? "good" : reliability >= 80 ? "warning" : "bad";
    $("#summary-reliability").className = `summary-reliability ${tone}`;
    $("#summary-reliability").innerHTML = scenario ? `
        <div><span>CONFIABILIDAD DE LA CONCILIACIÓN</span><small>${formatDate(scenario.inicial.fecha)} · ${escapeHtml(scenario.inicial.codigo)} · tolerancia ±${number(tolerance)}%</small></div>
        <strong>${compactPercentage(reliability)}</strong>
        <em>${good} grupos/piezas OK de ${rows.length}</em>
    ` : '<p class="empty">No hay un escenario de conciliación disponible.</p>';
    renderSummaryTable();
}

function causeLabel(code) {
    if (!code) return "Sin causa asignada";
    const cause = (state.setup?.causas || []).find((item) => String(item.codigo || item.id || item.valor || "") === String(code));
    return cause?.nombre || cause?.descripcion || cause?.label || code;
}

function summaryStatus(note) {
    const value = String(note?.estado || "PENDIENTE");
    const labels = { PENDIENTE: "Pendiente", RECONTAR: "Recontar", AJUSTAR_SISTEMA: "Ajustar sistema", REVISAR_MOVIMIENTOS: "Revisar movimientos", RESUELTO: "Resuelto" };
    return labels[value] || value.replaceAll("_", " ");
}

function renderSummaryTable() {
    if (!state.calculation || !state.setup) return;
    const scenario = selectedSummaryScenario();
    const notes = state.setup.notas || {};
    const query = normalize($("#summary-search").value);
    const status = $("#summary-status").value;
    const order = $("#summary-sort").value;
    let rows = [...(scenario?.filas || [])].filter((item) => {
        const note = notes[item.codigo] || {};
        const searchable = `${item.codigo} ${(item.codigos || []).join(" ")} ${item.codigo_material || ""} ${item.codigo_cliente || ""} ${item.descripcion || ""} ${causeLabel(note.causa)} ${note.observacion || ""} ${summaryStatus(note)}`;
        if (query && !normalize(searchable).includes(query)) return false;
        if (status === "DIFFERENCE") return !item.conciliacion_ok;
        if (status === "OK") return item.conciliacion_ok;
        if (status === "PENDING") return String(note.estado || "PENDIENTE") === "PENDIENTE";
        if (status === "NO_CAUSE") return !item.conciliacion_ok && !String(note.causa || "").trim();
        if (status === "RESOLVED") return String(note.estado || "") === "RESUELTO";
        return true;
    });
    if (order === "CODE") rows.sort((a, b) => a.codigo.localeCompare(b.codigo, "es", { numeric: true }));
    else if (order === "PERCENTAGE") rows.sort((a, b) => Math.abs(Number(b.porcentaje_desvio_conciliacion || 0)) - Math.abs(Number(a.porcentaje_desvio_conciliacion || 0)));
    else rows.sort((a, b) => Math.abs(Number(b.diferencia_conciliacion || 0)) - Math.abs(Number(a.diferencia_conciliacion || 0)));
    if (!rows.length) {
        $("#summary-table").innerHTML = '<p class="empty">No hay piezas para este filtro.</p>';
        return;
    }
    $("#summary-table").innerHTML = `<div class="summary-table-count">${rows.length} grupo${rows.length === 1 ? " / pieza" : "s / piezas"}</div><div class="summary-table-scroll"><table>
        <thead><tr><th>Pieza</th><th>Inicial</th><th>Ingresos</th><th>Egresos</th><th>Esperado</th><th>Conteo actual</th><th>Diferencia</th><th>Desvío</th><th>Análisis realizado</th><th></th></tr></thead>
        <tbody>${rows.map((item) => {
            const note = notes[item.codigo] || {};
            const analysis = note.causa || note.observacion || note.estado ? `<strong>${escapeHtml(summaryStatus(note))}</strong><span>${escapeHtml(causeLabel(note.causa))}</span>${note.observacion ? `<small>${escapeHtml(note.observacion)}</small>` : ""}` : '<strong>Pendiente</strong><span>Sin causa asignada</span>';
            return `<tr class="${item.conciliacion_ok ? "conciliation-ok" : "conciliation-bad"}">
                <td><span class="summary-piece"><strong>${item.es_grupo_mp ? `MP ${escapeHtml(item.codigo_material)} compartida` : escapeHtml(item.codigo)}</strong>${item.es_grupo_mp ? `<span class="shared-piece-codes">${item.codigos.map((codigo) => `<b>${escapeHtml(codigo)}</b>`).join("")}</span>` : ""}${item.codigo_cliente ? `<em>Cliente: ${escapeHtml(item.codigo_cliente)}</em>` : ""}<small>${escapeHtml(item.descripcion || "Sin descripción")}</small></span></td>
                <td class="numeric">${number(item.fisico_inicial)}</td><td class="numeric positive">${signed(item.ingresos)}</td><td class="numeric negative">${signed(-Number(item.egresos || 0))}</td><td class="numeric">${number(item.esperado)}</td><td class="numeric">${number(item.conteo_explotado_actual ?? item.fisico_actual)}</td>
                <td class="numeric difference ${item.conciliacion_ok ? "ok" : "bad"}">${signed(item.diferencia_conciliacion)}</td><td class="numeric difference ${item.conciliacion_ok ? "ok" : "bad"}">${percentage(item.porcentaje_desvio_conciliacion)}</td>
                <td><span class="summary-analysis">${analysis}</span></td><td><button type="button" class="summary-detail-button" data-open-piece="${escapeHtml(item.codigo)}">Ver detalle</button></td>
            </tr>`;
        }).join("")}</tbody></table></div>`;
}

function openPieceFromSummary(event) {
    const button = event.target.closest("[data-open-piece]");
    if (!button) return;
    const code = button.dataset.openPiece;
    $("#search").value = code;
    $("#diagnosis-filter").value = "ALL";
    $("#evidence-filter").value = "ALL";
    setAnalysisView("DETAIL");
    renderRows();
    const card = [...document.querySelectorAll("#piece-results [data-code]")].find((item) => item.dataset.code === code);
    if (!card) return;
    card.classList.add("summary-focus");
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(() => card.classList.remove("summary-focus"), 2200);
}

function openConciliationDiffusion() {
    if (!state.analysisId) {
        toast("Guardá el análisis antes de abrir la difusión", true);
        return;
    }
    const scenarioId = Number(state.selectedScenario || selectedSummaryScenario()?.inicial?.id);
    const params = new URLSearchParams({
        analisis: state.analysisId,
        inicial: String(scenarioId),
    });
    window.open(
        `/inventarios/${inventoryId}/preconciliacion/difusion?${params}`,
        "_blank",
        "noopener",
    );
}

function renderRows() {
    const query = normalize($("#search").value);
    const filter = $("#diagnosis-filter").value;
    const evidenceFilter = $("#evidence-filter").value;
    const order = $("#priority-sort").value;
    const rows = state.rows.filter((row) => (
        (filter === "ALL" || row.diagnosis.key === filter)
        && (!query || normalize(`${row.codigo} ${(row.codigos || []).join(" ")} ${row.codigo_material || ""} ${row.descripcion}`).includes(query))
        && evidenceMatches(row, evidenceFilter)
    ));
    rows.sort((a, b) => compareRows(a, b, order));
    $("#piece-results").innerHTML = rows.length ? rows.map(pieceCard).join("") : '<p class="empty">No hay piezas para este filtro.</p>';
}

function rowEvidence(row) {
    const details = row.scenarios.flatMap((item) => [...(item.detalle_ingresos || []), ...(item.detalle_egresos || [])]);
    const keys = new Set(details.map((item) => item.clave).filter(Boolean));
    const movements = (state.calculation.movimientos || []).filter((item) => keys.has(item.clave));
    const adjustmentKeys = new Set();
    row.scenarios.forEach((item) => (item.ajustes_sistema || []).forEach((adjustment) => adjustmentKeys.add(`${adjustment.fecha}|${adjustment.operacion}|${adjustment.cantidad}|${adjustment.motivo}`)));
    const currentDifference = Number(row.scenarios[0]?.diferencia_sistema || 0);
    const recurrence = currentDifference === 0 ? 0 : (state.setup.historial_sistema || []).filter((inventory) => {
        const difference = Number(historyValue(inventory, row)?.diferencia || 0);
        return difference && Math.sign(difference) === Math.sign(currentDifference);
    }).length;
    return {
        adjustments: adjustmentKeys.size,
        unverified: movements.filter((item) => !item.verificado).length,
        corrected: movements.filter((item) => item.cantidad_editada !== null && item.cantidad_editada !== undefined).length,
        manual: movements.filter((item) => item.manual).length,
        recurrence,
    };
}

function evidenceMatches(row, filter) {
    if (filter === "ALL") return true;
    const evidence = rowEvidence(row);
    if (filter === "ADJUSTMENTS") return evidence.adjustments > 0;
    if (filter === "UNVERIFIED") return evidence.unverified > 0;
    if (filter === "CORRECTED") return evidence.corrected > 0 || evidence.manual > 0;
    if (filter === "RECURRENT") return evidence.recurrence >= 2;
    return true;
}

function rowImpact(row) {
    return Math.max(Math.abs(Number(row.scenarios[0]?.diferencia_sistema || 0)), ...row.scenarios.map((item) => Math.abs(Number(item.diferencia_conciliacion || 0))));
}

function rowPercentageImpact(row) {
    return Math.max(Math.abs(Number(row.scenarios[0]?.porcentaje_desvio_sistema || 0)), ...row.scenarios.map((item) => Math.abs(Number(item.porcentaje_desvio_conciliacion || 0))));
}

function compareRows(a, b, order) {
    if (order === "QUANTITY") return rowImpact(b) - rowImpact(a) || a.codigo.localeCompare(b.codigo, "es", { numeric: true });
    if (order === "PERCENTAGE") return rowPercentageImpact(b) - rowPercentageImpact(a) || a.codigo.localeCompare(b.codigo, "es", { numeric: true });
    if (order === "RECURRENCE") return rowEvidence(b).recurrence - rowEvidence(a).recurrence || rowImpact(b) - rowImpact(a);
    if (order === "CODE") return a.codigo.localeCompare(b.codigo, "es", { numeric: true });
    const rank = { SYSTEM: 0, MOVEMENTS: 1, LOCATED: 2, REVIEW: 3, OK: 4 };
    return rank[a.diagnosis.key] - rank[b.diagnosis.key] || rowImpact(b) - rowImpact(a);
}

function pieceCard(row) {
    const current = row.scenarios[0] || {};
    const note = state.setup.notas[row.codigo] || {};
    const controls = note.controles || {};
    const evidence = rowEvidence(row);
    const evidenceChips = [
        evidence.adjustments ? `${evidence.adjustments} ajuste${evidence.adjustments === 1 ? '' : 's'} en sistema` : "",
        evidence.unverified ? `${evidence.unverified} movimiento${evidence.unverified === 1 ? '' : 's'} sin verificar` : "",
        evidence.corrected ? `${evidence.corrected} cantidad${evidence.corrected === 1 ? '' : 'es'} corregida${evidence.corrected === 1 ? '' : 's'}` : "",
        evidence.manual ? `${evidence.manual} movimiento${evidence.manual === 1 ? '' : 's'} manual${evidence.manual === 1 ? '' : 'es'}` : "",
        evidence.recurrence >= 2 ? `Patrón repetido en ${evidence.recurrence} inventarios` : "",
    ].filter(Boolean);
    const checkedControls = Object.values(controls).filter(Boolean).length;
    const identity = row.es_grupo_mp
        ? `<strong>MP ${escapeHtml(row.codigo_material)} compartida</strong><span class="shared-piece-codes">${row.codigos.map((codigo) => `<b>${escapeHtml(codigo)}</b>`).join("")}</span><span>${escapeHtml(row.descripcion || "Sin descripción")}</span>`
        : `<strong>${escapeHtml(row.codigo)}</strong><span>${escapeHtml(row.descripcion || "Sin descripción")}</span>`;
    return `<article class="piece-card ${row.diagnosis.key.toLowerCase()} ${row.es_grupo_mp ? "shared-analysis-group" : ""}" data-code="${escapeHtml(row.codigo)}">
        <div class="piece-main">
            <div class="piece-identity">${identity}<div class="diagnosis ${row.diagnosis.key.toLowerCase()}"><span><b>${row.diagnosis.label}</b><em>Confianza ${row.diagnosis.confidence}</em></span><small>${row.diagnosis.detail}</small><span class="diagnosis-action"><strong>Siguiente:</strong> ${row.diagnosis.action}</span><button type="button" data-apply-diagnosis="${row.diagnosis.status}">Aplicar acción</button></div>
                ${evidenceChips.length ? `<div class="evidence-chips">${evidenceChips.map((text) => `<span>${escapeHtml(text)}</span>`).join("")}</div>` : ''}
                <div class="piece-inline-controls"><label>Estado<select data-note="estado">${statusOptions(note.estado)}</select></label><label>Causa probable<select data-note="causa">${causeOptions(note.causa)}</select></label><span class="save-state">${note.estado || note.causa || note.observacion ? "✓ Guardado" : "Sin análisis"}</span></div>
                <details class="validation-checklist"><summary>Comprobaciones ${checkedControls}/5</summary><div>${validationCheck("conteo", "Conteo confirmado", controls)}${validationCheck("ingresos", "Ingresos revisados", controls)}${validationCheck("egresos", "Egresos revisados", controls)}${validationCheck("scrap", "Scrap revisado", controls)}${validationCheck("ajustes", "Ajustes del sistema revisados", controls)}</div></details>
            </div>
            <div class="current-values">
                ${row.es_grupo_mp ? sharedSystemComparisonsHtml(current) : `
                    ${systemStockHtml(current)}
                    ${physicalStockHtml(current)}
                    <span class="${current.diferencia_sistema ? "bad" : ""}"><small>Vs. sistema</small><strong>${signed(current.diferencia_sistema)}</strong><em>${percentage(current.porcentaje_desvio_sistema)}</em></span>
                    ${systemAdjustmentsHtml(row)}
                `}
            </div>
            <div class="history-column">${systemHistoryHtml(row, current.diferencia_sistema)}<label class="inline-observation">Observación<textarea data-note="observacion" rows="2" maxlength="1500" placeholder="Ej. Desde julio cierra; revisar ajuste realizado en junio.">${escapeHtml(note.observacion || "")}</textarea></label></div>
        </div>
        <div class="piece-reconciliation">
            <div class="piece-reconciliation-heading"><strong>Control explotado · Conciliación y origen de movimientos</strong><span>Padres explotados a componentes. No utiliza el stock directo del sistema.</span></div>
            <div class="piece-scenario-details">${row.scenarios.map(scenarioDetailHtml).join("")}</div>
        </div>
    </article>`;
}

function validationCheck(key, label, controls) {
    return `<label><input type="checkbox" data-check="${key}" ${controls[key] ? "checked" : ""}>${label}</label>`;
}

function sharedSystemComparisonsHtml(current) {
    const pieces = current.detalle_piezas || [];
    if (!pieces.length) return `${systemStockHtml(current)}${physicalStockHtml(current)}`;
    return `<div class="shared-system-comparisons">
        <div class="shared-system-heading"><strong>Control directo por pieza</strong><span>La conciliación conjunta se muestra debajo.</span></div>
        ${pieces.map((piece) => {
            const system = piece.detalle_sistema || {};
            const physical = piece.detalle_fisico || {};
            return `<article class="shared-system-piece ${piece.sistema_ok ? "ok" : "bad"}">
                <header><div><strong>${escapeHtml(piece.codigo)}</strong>${piece.codigo_cliente ? `<small>Cliente ${escapeHtml(piece.codigo_cliente)}</small>` : ""}</div><span class="${piece.diferencia_sistema ? "bad" : "ok"}">Δ ${signed(piece.diferencia_sistema)} · ${percentage(piece.porcentaje_desvio_sistema)}</span></header>
                <div class="shared-system-totals"><span><small>Sistema</small><b>${number(piece.sistema_actual)}</b></span><span><small>Físico</small><b>${number(piece.conteo_actual)}</b></span></div>
                <div class="shared-system-breakdown">
                    <span><small>MP sistema / físico</small><b>${number(system.materia_prima_equivalente)} / ${number(physical.materia_prima_equivalente)}</b></span>
                    <span><small>Proceso sistema / físico</small><b>${number(system.en_proceso)} / ${number(physical.en_proceso)}</b></span>
                    <span><small>PT sistema / físico</small><b>${number(system.producto_terminado)} / ${number(physical.producto_terminado)}</b></span>
                </div>
                ${systemAdjustmentsBlock(piece.ajustes_sistema || [], "Ajustes de esta pieza")}
            </article>`;
        }).join("")}
    </div>`;
}

function systemStockHtml(current) {
    const detail = current.detalle_sistema || {};
    const assigned = Number(detail.stock_asignado || 0);
    return `<div class="system-stock-card">
        <span><small>Sistema total · MP + Proceso + PT</small><strong>${number(current.sistema_actual)}</strong></span>
        <div class="stock-breakdown">
            <span title="${current.es_grupo_mp ? 'MP compartida consolidada una sola vez' : `${number(detail.materia_prima)} ${escapeHtml(detail.unidad_consumo || 'C/U')} ÷ ${number(detail.consumo_material || 1)}`}"><small>MP equiv.</small><b>${number(detail.materia_prima_equivalente ?? detail.materia_prima)}</b></span>
            <span><small>En proceso</small><b>${number(detail.en_proceso)}</b></span>
            <span title="El stock asignado ya está incluido en PT"><small>PT${assigned ? ` · asign. ${number(assigned)}` : ''}</small><b>${number(detail.producto_terminado)}</b></span>
        </div>
    </div>`;
}

function physicalStockHtml(current) {
    const detail = current.detalle_fisico || {};
    const system = current.detalle_sistema || {};
    return `<div class="system-stock-card physical-stock-card">
        <span><small>Físico total · MP + Proceso + PT</small><strong>${number(current.conteo_actual)}</strong></span>
        <div class="stock-breakdown">
            <span title="${current.es_grupo_mp ? 'MP compartida consolidada una sola vez' : `${number(detail.materia_prima)} ${escapeHtml(detail.unidad_consumo || 'C/U')} ÷ ${number(detail.consumo_material || 1)}`}"><small>MP equiv.</small><b>${number(detail.materia_prima_equivalente ?? detail.materia_prima)}</b><em>Δ ${signed(Number(detail.materia_prima_equivalente || 0) - Number(system.materia_prima_equivalente || 0))}</em></span>
            <span><small>En proceso</small><b>${number(detail.en_proceso)}</b><em>Δ ${signed(Number(detail.en_proceso || 0) - Number(system.en_proceso || 0))}</em></span>
            <span><small>PT</small><b>${number(detail.producto_terminado)}</b><em>Δ ${signed(Number(detail.producto_terminado || 0) - Number(system.producto_terminado || 0))}</em></span>
        </div>
    </div>`;
}

function systemAdjustmentsHtml(row) {
    const unique = new Map();
    row.scenarios.forEach((scenario) => (scenario.ajustes_sistema || []).forEach((adjustment) => {
        const key = `${adjustment.fecha}|${adjustment.operacion}|${adjustment.cantidad}|${adjustment.motivo}`;
        if (!unique.has(key)) unique.set(key, adjustment);
    }));
    const adjustments = [...unique.values()];
    return systemAdjustmentsBlock(adjustments, "Ajustes del sistema · produc16");
}

function systemAdjustmentsBlock(adjustments, title) {
    if (!adjustments.length) return "";
    const net = adjustments.reduce((sum, item) => sum + Number(item.cantidad || 0), 0);
    return `<details class="system-adjustments"><summary><span>${escapeHtml(title)}</span><b>${adjustments.length} registro${adjustments.length === 1 ? '' : 's'} · neto ${signed(net)}</b></summary><div>${adjustments.map((item) => `<article><strong>${item.etapa === "TERMINADO" ? "PT" : `Proceso ${escapeHtml(item.operacion || "—")}`}</strong><span>${formatDate(item.fecha)}</span><b class="${Number(item.cantidad) < 0 ? "negative" : "positive"}">${signed(item.cantidad)}</b><em>${escapeHtml(item.motivo || "Sin motivo informado")}</em></article>`).join("")}</div><p>Estos ajustes pertenecen al control directo del sistema; no forman parte de la fórmula explotada.</p></details>`;
}

function historyValue(inventory, row) {
    const codes = row.es_grupo_mp ? row.codigos : [row.codigo];
    const items = codes.map((code) => inventory.filas?.[code]).filter(Boolean);
    if (!items.length) return null;
    return {
        conteo: items.reduce((sum, item) => sum + Number(item.conteo || 0), 0),
        sistema: items.reduce((sum, item) => sum + Number(item.sistema || 0), 0),
        diferencia: items.reduce((sum, item) => sum + Number(item.diferencia || 0), 0),
    };
}

function systemHistoryHtml(row, currentDifference) {
    if (row.es_grupo_mp) {
        const pieces = row.scenarios[0]?.detalle_piezas || [];
        return `<div class="shared-piece-histories">${pieces.map((piece) => (
            systemHistoryForCode(piece.codigo, piece.diferencia_sistema, piece.codigo)
        )).join("")}</div>`;
    }
    return systemHistoryForCode(row.codigo, currentDifference);
}

function systemHistoryForCode(code, currentDifference, title = "") {
    const history = state.setup.historial_sistema || [];
    const repeated = Number(currentDifference) === 0 ? [] : history.filter((inventory) => {
        const difference = inventory.filas?.[code]?.diferencia;
        return difference && Math.sign(difference) === Math.sign(currentDifference);
    });
    const pattern = repeated.length >= 2 ? `<b class="history-pattern">Patrón repetido: ${currentDifference < 0 ? 'faltante' : 'sobrante'} actual y en ${repeated.length} inventarios anteriores</b>` : '';
    return `<div class="system-history">${title ? `<strong class="system-history-piece">${escapeHtml(title)}</strong>` : ""}<span>3 inventarios anteriores · diferencia vs. sistema</span>${pattern}<div>${history.length ? history.map((inventory) => {
        const item = inventory.filas?.[code];
        return `<article class="${item && item.diferencia ? 'bad' : 'ok'}"><small>${formatDate(inventory.fecha)} · ${escapeHtml(inventory.codigo)}</small><strong>${item ? signed(item.diferencia) : '—'}</strong><em>${item ? `${number(item.conteo)} vs ${number(item.sistema)}` : 'Sin conteo comparable'}</em></article>`;
    }).join('') : '<small>Sin inventarios anteriores comparables.</small>'}</div></div>`;
}

function scenarioDetailHtml(item) {
    return `<details class="scenario-calculation ${item.conciliacion_ok ? "ok" : "bad"}" data-scenario-detail="${item.initial.id}">
        <summary>
            <span>${formatDate(item.initial.fecha)} · ${escapeHtml(item.initial.codigo)}</span>
            <small>Inicial <b>${number(item.fisico_inicial)}</b></small>
            <small>Ingresos <b class="positive">＋${number(item.ingresos)}</b></small>
            <small>Egresos <b class="negative">−${number(item.egresos)}</b></small>
            <small class="scenario-scrap">Scrap <b>${number(item.scrap)}</b></small>
            <small class="scenario-expected">Esperado explotado <b>${number(item.esperado)}</b></small>
            <small class="scenario-current">Conteo actual explotado <b>${number(item.conteo_explotado_actual ?? item.fisico_actual)}</b></small>
            <span class="reconciliation-difference ${item.conciliacion_ok ? "ok" : "bad"}"><small>Físico explotado vs. esperado</small><strong>${signed(item.diferencia_conciliacion)}</strong><b>${percentage(item.porcentaje_desvio_conciliacion)}</b></span>
            <em class="detail-action">▾ Ver remitos</em>
        </summary>
        <div class="calculation-detail">
            <div class="scrap-editor"><label>Scrap del período <input data-scrap type="number" min="0" step="any" value="${item.scrap || 0}"></label><button type="button" data-save-scrap="${item.initial.id}">Guardar scrap y recalcular</button></div>
            ${movementListHtml("Ingresos considerados", item.detalle_ingresos, "IN")}
            ${movementListHtml("Egresos considerados", item.detalle_egresos, "OUT")}
        </div>
    </details>`;
}

function movementListHtml(title, rows = [], type) {
    if (!rows.length) return `<section class="movement-list"><h4>${title}</h4><p>Sin movimientos para esta pieza.</p></section>`;
    return `<section class="movement-list"><h4>${title} <span>${rows.length}</span></h4><div>${rows.map((row) => type === "IN" ? `
        <article class="${row.verificado ? 'verified' : ''}"><strong>${row.verificado ? '✓ ' : ''}${escapeHtml(row.remito || "Sin remito")}</strong><span>${formatDate(row.fecha)} · ${escapeHtml(row.codigo_material || row.codigo || "")}${row.manual ? ' · MANUAL' : ''}</span><b>＋${number(row.cantidad)}</b>${row.observacion ? `<em>${escapeHtml(row.observacion)}</em>` : ''}</article>
    ` : `
        <article class="${row.verificado ? 'verified' : ''}"><strong>${row.verificado ? '✓ ' : ''}${escapeHtml(row.remito || "Sin remito")}</strong><span>${formatDate(row.fecha)} · ${escapeHtml(row.pieza_origen || "")}${row.manual ? ' · MANUAL' : ''}</span><small>${number(row.cantidad_pieza)} × ${number(row.uso)}</small><b>−${number(row.cantidad_equivalente)}</b>${row.observacion ? `<em>${escapeHtml(row.observacion)}</em>` : ''}</article>
    `).join("")}</div></section>`;
}

function statusOptions(selected = "PENDIENTE") {
    const values = { PENDIENTE: "Pendiente", RECONTAR: "Recontar", REVISAR_MOVIMIENTOS: "Revisar movimientos", AJUSTAR_SISTEMA: "Ajustar sistema", RESUELTO: "Resuelto" };
    return Object.entries(values).map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("");
}

function causeOptions(selected = "") {
    return ['<option value="">Sin causa asignada</option>', ...state.setup.causas.map((cause) => `<option value="${escapeHtml(cause.codigo)}" ${cause.codigo === selected ? "selected" : ""}>${escapeHtml(cause.nombre)}</option>`)].join("");
}

function handleAnalysisChange(event) {
    const card = event.target.closest("[data-code]");
    if (card && (event.target.dataset.note || event.target.dataset.check)) {
        updateChecklistSummary(card);
        saveNote(card);
    }
}

function handleAnalysisInput(event) {
    const card = event.target.closest("[data-code]");
    if (!card || event.target.dataset.note !== "observacion") return;
    clearTimeout(state.timers.get(card.dataset.code));
    state.timers.set(card.dataset.code, setTimeout(() => saveNote(card), 650));
}

async function saveNote(card) {
    const payload = { codigo: card.dataset.code };
    card.querySelectorAll("[data-note]").forEach((input) => { payload[input.dataset.note] = input.value; });
    payload.controles = {};
    card.querySelectorAll("[data-check]").forEach((input) => { payload.controles[input.dataset.check] = input.checked; });
    const status = card.querySelector(".save-state");
    status.textContent = "Guardando…";
    try {
        const saved = await api(`/api/inventarios/${inventoryId}/preconciliacion/nota`, { method: "PUT", body: JSON.stringify(payload) });
        state.setup.notas[card.dataset.code] = saved;
        status.textContent = "✓ Guardado";
        renderSummaryView();
    } catch (error) {
        status.textContent = "Error al guardar";
        toast(error.message, true);
    }
}

function updateChecklistSummary(card) {
    const controls = [...card.querySelectorAll("[data-check]")];
    const summary = card.querySelector(".validation-checklist>summary");
    if (summary) summary.textContent = `Comprobaciones ${controls.filter((input) => input.checked).length}/${controls.length}`;
}

function handlePieceClick(event) {
    const apply = event.target.closest("[data-apply-diagnosis]");
    if (apply) {
        const card = apply.closest("[data-code]");
        const status = card?.querySelector('[data-note="estado"]');
        if (card && status) {
            status.value = apply.dataset.applyDiagnosis;
            saveNote(card);
        }
        return;
    }
    saveScrap(event);
}

function toast(message, error = false) {
    const element = $("#toast");
    element.textContent = message;
    element.className = `toast ${error ? "error" : ""}`;
    setTimeout(() => element.classList.add("hidden"), 3200);
}
function normalize(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
function number(value) { return new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(Number(value || 0)); }
function signed(value) { const numeric = Number(value || 0); return `${numeric > 0 ? "+" : ""}${number(numeric)}`; }
function percentage(value) { return value === null || value === undefined ? "—" : `${signed(value)}%`; }
function formatDate(value) { const [y, m, d] = String(value).slice(0, 10).split("-"); return `${d}/${m}/${y}`; }
function formatDateTime(value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value || "") : date.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" }); }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]); }

function renderUnifiedControls() {
    const scenarios = state.calculation.escenarios;
    if (!scenarios.some((scenario) => scenario.inicial.id === state.selectedScenario)) state.selectedScenario = scenarios[0]?.inicial.id || null;
    $("#export-scenario").innerHTML = scenarios.map((scenario) => `<option value="${scenario.inicial.id}" ${scenario.inicial.id === state.selectedScenario ? "selected" : ""}>Excel desde ${formatDate(scenario.inicial.fecha)} · ${escapeHtml(scenario.inicial.codigo)}</option>`).join("");
    $("#summary-scenario").innerHTML = scenarios.map((scenario) => `<option value="${scenario.inicial.id}" ${scenario.inicial.id === state.selectedScenario ? "selected" : ""}>Desde ${formatDate(scenario.inicial.fecha)} · ${escapeHtml(scenario.inicial.codigo)}</option>`).join("");
    const selected = $("#movement-scenario").value;
    $("#movement-scenario").innerHTML = '<option value="ALL">Todos los períodos seleccionados</option>' + scenarios.map((s) => `<option value="${s.inicial.id}">Desde ${escapeHtml(s.inicial.codigo)} · ${formatDate(s.inicial.fecha)}</option>`).join("");
    const validFilters = ["ALL", ...scenarios.map((s) => String(s.inicial.id))];
    $("#movement-scenario").value = validFilters.includes(selected) && selected !== "" ? selected : "ALL";
    $("#audit-warnings").innerHTML = warningsHtml(scenarios);
    $("#manual-form [name=fecha]").max = state.setup.final.fecha.slice(0, 10);
}

function warningsHtml(scenarios) {
    return scenarios.flatMap((s) => (s.advertencias || []).map((warning) => `<p class="audit-warning"><strong>${escapeHtml(s.inicial.codigo)}:</strong> ${escapeHtml(warning)}</p>`)).join("");
}

function movementCardHtml(movement) {
    return `<article class="audit-movement ${movement.verificado ? 'verified' : ''}" data-key="${movement.clave}">
        <div class="audit-identity">
            <strong>${movement.tipo === "IN" ? "Ingreso" : "Egreso"} · ${escapeHtml(movement.codigo)}</strong>
            <span>${movement.manual ? 'MANUAL' : 'SISTEMA'} · Original: ${number(movement.cantidad_original)} · Efectiva: ${number(movement.cantidad)}</span>
        </div>
        <div class="audit-controls">
            <label>Cantidad corregida<input data-quantity type="number" min="0" step="any" placeholder="${number(movement.cantidad_original)}" value="${movement.cantidad_editada ?? ''}"></label>
            <label class="check"><input data-verified type="checkbox" ${movement.verificado ? 'checked' : ''}>Verificado</label>
            <label>Comentario<textarea data-observation maxlength="1500" rows="2" placeholder="Qué se comprobó o por qué se corrigió">${escapeHtml(movement.observacion || '')}</textarea></label>
        </div>
        <fieldset><legend>Períodos incluidos</legend>${state.calculation.escenarios.map((scenario) => {
            const eligible = (movement.escenarios || []).includes(scenario.inicial.id);
            return `<label class="check"><input data-include="${scenario.inicial.id}" type="checkbox" ${eligible && !(movement.excluidos || []).includes(scenario.inicial.id) ? 'checked' : ''} ${eligible ? '' : 'disabled'}>Desde ${escapeHtml(scenario.inicial.codigo)}${eligible ? '' : ' — no corresponde'}</label>`;
        }).join("")}</fieldset>
        <div class="audit-actions"><button type="button" data-reset-movement>Usar cantidad original</button>${movement.manual ? '<button type="button" class="danger" data-delete-movement>Eliminar manual</button>' : ''}<span class="audit-save-state">${movement.verificado ? '✓ Verificado' : 'Pendiente de verificar'}</span></div>
    </article>`;
}

function renderMovements() {
    const query = normalize($("#movement-search").value);
    const scenario = $("#movement-scenario").value;
    const rows = [...(state.calculation.movimientos || [])];
    rows.sort((a, b) => String(a.fecha).localeCompare(String(b.fecha)) || String(a.remito).localeCompare(String(b.remito)));
    renderMovementType("IN", rows, "#income-movement-results", "#income-register-summary", query, scenario);
    renderMovementType("OUT", rows, "#outcome-movement-results", "#outcome-register-summary", query, scenario);
}

function renderMovementType(type, allRows, target, summaryTarget, query, scenario) {
    const typeRows = allRows.filter((movement) => movement.tipo === type);
    const groups = new Map();
    typeRows.forEach((movement) => {
        const key = String(movement.remito || "SIN REMITO").trim().toUpperCase();
        if (!groups.has(key)) groups.set(key, { remito: movement.remito || "Sin remito", fechas: new Set(), rows: [] });
        groups.get(key).fechas.add(String(movement.fecha).slice(0, 10));
        groups.get(key).rows.push(movement);
    });
    const visibleGroups = [...groups.values()].filter((group) => group.rows.some((movement) => (
        (scenario === "ALL" || (movement.escenarios || []).includes(Number(scenario)))
        && (!query || normalize(`${movement.remito} ${movement.codigo} ${movement.observacion || ''}`).includes(query))
    )));
    const rows = visibleGroups.flatMap((group) => group.rows);
    const verified = rows.filter((movement) => movement.verificado).length;
    const total = rows.reduce((sum, movement) => sum + Number(movement.cantidad || 0), 0);
    $(summaryTarget).innerHTML = `<strong>${rows.length} movimiento${rows.length === 1 ? '' : 's'}</strong><small>${verified}/${rows.length} verificados · Total ${number(total)}</small>`;
    if (!visibleGroups.length) {
        $(target).innerHTML = '<p class="empty">No hay remitos para este filtro.</p>';
        return;
    }
    $(target).innerHTML = visibleGroups.map((group) => {
        const groupVerified = group.rows.filter((movement) => movement.verificado).length;
        const groupTotal = group.rows.reduce((sum, movement) => sum + Number(movement.cantidad || 0), 0);
        return `<details class="remittance-group" data-remittance-type="${type}" data-remittance-key="${escapeHtml(String(group.rows[0]?.remito || 'SIN REMITO').trim().toUpperCase())}">
            <summary><span><strong>Remito ${escapeHtml(group.remito)}</strong><small>${[...group.fechas].map(formatDate).join(' / ')} · ${group.rows.length} código${group.rows.length === 1 ? '' : 's'}</small></span><span><b>${number(groupTotal)}</b><small>${groupVerified}/${group.rows.length} verificados</small></span></summary>
            <div class="remittance-group-body">
                <div class="remittance-bulk-actions">
                    <label class="check"><input data-verify-all type="checkbox" ${groupVerified === group.rows.length ? 'checked' : ''}> Verificar todas las piezas</label>
                    <span data-remittance-state>Sin cambios pendientes</span>
                    <button type="button" data-save-remittance disabled>Guardar remito</button>
                </div>
                <div class="remittance-movement-list">${group.rows.map(movementCardHtml).join("")}</div>
            </div>
        </details>`;
    }).join("");
}

let mutationPending = false;
async function mutate(url, method, payload) {
    if (mutationPending || state.busy) { toast("Esperá a que termine la operación actual", true); return false; }
    mutationPending = true;
    try {
        await api(url, { method, ...(payload === undefined ? {} : { body: JSON.stringify(payload) }) });
        const refreshed = await calculate(true);
        toast(refreshed ? "Guardado. Escenarios actualizados." : "Guardado, pero falló el recálculo. Volvé a calcular antes de usar los resultados.", !refreshed);
        return true;
    } catch (error) { toast(error.message, true); return false; }
    finally { mutationPending = false; }
}

async function movementAction(event) {
    const button = event.target.closest("button");
    if (!button) return;
    const group = button.closest(".remittance-group");
    if (button.hasAttribute("data-save-remittance") && group) {
        await saveRemittance(group, button);
        return;
    }
    const card = button.closest("[data-key]");
    if (!card) return;
    if (button.hasAttribute("data-reset-movement")) {
        card.querySelector("[data-quantity]").value = "";
        card.querySelector(".audit-save-state").textContent = "Pendiente: restaurar cantidad original";
        updateRemittanceDraft(group);
        return;
    }
    const url = `/api/inventarios/${inventoryId}/preconciliacion/movimientos/${card.dataset.key}`;
    if (button.hasAttribute("data-delete-movement")) {
        if (confirm("¿Eliminar este movimiento manual de todos los escenarios?")) await mutate(url, "DELETE");
    }
}

function movementDraftChanged(event) {
    const group = event.target.closest(".remittance-group");
    if (!group) return;
    if (event.target.hasAttribute("data-verify-all")) {
        group.querySelectorAll("[data-verified]").forEach((checkbox) => {
            checkbox.checked = event.target.checked;
        });
    }
    updateRemittanceDraft(group);
}

function remittanceMovementPayload(card) {
    const movement = state.calculation.movimientos.find((item) => item.clave === card.dataset.key);
    const exclusions = new Set(movement?.excluidos || []);
    card.querySelectorAll("[data-include]:not(:disabled)").forEach((checkbox) => {
        if (checkbox.checked) exclusions.delete(Number(checkbox.dataset.include));
        else exclusions.add(Number(checkbox.dataset.include));
    });
    const input = card.querySelector("[data-quantity]");
    return {
        clave: card.dataset.key,
        cantidad_editada: input.value === "" ? null : Number(input.value),
        verificado: card.querySelector("[data-verified]").checked,
        observacion: card.querySelector("[data-observation]").value,
        excluidos: [...exclusions].sort((a, b) => a - b),
    };
}

function sameNumbers(left, right) {
    const a = [...(left || [])].map(Number).sort((x, y) => x - y);
    const b = [...(right || [])].map(Number).sort((x, y) => x - y);
    return a.length === b.length && a.every((value, index) => value === b[index]);
}

function remittanceDraft(group) {
    const movements = [...group.querySelectorAll("[data-key]")].map(remittanceMovementPayload);
    let changed = false;
    let requiresRecalculation = false;
    movements.forEach((payload) => {
        const current = state.calculation.movimientos.find((item) => item.clave === payload.clave);
        if (!current) return;
        const quantityChanged = (current.cantidad_editada ?? null) !== payload.cantidad_editada;
        const periodsChanged = !sameNumbers(current.excluidos, payload.excluidos);
        const auditChanged = Boolean(current.verificado) !== payload.verificado
            || String(current.observacion || "") !== payload.observacion;
        changed ||= quantityChanged || periodsChanged || auditChanged;
        requiresRecalculation ||= quantityChanged || periodsChanged;
    });
    return { movements, changed, requiresRecalculation };
}

function updateRemittanceDraft(group) {
    if (!group) return;
    const draft = remittanceDraft(group);
    const button = group.querySelector("[data-save-remittance]");
    const status = group.querySelector("[data-remittance-state]");
    button.disabled = !draft.changed;
    button.textContent = draft.requiresRecalculation ? "Guardar remito y recalcular" : "Guardar remito";
    status.textContent = !draft.changed
        ? "Sin cambios pendientes"
        : draft.requiresRecalculation
            ? "Cambios de cálculo · se recalculará una sola vez"
            : "Verificación/comentarios · guardado rápido";
    group.classList.toggle("dirty", draft.changed);
}

function applySavedMovements(saved) {
    const updates = new Map(saved.map((item) => [item.clave, item]));
    state.calculation.movimientos.forEach((movement) => {
        const update = updates.get(movement.clave);
        if (update) Object.assign(movement, update);
    });
    state.calculation.escenarios.forEach((scenario) => (scenario.filas || []).forEach((row) => {
        ["detalle_ingresos", "detalle_egresos"].forEach((field) => (row[field] || []).forEach((detail) => {
            const update = updates.get(detail.clave);
            if (update) {
                detail.verificado = update.verificado;
                detail.observacion = update.observacion;
            }
        }));
    }));
}

function reopenRemittance(type, key) {
    const register = type === "IN" ? $("#income-register") : $("#outcome-register");
    if (register) register.open = true;
    const group = [...document.querySelectorAll(`.remittance-group[data-remittance-type="${type}"]`)]
        .find((item) => item.dataset.remittanceKey === key);
    if (group) {
        group.open = true;
        group.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
}

async function saveRemittance(group, button) {
    if (mutationPending || state.busy) return toast("Esperá a que termine la operación actual", true);
    const draft = remittanceDraft(group);
    if (!draft.changed) return toast("El remito no tiene cambios pendientes");
    const invalid = [...group.querySelectorAll("[data-quantity]")].find((input) => !input.reportValidity());
    if (invalid) return;
    const type = group.dataset.remittanceType;
    const key = group.dataset.remittanceKey;
    mutationPending = true;
    button.disabled = true;
    button.textContent = draft.requiresRecalculation ? "Guardando y recalculando…" : "Guardando remito…";
    try {
        const response = await api(`/api/inventarios/${inventoryId}/preconciliacion/movimientos/remito`, {
            method: "PUT",
            body: JSON.stringify({
                inventarios_iniciales: state.calculation.escenarios.map((scenario) => scenario.inicial.id),
                recalcular: draft.requiresRecalculation,
                movimientos: draft.movements,
            }),
        });
        if (response.recalculado) state.calculation = response.calculo;
        else applySavedMovements(response.movimientos || []);
        buildRows();
        renderAll();
        reopenRemittance(type, key);
        toast(response.recalculado
            ? "Remito guardado. Los escenarios se recalcularon una sola vez."
            : "Remito guardado sin recalcular: sólo cambió la auditoría.");
    } catch (error) {
        toast(error.message, true);
        updateRemittanceDraft(group);
    } finally {
        mutationPending = false;
        if (document.body.contains(button)) button.disabled = false;
    }
}

function scheduleManualCodeSearch(event) {
    clearTimeout(manualSearchTimer);
    const query = event.target.value.trim();
    if (query.length < 2) {
        hideManualCodeResults();
        return;
    }
    manualSearchTimer = setTimeout(() => searchManualCodes(query), 220);
}

async function searchManualCodes(query) {
    if (manualSearchController) manualSearchController.abort();
    manualSearchController = new AbortController();
    const results = $("#manual-code-results");
    results.innerHTML = '<span class="manual-search-state">Buscando piezas y materias primas…</span>';
    results.classList.remove("hidden");
    try {
        const encoded = encodeURIComponent(query);
        const [pieces, materials] = await Promise.all([
            api(`/api/busqueda/piezas?q=${encoded}&limite=8`, { signal: manualSearchController.signal }),
            api(`/api/busqueda/materiales?q=${encoded}&limite=8`, { signal: manualSearchController.signal }),
        ]);
        if ($("#manual-code-input").value.trim() !== query) return;
        const options = [
            ...(pieces.resultados || []).map((item) => ({ ...item, tipo: "PIEZA" })),
            ...(materials.resultados || []).map((item) => ({ ...item, tipo: "MP" })),
        ];
        results.innerHTML = options.length ? options.map((item) => `<button type="button" data-manual-code="${escapeHtml(item.codigo)}">
            <span><b>${escapeHtml(item.codigo)}</b><em>${item.tipo}</em></span>
            <small>${escapeHtml(item.descripcion || "Sin descripción")}${item.codigo_cliente ? ` · Cliente: ${escapeHtml(item.codigo_cliente)}` : ""}</small>
        </button>`).join("") : '<span class="manual-search-state">No se encontraron piezas ni materias primas.</span>';
    } catch (error) {
        if (error.name !== "AbortError") results.innerHTML = `<span class="manual-search-state error">${escapeHtml(error.message)}</span>`;
    }
}

function chooseManualCode(event) {
    const option = event.target.closest("[data-manual-code]");
    if (!option) return;
    $("#manual-code-input").value = option.dataset.manualCode;
    hideManualCodeResults();
    $("#manual-form [name=cantidad]").focus();
}

function hideManualCodeResults() {
    $("#manual-code-results").classList.add("hidden");
}

async function addManual(event) {
    event.preventDefault();
    const form = event.target;
    if (!form.reportValidity()) return;
    const payload = Object.fromEntries(new FormData(form));
    payload.cantidad = Number(payload.cantidad);
    const button = form.querySelector("button");
    button.disabled = true;
    try {
        if (await mutate(`/api/inventarios/${inventoryId}/preconciliacion/movimientos`, "POST", payload)) {
            form.reset();
            hideManualCodeResults();
        }
    } finally { button.disabled = false; }
}

async function saveScrap(event) {
    const button = event.target.closest("[data-save-scrap]");
    if (!button) return;
    const card = button.closest("[data-code]");
    const input = button.closest(".scenario-calculation").querySelector("[data-scrap]");
    if (!input.reportValidity() || input.value === "") return;
    button.disabled = true;
    try {
        await mutate(`/api/inventarios/${inventoryId}/preconciliacion/scrap`, "PUT", { inicial_id: Number(button.dataset.saveScrap), codigo: card.dataset.code, cantidad: Number(input.value) });
    } finally { button.disabled = false; }
}
