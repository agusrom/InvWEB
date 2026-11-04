const inventory = JSON.parse(document.querySelector("#inventory-data").textContent);
const causeNames = JSON.parse(document.querySelector("#cause-data").textContent);
const settings = JSON.parse(document.querySelector("#settings-data").textContent);
const tolerance = Number(settings.tolerancia_pct ?? 5);
const target = Number(settings.objetivo_confiabilidad_pct ?? 90);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[char]));
const formatNumber = (value) => new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(Number(value || 0));
const signed = (value) => `${Number(value) > 0 ? "+" : ""}${formatNumber(value)}`;
const percent = (value) => value == null ? "—" : `${Number(value) > 0 ? "+" : ""}${formatNumber(value)}%`;

function calculate(system, physical, complete = true) {
    if (!complete || physical == null) return { system, physical: null, difference: null, deviation: null, ok: null };
    const difference = physical - system;
    const deviation = system === 0 ? (physical === 0 ? 0 : 100) : difference * 100 / system;
    return { system, physical, difference, deviation, ok: Math.abs(deviation) <= tolerance + 1e-9 };
}

function pieces() {
    const groups = new Map();
    inventory.items.forEach((item, index) => {
        if (!groups.has(item.codigo)) groups.set(item.codigo, {
            codigo: item.codigo,
            descripcion: item.descripcion,
            tipoEstructura: item.tipo_estructura || "INDEPENDIENTE",
            originalOrder: index,
            items: [],
        });
        groups.get(item.codigo).items.push(item);
        if (item.etapa !== "MATERIAL" && item.tipo_estructura) {
            groups.get(item.codigo).tipoEstructura = item.tipo_estructura;
        }
    });
    return [...groups.values()].map((group) => {
        const productive = group.items.filter((item) => ["PROCESO_GLOBAL", "OPERACION", "TERMINADO"].includes(item.etapa));
        const stockPt = group.items.filter((item) => item.etapa === "TERMINADO")
            .reduce((sum, item) => sum + Number(item.stock_sistema || 0), 0);
        const stockProcess = group.items.filter((item) => ["PROCESO_GLOBAL", "OPERACION"].includes(item.etapa))
            .reduce((sum, item) => sum + Number(item.stock_sistema || 0), 0);
        const stockMp = group.items.filter((item) => item.etapa === "MATERIAL")
            .reduce((sum, item) => sum + Number(item.stock_sistema || 0), 0);
        const complete = productive.length > 0 && productive.every((item) => item.conteo_fisico != null);
        const system = stockPt + stockProcess;
        const physical = complete ? productive.reduce((sum, item) => sum + Number(item.conteo_fisico || 0), 0) : null;
        return { ...group, stockPt, stockProcess, stockMp, ...calculate(system, physical, complete) };
    });
}

function simpleItems() {
    return inventory.items.map((item, index) => ({
        codigo: item.codigo, descripcion: item.descripcion, items: [item],
        tipoEstructura: item.tipo_estructura || "INDEPENDIENTE",
        originalOrder: index,
        vacios: item.conteo_vacios, llenos: item.conteo_llenos, rotos: item.conteo_rotos,
        stockPt: item.etapa === "TERMINADO" ? Number(item.stock_sistema || 0) : 0,
        stockProcess: ["PROCESO_GLOBAL", "OPERACION"].includes(item.etapa) ? Number(item.stock_sistema || 0) : 0,
        stockMp: item.etapa === "MATERIAL" ? Number(item.stock_sistema || 0) : 0,
        ...calculate(Number(item.stock_sistema || 0), item.conteo_fisico == null ? null : Number(item.conteo_fisico)),
    }));
}

function causeFor(row) {
    const codes = [...new Set(row.items.map((item) => item.causa_diferencia_codigo).filter(Boolean))];
    if (!codes.length) return row.ok === false ? "Sin informar" : "—";
    return codes.map((code) => causeNames[code] || code).join(" / ");
}

function commentFor(row) {
    const comments = [...new Set(row.items
        .map((item) => String(item.observaciones || "").trim())
        .filter(Boolean))];
    return comments.length ? comments.join(" / ") : "—";
}

const isMedia = inventory.modalidad_conteo === "MEDIOS";
const structureOrder = { PADRE: 0, SUBCONJUNTO: 1, HIJO: 2, INDEPENDIENTE: 3 };
const rows = (isMedia || inventory.categoria === "MATERIA_PRIMA" ? simpleItems() : pieces())
    .sort((a, b) => (
        (structureOrder[String(a.tipoEstructura).trim().toUpperCase()] ?? 3)
        - (structureOrder[String(b.tipoEstructura).trim().toUpperCase()] ?? 3)
        || a.originalOrder - b.originalOrder
    ));
// El resultado general replica exactamente la métrica que usa la pantalla PC:
// cada renglón no pendiente de stock participa del denominador, incluso si aún
// no fue contado. La tabla continúa agrupada por código para facilitar difusión.
const total = Number(inventory.items_evaluables || 0);
const evaluated = Number(inventory.items_evaluados || 0);
const correct = Number(inventory.items_ok || 0);
const differences = Math.max(evaluated - correct, 0);
const pending = Math.max(total - evaluated, 0);
const reliability = inventory.confiabilidad == null
    ? null
    : Number(inventory.confiabilidad);
if (rows.length > 34) document.body.classList.add("many-rows");
if (rows.length > 48) document.body.classList.add("very-many-rows");

document.querySelectorAll("[data-tolerance]").forEach((element) => { element.textContent = formatNumber(tolerance); });
document.querySelector("#target-label").textContent = `Objetivo ≥ ${formatNumber(target)}%`;
document.querySelector("#reliability").textContent = reliability == null ? "—" : `${formatNumber(reliability)}%`;
document.querySelector("#result-caption").textContent = reliability == null ? "Sin resultados" : reliability >= target ? "Satisfactorio" : "Requiere acciones";
document.querySelector("#general-result").classList.toggle("warning", reliability != null && reliability < target);
document.querySelector("#summary").innerHTML = `
    <div><span>Renglones evaluables</span><strong>${total}</strong></div>
    <div><span>Dentro de tolerancia</span><strong class="good">${correct}</strong></div>
    <div><span>Fuera de tolerancia</span><strong class="bad">${differences}</strong></div>
    <div><span>Pendientes</span><strong>${pending}</strong></div>`;
document.querySelector("#footer-result").textContent = differences
    ? `${differences} renglones requieren revisión con Producción`
    : "Todos los renglones evaluados están dentro de tolerancia";

document.querySelector("#table-head").innerHTML = isMedia
    ? "<th class='code-column'>Código interno</th><th class='description-column'>Descripción</th><th>Sistema</th><th>Vacíos</th><th>Llenos</th><th>Rotos</th><th>Total</th><th>Dif.</th><th>Desvío</th><th class='cause-column'>Causa</th><th class='comment-column'>Comentario</th>"
    : "<th class='code-column'>Código interno</th><th class='description-column'>Descripción</th><th>Stock PT</th><th>Stock proceso</th><th>Stock MP</th><th>Total sistema</th><th>Total físico</th><th>Diferencia</th><th>Desvío</th><th class='cause-column'>Causa</th><th class='comment-column'>Comentario</th>";
document.querySelector("#table-body").innerHTML = rows.map((row) => {
    const status = row.ok == null ? "pending" : row.ok ? "correct" : "difference";
    const parentClass = String(row.tipoEstructura).trim().toUpperCase() === "PADRE" ? " parent-row" : "";
    const parentLabel = parentClass ? '<small class="parent-label">Padre</small>' : "";
    const identity = `<td class="internal-code">${escapeHtml(row.codigo)}${parentLabel}</td><td class="description">${escapeHtml(row.descripcion)}</td>`;
    if (isMedia) return `<tr class="${status}${parentClass}">${identity}<td>${formatNumber(row.system)}</td><td>${row.vacios ?? "—"}</td><td>${row.llenos ?? "—"}</td><td>${row.rotos ?? "—"}</td><td>${row.physical == null ? "—" : formatNumber(row.physical)}</td><td class="result-value">${row.difference == null ? "—" : signed(row.difference)}</td><td class="result-value deviation-value">${percent(row.deviation)}</td><td class="cause">${escapeHtml(causeFor(row))}</td><td class="comment">${escapeHtml(commentFor(row))}</td></tr>`;
    return `<tr class="${status}${parentClass}">${identity}<td class="stock-detail">${formatNumber(row.stockPt)}</td><td class="stock-detail">${formatNumber(row.stockProcess)}</td><td class="stock-detail stock-mp">${formatNumber(row.stockMp)}</td><td class="system-total">${formatNumber(row.system)}</td><td>${row.physical == null ? "—" : formatNumber(row.physical)}</td><td class="result-value">${row.difference == null ? "—" : signed(row.difference)}</td><td class="result-value deviation-value">${percent(row.deviation)}</td><td class="cause">${escapeHtml(causeFor(row))}</td><td class="comment">${escapeHtml(commentFor(row))}</td></tr>`;
}).join("");

function sectorMetrics(label, stages) {
    const groups = new Map();
    inventory.items.filter((item) => stages.includes(item.etapa)).forEach((item) => {
        if (!groups.has(item.codigo)) groups.set(item.codigo, []);
        groups.get(item.codigo).push(item);
    });
    const sectorRows = [...groups.values()].map((items) => {
        const complete = items.every((item) => item.conteo_fisico != null);
        const system = items.reduce((sum, item) => sum + Number(item.stock_sistema || 0), 0);
        const physical = complete
            ? items.reduce((sum, item) => sum + Number(item.conteo_fisico || 0), 0)
            : null;
        return calculate(system, physical, complete);
    });
    const evaluatedRows = sectorRows.filter((row) => row.ok != null);
    const correctRows = evaluatedRows.filter((row) => row.ok).length;
    return {
        label,
        evaluated: evaluatedRows.length,
        correct: correctRows,
        value: evaluatedRows.length ? correctRows * 100 / evaluatedRows.length : null,
    };
}

const sectors = [
    sectorMetrics("Producto terminado", ["TERMINADO"]),
    sectorMetrics("En proceso", ["PROCESO_GLOBAL", "OPERACION"]),
    sectorMetrics("Materia prima", ["MATERIAL"]),
];
document.querySelector("#sector-chart").innerHTML = sectors.map((sector) => {
    const value = sector.value ?? 0;
    const level = sector.value == null ? "empty" : value >= target ? "good" : value >= Math.max(target - 20, 0) ? "medium" : "bad";
    return `<div class="sector-row ${level}">
        <div class="sector-label"><strong>${sector.label}</strong><span>${sector.evaluated ? `${sector.correct} de ${sector.evaluated} correctos` : "Sin datos evaluables"}</span></div>
        <div class="chart-track"><i style="width:${Math.max(value, sector.value == null ? 0 : 2)}%"></i><b>${sector.value == null ? "—" : `${Math.round(value)}%`}</b></div>
    </div>`;
}).join("");

const causeCounts = new Map();
rows.filter((row) => row.ok === false).forEach((row) => {
    const codes = new Set(row.items.map((item) => item.causa_diferencia_codigo).filter(Boolean));
    codes.forEach((code) => causeCounts.set(code, (causeCounts.get(code) || 0) + 1));
});
const causes = [...causeCounts.entries()].sort((a, b) => b[1] - a[1]);
const causeTotal = causes.reduce((sum, [, count]) => sum + count, 0);
document.querySelector("#causes-total").textContent = causeTotal ? `${causeTotal} causas informadas` : "Sin causas informadas";
document.querySelector("#cause-chart").innerHTML = causes.length ? causes.slice(0, 6).map(([code, count], index) => {
    const value = count * 100 / causeTotal;
    const label = causeNames[code] || code;
    return `<div class="cause-chart-row"><span class="cause-rank">${index + 1}</span><strong>${escapeHtml(label)}</strong><div class="chart-track"><i style="width:${value}%"></i></div><b>${Math.round(value)}%</b><small>${count}</small></div>`;
}).join("") : '<div class="analytics-empty">Todavía no hay causas informadas para analizar.</div>';

const direction = {
    shortage: rows.filter((row) => row.ok === false && row.difference < 0).length,
    surplus: rows.filter((row) => row.ok === false && row.difference > 0).length,
    correct: rows.filter((row) => row.ok === true).length,
};
const directionTotal = direction.shortage + direction.surplus + direction.correct;
const share = (value) => directionTotal ? value * 100 / directionTotal : 0;
document.querySelector("#direction-chart").innerHTML = `
    <div class="direction-total"><strong>${direction.shortage + direction.surplus}</strong><span>códigos fuera de tolerancia</span></div>
    <div class="stacked-bar" aria-label="Distribución de resultados">
        <i class="shortage" style="width:${share(direction.shortage)}%"></i>
        <i class="surplus" style="width:${share(direction.surplus)}%"></i>
        <i class="correct" style="width:${share(direction.correct)}%"></i>
    </div>
    <div class="direction-legend">
        <div><i class="shortage"></i><span>Faltantes</span><strong>${direction.shortage}</strong><small>${Math.round(share(direction.shortage))}%</small></div>
        <div><i class="surplus"></i><span>Sobrantes</span><strong>${direction.surplus}</strong><small>${Math.round(share(direction.surplus))}%</small></div>
        <div><i class="correct"></i><span>Correctos</span><strong>${direction.correct}</strong><small>${Math.round(share(direction.correct))}%</small></div>
    </div>`;

const critical = rows.filter((row) => row.ok === false)
    .sort((a, b) => Math.abs(b.deviation) - Math.abs(a.deviation))
    .slice(0, 6);
document.querySelector("#critical-list").innerHTML = critical.length ? critical.map((row, index) => {
    const comment = commentFor(row);
    const noComment = comment === "—";
    return `<div class="critical-row"><span>${index + 1}</span><div>
        <strong>${escapeHtml(row.codigo)}</strong>
        <small class="critical-description">${escapeHtml(row.descripcion)}</small>
        <small class="critical-comment ${noComment ? "empty" : ""}" title="${escapeHtml(noComment ? "Sin comentario" : comment)}">${noComment ? "Sin comentario" : `Comentario: ${escapeHtml(comment)}`}</small>
    </div><em title="Cantidad de diferencia">${signed(row.difference)}</em><b title="Porcentaje de desvío">${percent(row.deviation)}</b></div>`;
}).join("") : '<div class="analytics-empty">No hay códigos fuera de tolerancia.</div>';
