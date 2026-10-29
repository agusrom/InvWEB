const homeCacheKey = "inventory-mobile-home-cache-v1";
const state = { data: null, filter: "ABIERTO", selected: null, manualArticles: [], manualTimer: null };
const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    setDates();
    await loadData();
});

function bindEvents() {
    $("#show-list").addEventListener("click", () => switchView("list"));
    $("#show-create").addEventListener("click", () => switchView("create"));
    $("#inventory-search").addEventListener("input", renderInventories);
    document.querySelectorAll("[data-filter]").forEach((button) => button.addEventListener("click", () => {
        state.filter = button.dataset.filter;
        document.querySelectorAll("[data-filter]").forEach((item) => item.classList.toggle("active", item === button));
        renderInventories();
    }));
    $("#inventory-list").addEventListener("click", (event) => {
        const button = event.target.closest("[data-detail]");
        if (button) openDetail(Number(button.dataset.detail));
    });
    $("#create-mode").addEventListener("change", renderCreateMode);
    $("#manual-type").addEventListener("change", resetManualArticles);
    $("#manual-search").addEventListener("input", scheduleManualSearch);
    $("#manual-suggestions").addEventListener("click", (event) => {
        const button = event.target.closest("[data-manual-code]");
        if (button) selectManualArticle(button.dataset.manualCode, button.dataset.manualDescription || "");
    });
    $("#manual-selected").addEventListener("click", (event) => {
        const button = event.target.closest("[data-remove-manual]");
        if (button) removeManualArticle(button.dataset.removeManual);
    });
    $("#create-form").addEventListener("submit", createInventory);
    $("#close-detail").addEventListener("click", closeDetail);
    $("#detail-backdrop").addEventListener("click", closeDetail);
}

async function api(url, options = {}) {
    const response = await fetch(url, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
    const body = (response.headers.get("content-type") || "").includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new Error(body?.detail || "No se pudo completar la operación");
    return body;
}

async function loadData() {
    const cached = readHomeCache();
    if (cached) {
        state.data = cached;
        fillCreateOptions();
        renderInventories();
    }
    try {
        state.data = await api("/api/inicio-movil");
        localStorage.setItem(homeCacheKey, JSON.stringify(state.data));
        fillCreateOptions();
        renderInventories();
    } catch (error) {
        if (!state.data) $("#inventory-list").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    }
}

function readHomeCache() {
    try { return JSON.parse(localStorage.getItem(homeCacheKey) || "null"); }
    catch (_error) { return null; }
}

function fillCreateOptions() {
    $("#create-template").innerHTML = state.data.plantillas.filter((item) => item.activa).map((item) =>
        `<option value="${item.id}">${escapeHtml(item.cliente)} · ${escapeHtml(item.nombre)}</option>`
    ).join("");
    $("#people-list").innerHTML = (state.data.personas || []).map((item) =>
        `<option value="${escapeHtml(item.nombre)}"></option>`
    ).join("");
}

function renderInventories() {
    if (!state.data) return;
    const query = normalize($("#inventory-search").value);
    const items = state.data.inventarios.filter((item) => {
        const open = item.estado !== "Cerrado";
        if (state.filter === "ABIERTO" && !open) return false;
        if (state.filter === "CERRADO" && open) return false;
        return !query || normalize(`${item.codigo} ${item.cliente} ${item.responsable} ${item.fecha}`).includes(query);
    });
    $("#inventory-list").innerHTML = items.length ? items.map(inventoryCard).join("") : '<p class="empty">No hay inventarios para mostrar.</p>';
}

function inventoryCard(item) {
    const closed = item.estado === "Cerrado";
    const confidence = item.confiabilidad == null ? "—" : `${format(item.confiabilidad)}%`;
    return `<article class="inventory-card">
        <div class="card-head"><strong>${escapeHtml(item.codigo)}</strong><span class="badge ${closed ? "closed" : "open"}">${escapeHtml(item.estado)}</span></div>
        <h3>${escapeHtml(item.cliente)}</h3><p>${formatDate(item.fecha)} · ${escapeHtml(item.responsable)}</p>
        <div class="progress"><span style="width:${Number(item.progreso || 0)}%"></span></div>
        <div class="metric-row"><span>${item.progreso}% cargado</span><span>Confiabilidad ${confidence}</span></div>
        <div class="card-actions"><button data-detail="${item.id}">Ver resultados</button>${closed ? "" : `<a href="/inventarios/${item.id}/movil">Abrir conteo</a>`}</div>
    </article>`;
}

function openDetail(id) {
    const item = state.data.inventarios.find((candidate) => candidate.id === id);
    if (!item) return;
    state.selected = item;
    const counted = item.items.filter((row) => row.conteo_fisico !== null).length;
    const totalSystem = item.items.reduce((sum, row) => sum + Number(row.stock_sistema || 0), 0);
    const totalPhysical = item.items.reduce((sum, row) => sum + Number(row.conteo_fisico || 0), 0);
    const totalPercentage = item.confiabilidad == null ? null : Number(item.confiabilidad);
    const rows = item.items.map((row) => `<div class="detail-item">
        <div class="detail-item-title"><strong>${escapeHtml(row.codigo)}</strong><small>${escapeHtml(stageLabel(row))}</small></div>
        <div class="detail-metrics">
            <span><small>Sistema</small><strong>${format(row.stock_sistema)}</strong></span>
            <span><small>Físico</small><strong>${row.conteo_fisico == null ? "—" : format(row.conteo_fisico)}</strong></span>
            <span class="difference ${row.dentro_tolerancia === false ? "bad" : ""}"><small>Diferencia</small><strong>${row.diferencia == null ? "—" : signed(row.diferencia)}</strong></span>
            <span class="percentage ${row.dentro_tolerancia === false ? "bad" : ""}"><small>Desvío</small><strong>${row.desvio_porcentaje == null ? "—" : `${signed(row.desvio_porcentaje)}%`}</strong></span>
        </div>
    </div>`).join("");
    $("#detail-content").innerHTML = `<div class="detail-title"><h2>${escapeHtml(item.codigo)}</h2><p>${escapeHtml(item.cliente)} · ${escapeHtml(item.estado)}</p></div>
        <div class="summary-grid"><div><small>Renglones</small><strong>${counted}/${item.items.length}</strong></div><div><small>Sistema total</small><strong>${format(totalSystem)}</strong></div><div><small>Físico total</small><strong>${counted === 0 ? "—" : format(totalPhysical)}</strong></div><div class="total-percentage"><small>Confiabilidad</small><strong>${totalPercentage == null ? "—" : `${format(totalPercentage)}%`}</strong></div></div>
        <div class="detail-items">${rows}</div>`;
    $("#detail-sheet").classList.remove("hidden");
    $("#detail-sheet").setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
}

function closeDetail() { $("#detail-sheet").classList.add("hidden"); document.body.style.overflow = ""; }

function switchView(view) {
    $("#list-view").classList.toggle("hidden", view !== "list");
    $("#create-view").classList.toggle("hidden", view !== "create");
    $("#show-list").classList.toggle("active", view === "list");
    $("#show-create").classList.toggle("active", view === "create");
}

function renderCreateMode() {
    const mode = $("#create-mode").value;
    $("#template-field").classList.toggle("hidden", mode !== "PLANTILLA");
    $("#manual-fields").classList.toggle("hidden", mode !== "MANUAL");
    $("#cyclic-field").classList.toggle("hidden", mode !== "CICLICO");
}

function resetManualArticles() {
    state.manualArticles = [];
    $("#manual-search").value = "";
    $("#manual-suggestions").innerHTML = "";
    renderManualArticles();
}

function scheduleManualSearch() {
    window.clearTimeout(state.manualTimer);
    const query = $("#manual-search").value.trim();
    if (query.length < 2) {
        $("#manual-suggestions").innerHTML = "";
        return;
    }
    state.manualTimer = window.setTimeout(() => searchManualArticles(query), 230);
}

async function searchManualArticles(query) {
    const resource = $("#manual-type").value === "MATERIA_PRIMA" ? "materiales" : "piezas";
    try {
        const data = await api(`/api/busqueda/${resource}?q=${encodeURIComponent(query)}&limite=10`);
        const selected = new Set(state.manualArticles.map((item) => normalize(item.codigo)));
        const results = (data.resultados || []).filter((item) => !selected.has(normalize(item.codigo)));
        $("#manual-suggestions").innerHTML = results.map((item) => `<button type="button" data-manual-code="${escapeHtml(item.codigo)}" data-manual-description="${escapeHtml(item.descripcion || "")}"><strong>${escapeHtml(item.codigo)}</strong><span>${escapeHtml(item.descripcion || "Sin descripción")}</span></button>`).join("");
    } catch (error) { toast(error.message); }
}

function selectManualArticle(code, description) {
    if (!state.manualArticles.some((item) => normalize(item.codigo) === normalize(code))) {
        state.manualArticles.push({ codigo: code, descripcion: description });
    }
    $("#manual-search").value = "";
    $("#manual-suggestions").innerHTML = "";
    renderManualArticles();
    $("#manual-search").focus();
}

function removeManualArticle(code) {
    state.manualArticles = state.manualArticles.filter((item) => item.codigo !== code);
    renderManualArticles();
}

function renderManualArticles() {
    $("#manual-selected").innerHTML = state.manualArticles.length
        ? state.manualArticles.map((item) => `<div class="selected-chip"><strong>${escapeHtml(item.codigo)}</strong><button type="button" data-remove-manual="${escapeHtml(item.codigo)}">×</button></div>`).join("")
        : "<small>Todavía no agregaste códigos.</small>";
}

async function createInventory(event) {
    event.preventDefault();
    const mode = $("#create-mode").value;
    const payload = {
        modo: mode, fecha: $("#create-date").value, mes_cierre: `${$("#create-month").value}-01`,
        responsable: $("#create-owner").value.trim(), colaboradores: $("#create-collaborators").value.trim(),
        observaciones: $("#create-notes").value.trim(), ambito: "INTERNO", modalidad_conteo: "ESTANDAR",
        tipo_conteo: "GLOBAL", controla_remitos: false,
    };
    if (mode === "PLANTILLA") payload.plantilla_id = Number($("#create-template").value);
    if (mode === "CICLICO") payload.codigo_raiz = $("#cyclic-code").value.trim();
    if (mode === "MANUAL") {
        if (!state.manualArticles.length) return toast("Agregá al menos un código");
        payload.articulos_manual = state.manualArticles.map((item) => ({ codigo: item.codigo, tipo_articulo: $("#manual-type").value, contar_material: true }));
    }
    try {
        const created = await api("/api/inventarios", { method: "POST", body: JSON.stringify(payload) });
        toast(`${created.codigo} creado`);
        window.location.href = `/inventarios/${created.id}/movil`;
    } catch (error) { toast(error.message); }
}

function setDates() { const now = new Date(); const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000); $("#create-date").value = local.toISOString().slice(0, 10); $("#create-month").value = local.toISOString().slice(0, 7); }
function stageLabel(row) { if (row.etapa === "MATERIAL") return row.lote ? `Material · ${row.lote}` : "Material"; if (row.etapa === "TERMINADO") return "Terminado"; if (row.etapa === "PROCESO_GLOBAL") return "Proceso"; return row.titulo_operacion || `Operación ${row.operacion || ""}`; }
function normalize(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
function format(value) { return Number(value || 0).toLocaleString("es-AR", { maximumFractionDigits: 2 }); }
function signed(value) { const number = Number(value); return `${number > 0 ? "+" : ""}${format(number)}`; }
function formatDate(value) { if (!value) return "—"; const [year, month, day] = value.split("-"); return `${day}/${month}/${year}`; }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char])); }
let toastTimer; function toast(message) { const node = $("#toast"); node.textContent = message; node.classList.remove("hidden"); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.add("hidden"), 3200); }
