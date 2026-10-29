const state = {
    racks: [], rack: null, selectedCoordinate: null,
    selectedArticle: null, articleTimer: null,
};
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    if (!response.ok) {
        let message = `Error ${response.status}`;
        try { message = (await response.json()).detail || message; } catch (_error) { /* sin JSON */ }
        throw new Error(message);
    }
    return response.status === 204 ? null : response.json();
}
function showToast(message, error = false) {
    const toast = $("#warehouse-toast");
    toast.textContent = message;
    toast.classList.toggle("error", error);
    toast.classList.remove("hidden");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => toast.classList.add("hidden"), 3200);
}
function formatNumber(value) {
    return Number(value || 0).toLocaleString("es-AR", { maximumFractionDigits: 3 });
}
const positionKey = (level, column, row, position) => `${level}-${column}-${row}-${position}`;
function locationCode(level, column, row, position) {
    return `${state.rack.codigo}-P${String(level).padStart(2, "0")}`
        + `-C${String(column).padStart(2, "0")}`
        + `-F${String(row).padStart(2, "0")}`
        + `-${String(position).padStart(2, "0")}`;
}
function totalPositions(rack) {
    return rack.niveles.reduce(
        (total, level) => total + rack.columnas * level.filas * level.divisiones, 0,
    );
}

async function loadRacks(preferredCode = "") {
    const container = $("#rack-list-content");
    container.innerHTML = '<p class="rack-loading">Cargando estanterías…</p>';
    try {
        const data = await api("/api/deposito/estanterias");
        state.racks = data.estanterias || [];
        renderRackList();
        const code = preferredCode || state.rack?.codigo || state.racks[0]?.codigo;
        if (code) await selectRack(code);
        else renderEmptyRack("Todavía no hay estanterías configuradas.");
    } catch (error) {
        container.innerHTML = `<div class="rack-store-error"><strong>No se pudo abrir el mapa</strong><span>${escapeHtml(error.message)}</span><small>Revisá que la carpeta data tenga permiso de escritura.</small></div>`;
        renderEmptyRack("No se pudo abrir el almacenamiento local del depósito.");
    }
}
function renderRackList() {
    const container = $("#rack-list-content");
    if (!state.racks.length) {
        container.innerHTML = '<p class="rack-loading">No hay estanterías. Tocá ＋ para crear una.</p>';
        return;
    }
    let currentSector = null;
    container.innerHTML = state.racks.map((rack) => {
        const sector = rack.sector || "Sin sector";
        const heading = sector !== currentSector
            ? `<div class="zone-label">${escapeHtml(sector)}</div>` : "";
        currentSector = sector;
        const active = rack.codigo === state.rack?.codigo ? " active" : "";
        return `${heading}<button class="rack-option${active}" data-rack="${escapeHtml(rack.codigo)}" type="button"><span>${escapeHtml(rack.codigo)}</span><small>${rack.ocupadas} ubicadas · ${formatNumber(rack.cantidad_total)} unidades</small><i>›</i></button>`;
    }).join("");
    $$(".rack-option").forEach((button) => {
        button.addEventListener("click", () => selectRack(button.dataset.rack));
    });
}
async function selectRack(code) {
    try {
        state.rack = await api(`/api/deposito/estanterias/${encodeURIComponent(code)}`);
        renderRackList();
        renderRack();
    } catch (error) { showToast(error.message, true); }
}
function renderEmptyRack(message) {
    $("#rack-grid").innerHTML = `<div class="rack-empty">${escapeHtml(message)}</div>`;
    $("#rack-title").textContent = "Mapa de estantería";
    $("#rack-description").textContent = "Configurá una estantería para comenzar.";
    updateMetrics(null);
}
function renderRack() {
    const rack = state.rack;
    if (!rack) return renderEmptyRack("Seleccioná una estantería.");
    const grid = $("#rack-grid");
    const contents = new Map(rack.ubicaciones.map((item) => [
        positionKey(item.nivel, item.columna, item.fila, item.posicion), item,
    ]));
    grid.style.setProperty("--rack-columns", rack.columnas);
    grid.innerHTML = '<div class="rack-corner"></div>'
        + Array.from({ length: rack.columnas }, (_, index) => `<div class="rack-column-label">Columna ${index + 1}</div>`).join("");
    [...rack.niveles].sort((a, b) => b.numero - a.numero).forEach((level) => {
        grid.insertAdjacentHTML("beforeend", `<div class="rack-floor-label"><strong>Piso ${level.numero}</strong><small>${escapeHtml(level.tipo)}</small></div>`);
        for (let column = 1; column <= rack.columnas; column += 1) {
            const bay = document.createElement("div");
            const cells = level.filas * level.divisiones;
            bay.className = `rack-bay${cells >= 8 ? " compact" : ""}`;
            bay.style.gridTemplateColumns = `repeat(${level.divisiones}, minmax(0, 1fr))`;
            bay.style.gridTemplateRows = `repeat(${level.filas}, minmax(0, 1fr))`;
            for (let row = 1; row <= level.filas; row += 1) {
                for (let position = 1; position <= level.divisiones; position += 1) {
                    const item = contents.get(positionKey(level.numero, column, row, position));
                    const button = document.createElement("button");
                    button.type = "button";
                    button.className = `rack-position ${item ? (item.estado === "VERIFICAR" ? "review" : "occupied") : "free"}`;
                    button.dataset.search = item ? `${item.codigo} ${item.codigo_cliente} ${item.descripcion} ${item.trazabilidad}`.toLowerCase() : "";
                    const shortCode = `F${row}-${position}`;
                    button.innerHTML = item
                        ? `<small class="position-code">${shortCode}</small><strong>${escapeHtml(item.codigo)}</strong><small>${escapeHtml(item.trazabilidad)}</small><span>${formatNumber(item.cantidad)} u.</span>`
                        : `<small class="position-code">${shortCode}</small><strong>Libre</strong>`;
                    button.title = locationCode(level.numero, column, row, position);
                    button.addEventListener("click", () => openLocation(
                        { level: level.numero, column, row, position }, item,
                    ));
                    bay.append(button);
                }
            }
            grid.append(bay);
        }
    });
    $("#rack-title").textContent = rack.nombre;
    $("#rack-description").textContent = `${rack.niveles.length} pisos · ${rack.columnas} columnas · ${totalPositions(rack)} ubicaciones configuradas`;
    updateMetrics(rack);
    applyMapSearch();
}
function updateMetrics(rack) {
    const positions = rack ? totalPositions(rack) : 0;
    const items = rack?.ubicaciones || [];
    $("#occupied-total").textContent = items.length;
    $("#occupied-detail").textContent = `de ${positions} disponibles`;
    $("#free-total").textContent = Math.max(0, positions - items.length);
    $("#quantity-total").textContent = formatNumber(items.reduce((sum, item) => sum + Number(item.cantidad || 0), 0));
    $("#review-total").textContent = items.filter((item) => item.estado === "VERIFICAR").length;
}
function applyMapSearch() {
    const query = $("#rack-search").value.trim().toLowerCase();
    let matches = 0;
    $$(".rack-position").forEach((position) => {
        const match = query.length >= 2 && position.dataset.search.includes(query);
        position.classList.toggle("match", match);
        if (match) matches += 1;
    });
    $("#search-result").classList.toggle("hidden", query.length < 2);
    if (query.length >= 2) {
        $("#search-result").textContent = matches
            ? `${matches} ubicación${matches === 1 ? "" : "es"} coincide${matches === 1 ? "" : "n"} con “${$("#rack-search").value.trim()}”.`
            : `No se encontraron ubicaciones para “${$("#rack-search").value.trim()}”.`;
    }
}

function openLocation(coordinate, item = null) {
    state.selectedCoordinate = coordinate;
    state.selectedArticle = item ? {
        codigo: item.codigo, descripcion: item.descripcion, codigo_cliente: item.codigo_cliente,
    } : null;
    $("#detail-location").textContent = locationCode(coordinate.level, coordinate.column, coordinate.row, coordinate.position);
    $("#article-type").value = item?.tipo_articulo || "PIEZA";
    $("#article-search").value = item?.codigo || "";
    $("#article-trace").value = item?.trazabilidad || "";
    $("#article-quantity").value = item?.cantidad || "";
    $("#article-status").value = item?.estado || "CONFIRMADA";
    $("#empty-location").classList.toggle("hidden", !item);
    $("#detail-current").classList.toggle("hidden", !item);
    $("#detail-current").innerHTML = item
        ? `<strong>${escapeHtml(item.codigo)}</strong><span>${escapeHtml(item.descripcion)}</span><small>${escapeHtml(item.codigo_cliente || "Sin código de cliente")}</small>` : "";
    renderSelectedArticle();
    $("#article-suggestions").classList.add("hidden");
    $("#position-sheet").classList.remove("hidden");
    $("#position-sheet").setAttribute("aria-hidden", "false");
}
function closeLocation() {
    $("#position-sheet").classList.add("hidden");
    $("#position-sheet").setAttribute("aria-hidden", "true");
}
function renderSelectedArticle() {
    const selected = $("#selected-article");
    if (!state.selectedArticle) {
        selected.classList.add("hidden"); selected.innerHTML = ""; return;
    }
    selected.innerHTML = `<strong>${escapeHtml(state.selectedArticle.codigo)}</strong><span>${escapeHtml(state.selectedArticle.descripcion || "Sin descripción")}</span><small>${escapeHtml(state.selectedArticle.codigo_cliente || "")}</small>`;
    selected.classList.remove("hidden");
}
async function searchArticles() {
    const query = $("#article-search").value.trim();
    const suggestions = $("#article-suggestions");
    if (query.length < 2) { suggestions.classList.add("hidden"); return; }
    const endpoint = $("#article-type").value === "PIEZA" ? "/api/busqueda/piezas" : "/api/busqueda/materiales";
    try {
        const data = await api(`${endpoint}?q=${encodeURIComponent(query)}&limite=12`);
        const results = data.resultados || [];
        suggestions.innerHTML = results.length
            ? results.map((item, index) => `<button type="button" data-result="${index}"><strong>${escapeHtml(item.codigo)}</strong><span>${escapeHtml(item.descripcion || "")}</span><small>${escapeHtml(item.codigo_cliente || item.unidad || "")}</small></button>`).join("")
            : '<p>No se encontraron códigos.</p>';
        suggestions.classList.remove("hidden");
        suggestions.querySelectorAll("button").forEach((button) => {
            button.addEventListener("click", () => {
                state.selectedArticle = results[Number(button.dataset.result)];
                $("#article-search").value = state.selectedArticle.codigo;
                suggestions.classList.add("hidden");
                renderSelectedArticle();
            });
        });
    } catch (error) {
        suggestions.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
        suggestions.classList.remove("hidden");
    }
}
async function saveLocation(event) {
    event.preventDefault();
    if (!state.rack || !state.selectedCoordinate) return;
    if (!state.selectedArticle) { showToast("Elegí una pieza o materia prima de la lista.", true); return; }
    const c = state.selectedCoordinate;
    const url = `/api/deposito/estanterias/${encodeURIComponent(state.rack.codigo)}/ubicaciones/${c.level}/${c.column}/${c.row}/${c.position}`;
    try {
        state.rack = await api(url, { method: "PUT", body: JSON.stringify({
            tipo_articulo: $("#article-type").value,
            codigo: state.selectedArticle.codigo,
            trazabilidad: $("#article-trace").value.trim(),
            cantidad: Number($("#article-quantity").value),
            estado: $("#article-status").value,
        }) });
        closeLocation(); await loadRacks(state.rack.codigo);
        showToast("Contenido guardado en la ubicación.");
    } catch (error) { showToast(error.message, true); }
}
async function emptyLocation() {
    if (!state.rack || !state.selectedCoordinate) return;
    if (!window.confirm("¿Vaciar esta ubicación? El registro actual se eliminará.")) return;
    const c = state.selectedCoordinate;
    const url = `/api/deposito/estanterias/${encodeURIComponent(state.rack.codigo)}/ubicaciones/${c.level}/${c.column}/${c.row}/${c.position}`;
    try {
        await api(url, { method: "DELETE" }); closeLocation();
        await loadRacks(state.rack.codigo); showToast("La ubicación quedó libre.");
    } catch (error) { showToast(error.message, true); }
}

function defaultLevels(floors) {
    return Array.from({ length: floors }, (_, index) => {
        const number = index + 1;
        return number <= 2
            ? { numero: number, tipo: number === 1 ? "BANDEJA" : "CAJA", filas: 2, divisiones: 4 }
            : { numero: number, tipo: "PALLET", filas: 1, divisiones: number === 3 ? 2 : 3 };
    });
}
function openConfig(createNew = false) {
    const rack = createNew ? null : state.rack;
    $("#config-code").value = rack?.codigo || "";
    $("#config-code").readOnly = Boolean(rack);
    $("#config-name").value = rack?.nombre || "";
    $("#config-sector").value = rack?.sector || "";
    $("#config-columns").value = rack?.columnas || 4;
    $("#config-floors").value = rack?.niveles.length || 5;
    renderLevelConfig(rack?.niveles || defaultLevels(5));
    $("#config-sheet").classList.remove("hidden");
    $("#config-sheet").setAttribute("aria-hidden", "false");
}
function closeConfig() {
    $("#config-sheet").classList.add("hidden");
    $("#config-sheet").setAttribute("aria-hidden", "true");
}
function readLevelConfig() {
    return $$(".level-config").map((card) => ({
        numero: Number(card.dataset.level),
        tipo: card.querySelector(".level-type").value,
        filas: Number(card.querySelector(".level-rows").value),
        divisiones: Number(card.querySelector(".level-divisions").value),
    }));
}
function renderLevelConfig(levels) {
    const container = $("#level-config-list");
    container.innerHTML = [...levels].sort((a, b) => b.numero - a.numero).map((level) => `
        <article class="level-config" data-level="${level.numero}">
            <div><strong>Piso ${level.numero}</strong><small class="level-capacity"></small></div>
            <label>Tipo<select class="level-type">
                <option value="PALLET" ${level.tipo === "PALLET" ? "selected" : ""}>Pallet</option>
                <option value="BANDEJA" ${level.tipo === "BANDEJA" ? "selected" : ""}>Bandeja</option>
                <option value="CAJA" ${level.tipo === "CAJA" ? "selected" : ""}>Caja chica</option>
                <option value="PERSONALIZADO" ${level.tipo === "PERSONALIZADO" ? "selected" : ""}>Personalizado</option>
            </select></label>
            <label>Filas por columna<input class="level-rows" type="number" min="1" max="8" value="${level.filas}"></label>
            <label>Divisiones por fila<input class="level-divisions" type="number" min="1" max="12" value="${level.divisiones}"></label>
        </article>`).join("");
    container.querySelectorAll("input, select").forEach((control) => control.addEventListener("input", updateConfigSummary));
    updateConfigSummary();
}
function resizeLevelConfig() {
    const floors = Math.max(1, Math.min(20, Number($("#config-floors").value) || 1));
    const current = new Map(readLevelConfig().map((level) => [level.numero, level]));
    renderLevelConfig(defaultLevels(floors).map((level) => current.get(level.numero) || level));
}
function updateConfigSummary() {
    const columns = Math.max(1, Number($("#config-columns").value) || 1);
    let total = 0;
    $$(".level-config").forEach((card) => {
        const capacity = columns * (Number(card.querySelector(".level-rows").value) || 0)
            * (Number(card.querySelector(".level-divisions").value) || 0);
        total += capacity;
        card.querySelector(".level-capacity").textContent = `${capacity} ubicaciones en el piso`;
    });
    $("#config-summary").innerHTML = `<span>Capacidad total estimada</span><strong>${total} ubicaciones</strong>`;
}
async function saveRackConfig(event) {
    event.preventDefault();
    const code = $("#config-code").value.trim().toUpperCase();
    const payload = {
        nombre: $("#config-name").value.trim(), sector: $("#config-sector").value.trim(),
        columnas: Number($("#config-columns").value), niveles: readLevelConfig(),
    };
    try {
        const rack = await api(`/api/deposito/estanterias/${encodeURIComponent(code)}`, {
            method: "PUT", body: JSON.stringify(payload),
        });
        closeConfig(); await loadRacks(rack.codigo);
        showToast("Distribución de la estantería guardada.");
    } catch (error) { showToast(error.message, true); }
}

$("#rack-search").addEventListener("input", applyMapSearch);
$("#print-rack").addEventListener("click", () => window.print());
$("#configure-rack").addEventListener("click", () => openConfig(false));
$("#add-rack").addEventListener("click", () => openConfig(true));
$("#close-sheet").addEventListener("click", closeLocation);
$("#sheet-backdrop").addEventListener("click", closeLocation);
$("#close-config").addEventListener("click", closeConfig);
$("#config-backdrop").addEventListener("click", closeConfig);
$("#location-form").addEventListener("submit", saveLocation);
$("#empty-location").addEventListener("click", emptyLocation);
$("#rack-config-form").addEventListener("submit", saveRackConfig);
$("#config-floors").addEventListener("input", resizeLevelConfig);
$("#config-columns").addEventListener("input", updateConfigSummary);
$("#article-type").addEventListener("change", () => {
    state.selectedArticle = null; $("#article-search").value = "";
    $("#article-suggestions").classList.add("hidden"); renderSelectedArticle();
});
$("#article-search").addEventListener("input", () => {
    state.selectedArticle = null; renderSelectedArticle();
    window.clearTimeout(state.articleTimer);
    state.articleTimer = window.setTimeout(searchArticles, 250);
});
loadRacks();
