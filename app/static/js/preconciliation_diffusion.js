const inventory = JSON.parse(document.querySelector("#inventory-data").textContent);
const analysis = JSON.parse(document.querySelector("#analysis-data").textContent);
const scenario = JSON.parse(document.querySelector("#scenario-data").textContent);
const notes = JSON.parse(document.querySelector("#notes-data").textContent);
const movements = JSON.parse(document.querySelector("#movements-data").textContent);
const causeNames = JSON.parse(document.querySelector("#causes-data").textContent);
const settings = JSON.parse(document.querySelector("#settings-data").textContent);
const tolerance = Number(scenario.tolerancia ?? settings.tolerancia_pct ?? 5);
const target = Number(settings.objetivo_confiabilidad_pct ?? 90);
const rows = [...(scenario.filas || [])];

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[char]));
const formatNumber = (value) => new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(Number(value || 0));
const signed = (value) => `${Number(value || 0) > 0 ? "+" : ""}${formatNumber(value)}`;
const percent = (value) => value == null ? "—" : `${Number(value) > 0 ? "+" : ""}${formatNumber(value)}%`;
const formatDate = (value) => {
    const [year, month, day] = String(value || "").slice(0, 10).split("-");
    return day ? `${day}/${month}/${year}` : "—";
};

function noteFor(row) {
    return notes[row.codigo] || {};
}

function causeFor(row) {
    const code = String(noteFor(row).causa || "").trim();
    return code ? (causeNames[code] || code) : "Sin causa asignada";
}

function commentFor(row) {
    return String(noteFor(row).observacion || "").trim() || "—";
}

function statusFor(row) {
    const value = String(noteFor(row).estado || "PENDIENTE");
    return ({
        PENDIENTE: "Pendiente",
        RECONTAR: "Recontar",
        AJUSTAR_SISTEMA: "Ajustar sistema",
        REVISAR_MOVIMIENTOS: "Revisar movimientos",
        RESUELTO: "Resuelto",
    })[value] || value.replaceAll("_", " ");
}

const correct = rows.filter((row) => row.conciliacion_ok).length;
const differences = rows.length - correct;
const pendingAnalysis = rows.filter((row) => (
    !row.conciliacion_ok
    && String(noteFor(row).estado || "PENDIENTE") === "PENDIENTE"
)).length;
const reliability = rows.length ? correct * 100 / rows.length : null;

if (rows.length > 30) document.body.classList.add("many-rows");
if (rows.length > 48) document.body.classList.add("very-many-rows");
document.querySelectorAll("[data-tolerance]").forEach((element) => { element.textContent = formatNumber(tolerance); });
document.querySelector("#initial-inventory").textContent = scenario.inicial.codigo;
document.querySelector("#initial-date").textContent = formatDate(scenario.inicial.fecha);
document.querySelector("#analytics-period").textContent = `${scenario.inicial.codigo} → ${inventory.codigo} · ${analysis.nombre}`;
document.querySelector("#reliability").textContent = reliability == null ? "—" : `${formatNumber(reliability)}%`;
document.querySelector("#result-caption").textContent = reliability == null ? "Sin resultados" : reliability >= target ? "Satisfactorio" : "Requiere acciones";
document.querySelector("#general-result").classList.toggle("warning", reliability != null && reliability < target);
document.querySelector("#summary").innerHTML = `
    <div><span>Total de piezas</span><strong>${rows.length}</strong></div>
    <div><span>Dentro de tolerancia</span><strong class="good">${correct}</strong></div>
    <div><span>Fuera de tolerancia</span><strong class="bad">${differences}</strong></div>
    <div><span>Pendientes de análisis</span><strong class="pending">${pendingAnalysis}</strong></div>`;
document.querySelector("#footer-result").textContent = differences
    ? `${differences} piezas requieren revisión`
    : "Todas las piezas cierran dentro de tolerancia";

document.querySelector("#table-body").innerHTML = rows.map((row) => {
    const status = row.conciliacion_ok ? "correct" : "difference";
    return `<tr class="${status}">
        <td class="internal-code">${escapeHtml(row.codigo)}${row.codigo_cliente ? `<small>Cliente: ${escapeHtml(row.codigo_cliente)}</small>` : ""}</td>
        <td class="description">${escapeHtml(row.descripcion || "Sin descripción")}</td>
        <td>${formatNumber(row.fisico_inicial)}</td>
        <td class="positive">${signed(row.ingresos)}</td>
        <td class="negative">${signed(-Number(row.egresos || 0))}</td>
        <td class="negative">${signed(-Number(row.scrap || 0))}</td>
        <td>${formatNumber(row.esperado)}</td>
        <td>${formatNumber(row.conteo_explotado_actual ?? row.fisico_actual)}</td>
        <td class="result-value">${signed(row.diferencia_conciliacion)}</td>
        <td class="result-value">${percent(row.porcentaje_desvio_conciliacion)}</td>
        <td class="analysis"><strong>${escapeHtml(statusFor(row))}</strong><span>${escapeHtml(causeFor(row))}</span></td>
        <td class="comment">${escapeHtml(commentFor(row))}</td>
    </tr>`;
}).join("");

const critical = rows.filter((row) => !row.conciliacion_ok)
    .sort((a, b) => Math.abs(Number(b.diferencia_conciliacion || 0)) - Math.abs(Number(a.diferencia_conciliacion || 0)))
    .slice(0, 6);
document.querySelector("#critical-list").innerHTML = critical.length ? critical.map((row, index) => {
    const comment = commentFor(row);
    return `<div class="critical-row"><span>${index + 1}</span><div><strong>${escapeHtml(row.codigo)}</strong><small>${escapeHtml(row.descripcion || "Sin descripción")}</small><em>${escapeHtml(causeFor(row))}</em><p>${escapeHtml(comment === "—" ? "Sin comentario" : comment)}</p></div><b>${signed(row.diferencia_conciliacion)}</b><i>${percent(row.porcentaje_desvio_conciliacion)}</i></div>`;
}).join("") : '<div class="empty-state">No hay piezas fuera de tolerancia.</div>';

const causeCounts = new Map();
rows.filter((row) => !row.conciliacion_ok).forEach((row) => {
    const code = String(noteFor(row).causa || "").trim();
    if (code) causeCounts.set(code, (causeCounts.get(code) || 0) + 1);
});
const causes = [...causeCounts.entries()].sort((a, b) => b[1] - a[1]);
const causeTotal = causes.reduce((sum, [, count]) => sum + count, 0);
document.querySelector("#causes-total").textContent = causeTotal ? `${causeTotal} causas informadas` : "Sin causas informadas";
document.querySelector("#cause-chart").innerHTML = causes.length ? causes.slice(0, 6).map(([code, count], index) => {
    const value = count * 100 / causeTotal;
    return `<div class="cause-row"><span>${index + 1}</span><strong>${escapeHtml(causeNames[code] || code)}</strong><div><i style="width:${value}%"></i></div><b>${Math.round(value)}%</b><small>${count}</small></div>`;
}).join("") : '<div class="empty-state">Las piezas con diferencia todavía no tienen causas clasificadas.</div>';

const scenarioId = Number(scenario.inicial.id);
const scenarioMovements = movements.filter((movement) => (
    (movement.escenarios || []).map(Number).includes(scenarioId)
    && !(movement.excluidos || []).map(Number).includes(scenarioId)
));
const verified = scenarioMovements.filter((movement) => movement.verificado).length;
const manual = scenarioMovements.filter((movement) => movement.manual).length;
const corrected = scenarioMovements.filter((movement) => movement.cantidad_editada != null).length;
const verifiedPercentage = scenarioMovements.length ? verified * 100 / scenarioMovements.length : null;
document.querySelector("#audit-caption").textContent = `${verified}/${scenarioMovements.length} verificados`;
document.querySelector("#audit-chart").innerHTML = `
    <div class="audit-percentage"><strong>${verifiedPercentage == null ? "—" : `${formatNumber(verifiedPercentage)}%`}</strong><span>movimientos verificados</span></div>
    <div class="audit-track"><i style="width:${verifiedPercentage || 0}%"></i></div>
    <div class="audit-details"><span><b>${scenarioMovements.length}</b>Total</span><span><b>${scenarioMovements.length - verified}</b>Pendientes</span><span><b>${corrected}</b>Corregidos</span><span><b>${manual}</b>Manuales</span></div>`;

const direction = {
    shortage: rows.filter((row) => !row.conciliacion_ok && Number(row.diferencia_conciliacion) < 0).length,
    surplus: rows.filter((row) => !row.conciliacion_ok && Number(row.diferencia_conciliacion) > 0).length,
    correct,
};
const directionTotal = direction.shortage + direction.surplus + direction.correct;
const share = (value) => directionTotal ? value * 100 / directionTotal : 0;
document.querySelector("#direction-chart").innerHTML = `
    <div class="direction-total"><strong>${direction.shortage + direction.surplus}</strong><span>fuera de tolerancia</span></div>
    <div class="stacked-bar"><i class="shortage" style="width:${share(direction.shortage)}%"></i><i class="surplus" style="width:${share(direction.surplus)}%"></i><i class="correct" style="width:${share(direction.correct)}%"></i></div>
    <div class="direction-details"><span><i class="shortage"></i>Faltantes <b>${direction.shortage}</b></span><span><i class="surplus"></i>Sobrantes <b>${direction.surplus}</b></span><span><i class="correct"></i>Correctas <b>${direction.correct}</b></span></div>`;
