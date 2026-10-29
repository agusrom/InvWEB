const inventoryId = Number(document.body.dataset.inventoryId);
const queueKey = `inventory-mobile-queue-v1-${inventoryId}`;
const cacheKey = `inventory-mobile-cache-v1-${inventoryId}`;
const deviceKey = "inventory-mobile-device-v1";
const routeContextKey = `inventory-mobile-route-context-v1-${inventoryId}`;
const itemOrderKey = `inventory-mobile-item-order-v1-${inventoryId}`;

const mobileState = {
    data: null,
    selectedItemId: null,
    expandedGroups: new Set(),
    expandedStages: new Set(),
    queue: readJson(queueKey, []),
    syncing: false,
    device: getDeviceId(),
    materialTimer: null,
    articleType: "PIEZA",
    lotMaterialCode: null,
    lotPieceCode: null,
    mode: "ROUTE",
    routeContext: readJson(routeContextKey, { physical: "DISPONIBLE", system: "TERMINADO" }),
    expandedRouteItems: new Set(),
    expandedRouteMaterials: new Set(),
    loadedRouteHistories: new Set(),
    loadingRouteHistories: new Set(),
    selectingRouteItemId: null,
    selectedRouteBoxes: new Set(),
    quickEntry: false,
    entryPhysicalState: null,
    itemOrder: readJson(itemOrderKey, []),
};

const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", async () => {
    registerEvents();
    syncVisualViewport();
    await registerServiceWorker();
    await loadInventory();
    if (navigator.onLine) syncQueue();
});

function registerEvents() {
    $("#media-search").addEventListener("input", renderMediaResults);
    $("#add-media-code").addEventListener("click", openMaterialSheet);
    $("#media-results").addEventListener("click", (event) => {
        const saveButton = event.target.closest("[data-save-media]");
        if (saveButton) saveMediaItem(Number(saveButton.dataset.saveMedia));
        const deleteButton = event.target.closest("[data-delete-media]");
        if (deleteButton) deleteInventoryCode(Number(deleteButton.dataset.deleteMedia));
    });
    $("#media-results").addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || !event.target.closest("[data-media-kind]")) return;
        event.preventDefault();
        const card = event.target.closest("[data-media-card]");
        if (card) saveMediaItem(Number(card.dataset.mediaCard));
    });
    $("#physical-options").addEventListener("click", (event) => {
        const button = event.target.closest("[data-physical]");
        if (button) setRouteContext("physical", button.dataset.physical);
    });
    $("#system-options").addEventListener("click", (event) => {
        const button = event.target.closest("[data-system]");
        if (button) setRouteContext("system", button.dataset.system);
    });
    $("#route-item-search").addEventListener("input", renderRouteResults);
    $("#route-results").addEventListener("click", (event) => {
        const selectionButton = event.target.closest("[data-route-select-mode]");
        if (selectionButton) {
            toggleRouteSelection(Number(selectionButton.dataset.routeSelectMode));
            return;
        }
        const selectAllButton = event.target.closest("[data-route-select-all]");
        if (selectAllButton) {
            selectAllRouteBoxes(Number(selectAllButton.dataset.routeSelectAll));
            return;
        }
        const selectSameButton = event.target.closest("[data-route-select-same]");
        if (selectSameButton) {
            selectSameRouteBatch(Number(selectSameButton.dataset.routeSelectSame));
            return;
        }
        const deleteSelectedButton = event.target.closest("[data-route-delete-selected]");
        if (deleteSelectedButton) {
            deleteSelectedRouteBoxes(Number(deleteSelectedButton.dataset.routeDeleteSelected));
            return;
        }
        const deleteCodeButton = event.target.closest("[data-delete-route-code]");
        if (deleteCodeButton) {
            deleteInventoryCode(Number(deleteCodeButton.dataset.deleteRouteCode));
            return;
        }
        const deleteButton = event.target.closest("[data-delete-box]");
        if (deleteButton) {
            deleteBox(deleteButton.dataset.deleteBox);
            return;
        }
        const materialToggle = event.target.closest("[data-route-toggle-material]");
        if (materialToggle) {
            toggleRouteMaterial(materialToggle.dataset.routeToggleMaterial);
            return;
        }
        const addButton = event.target.closest("[data-route-add]");
        if (addButton) {
            addRouteInlineRecord(Number(addButton.dataset.routeAdd));
            return;
        }
        const toggleButton = event.target.closest("[data-route-toggle]");
        if (toggleButton) {
            toggleRouteHistory(Number(toggleButton.dataset.routeToggle));
            return;
        }
        const lotButton = event.target.closest("[data-route-add-lot]");
        if (lotButton) {
            openLotSheet(
                lotButton.dataset.routeAddLot,
                lotButton.dataset.routeLotPiece,
            );
            return;
        }
        const deleteLotButton = event.target.closest("[data-route-delete-lot]");
        if (deleteLotButton) deleteLot(Number(deleteLotButton.dataset.routeDeleteLot));
    });
    $("#route-results").addEventListener("change", (event) => {
        const checkbox = event.target.closest("[data-route-select-box]");
        if (!checkbox) return;
        setRouteBoxSelected(checkbox.dataset.routeSelectBox, checkbox.checked);
    });
    $("#route-results").addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || !event.target.closest("[data-route-quantity],[data-route-count]")) return;
        event.preventDefault();
        const card = event.target.closest("[data-route-card]");
        if (card) addRouteInlineRecord(Number(card.dataset.routeCard));
    });
    $("#route-recent").addEventListener("click", (event) => {
        const button = event.target.closest("[data-route-delete-box]");
        if (button) deleteBox(button.dataset.routeDeleteBox);
    });
    $("#item-search").addEventListener("input", renderItems);
    $("#sync-now").addEventListener("click", syncQueue);
    $("#item-list").addEventListener("click", (event) => {
        const groupButton = event.target.closest("[data-toggle-group]");
        if (groupButton) {
            toggleGroup(groupButton.dataset.toggleGroup);
            return;
        }
        const stageButton = event.target.closest("[data-toggle-stage]");
        if (stageButton) {
            toggleStage(stageButton.dataset.toggleStage);
            return;
        }
        const lotButton = event.target.closest("[data-add-lot]");
        if (lotButton) {
            openLotSheet(
                lotButton.dataset.addLot,
                lotButton.dataset.lotPiece,
            );
            return;
        }
        const deleteLotButton = event.target.closest("[data-delete-lot]");
        if (deleteLotButton) {
            deleteLot(Number(deleteLotButton.dataset.deleteLot));
            return;
        }
        const button = event.target.closest("[data-open-item]");
        if (button) openItem(Number(button.dataset.openItem));
    });
    $("#close-sheet").addEventListener("click", closeSheet);
    $("#sheet-backdrop").addEventListener("click", closeSheet);
    $("#box-form").addEventListener("submit", addBox);
    $("#box-quantity").addEventListener("input", updateBatchSummary);
    $("#box-count").addEventListener("input", updateBatchSummary);
    [$("#box-quantity"), $("#box-count")].forEach((input) => input.addEventListener("focus", () => {
        if (!mobileState.quickEntry) return;
        window.setTimeout(() => $("#add-box").scrollIntoView({ behavior: "smooth", block: "center" }), 220);
    }));
    $("#recent-boxes").addEventListener("click", (event) => {
        const button = event.target.closest("[data-delete-box]");
        if (button) deleteBox(button.dataset.deleteBox);
    });
    $("#add-material").addEventListener("click", openMaterialSheet);
    $("#add-route-article").addEventListener("click", openMaterialSheet);
    $("#close-material").addEventListener("click", closeMaterialSheet);
    $("#material-backdrop").addEventListener("click", closeMaterialSheet);
    $("#material-search").addEventListener("input", scheduleMaterialSearch);
    $("#material-suggestions").addEventListener("click", (event) => {
        const button = event.target.closest("[data-material-code]");
        if (button) addMaterialToInventory(button.dataset.materialCode);
    });
    $("#close-lot").addEventListener("click", closeLotSheet);
    $("#lot-backdrop").addEventListener("click", closeLotSheet);
    $("#lot-number").addEventListener("input", (event) => {
        event.target.value = event.target.value.replace(/\D/g, "").slice(0, 5);
    });
    $("#lot-form").addEventListener("submit", addLotToInventory);
    window.addEventListener("online", () => {
        updateConnectionState();
        syncQueue();
    });
    window.addEventListener("offline", updateConnectionState);
    if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", syncVisualViewport);
        window.visualViewport.addEventListener("scroll", syncVisualViewport);
    }
}

function syncVisualViewport() {
    if (!window.visualViewport) return;
    const viewport = window.visualViewport;
    const keyboardBottom = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
    document.documentElement.style.setProperty("--mobile-viewport-height", `${viewport.height}px`);
    document.documentElement.style.setProperty("--keyboard-bottom", `${keyboardBottom}px`);
}

async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
        await navigator.serviceWorker.register("/mobile-sw.js", { scope: "/" });
        await navigator.serviceWorker.ready;
        const cache = await caches.open("inventory-mobile-v843");
        await cache.add(window.location.href);
    } catch (_error) {
        // El conteo en línea sigue funcionando aunque el navegador no admita
        // el modo sin conexión.
    }
}

async function request(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
    });
    const type = response.headers.get("content-type") || "";
    const body = type.includes("application/json")
        ? await response.json()
        : null;
    if (!response.ok) {
        throw new Error(body?.detail || "No se pudo completar la operación");
    }
    return body;
}

async function loadInventory() {
    const cached = readJson(cacheKey, null);
    if (cached) {
        mobileState.data = cached;
        ensureStableItemOrder();
        renderAll();
    }
    try {
        const fresh = await request(`/api/inventarios/${inventoryId}/conteo-movil`);
        mobileState.data = fresh;
        reconcileQueueWithServer();
        applyPendingOperations();
        ensureStableItemOrder();
        saveCache();
        renderAll();
    } catch (error) {
        if (!mobileState.data) {
            renderFatal(error.message);
            updateConnectionState();
            return;
        }
        toast("Sin conexión: mostrando el último inventario guardado");
    }
}

function ensureStableItemOrder() {
    const currentIds = mobileState.data?.inventario?.items.map((item) => Number(item.id)) || [];
    const currentSet = new Set(currentIds);
    const kept = mobileState.itemOrder.map(Number).filter((itemId) => currentSet.has(itemId));
    const known = new Set(kept);
    currentIds.forEach((itemId) => {
        if (!known.has(itemId)) kept.push(itemId);
    });
    mobileState.itemOrder = kept;
    localStorage.setItem(itemOrderKey, JSON.stringify(kept));
}

function stableItemOrderMap() {
    return new Map(mobileState.itemOrder.map((itemId, index) => [Number(itemId), index]));
}

function reconcileQueueWithServer() {
    const serverUids = new Set(
        mobileState.data.cajas.map((box) => box.cliente_uid)
    );
    const before = mobileState.queue.length;
    mobileState.queue = mobileState.queue.filter((operation) => (
        operation.kind !== "ADD" || !serverUids.has(operation.cliente_uid)
    ));
    if (before !== mobileState.queue.length) saveQueue();
}

function applyPendingOperations() {
    mobileState.queue.forEach((operation) => {
        const item = itemById(operation.item_id);
        if (!item) return;
        if (operation.kind === "MEDIA_SAVE") {
            item.conteo_vacios = operation.conteo_vacios;
            item.conteo_llenos = operation.conteo_llenos;
            item.conteo_rotos = operation.conteo_rotos;
            item.conteo_fisico = operation.conteo_vacios + operation.conteo_llenos + operation.conteo_rotos;
        } else if (operation.kind === "ADD") {
            if (mobileState.data.cajas.some(
                (box) => box.cliente_uid === operation.cliente_uid
            )) return;
            item.conteo_fisico = Number(item.conteo_fisico || 0)
                + Number(operation.cantidad);
            item.total_cajas = Number(item.total_cajas || 0)
                + Number(operation.cantidad);
            item.cantidad_cajas = Number(item.cantidad_cajas || 0) + 1;
            mobileState.data.cajas.unshift({
                id: operation.local_id,
                cliente_uid: operation.cliente_uid,
                item_id: operation.item_id,
                cantidad: operation.cantidad,
                observacion: operation.observacion,
                capturado_en: operation.capturado_en,
                pending_local: true,
            });
        } else if (operation.kind === "DELETE") {
            const box = mobileState.data.cajas.find(
                (candidate) => String(candidate.id) === String(operation.box_id)
            );
            if (box?.pending_delete) return;
            if (box) box.pending_delete = true;
            item.conteo_fisico = Math.max(
                0,
                Number(item.conteo_fisico || 0) - Number(operation.cantidad),
            );
            item.total_cajas = Math.max(
                0,
                Number(item.total_cajas || 0) - Number(operation.cantidad),
            );
            item.cantidad_cajas = Math.max(
                0,
                Number(item.cantidad_cajas || 0) - 1,
            );
        } else if (operation.kind === "DELETE_BATCH") {
            const boxes = operation.boxes || [];
            boxes.forEach((entry) => {
                const box = mobileState.data.cajas.find(
                    (candidate) => String(candidate.id) === String(entry.box_id)
                );
                if (box) box.pending_delete = true;
            });
            const removedTotal = boxes.reduce(
                (total, entry) => total + Number(entry.cantidad || 0), 0
            );
            item.conteo_fisico = Math.max(0, Number(item.conteo_fisico || 0) - removedTotal);
            item.total_cajas = Math.max(0, Number(item.total_cajas || 0) - removedTotal);
            item.cantidad_cajas = Math.max(0, Number(item.cantidad_cajas || 0) - boxes.length);
        }
    });
}

function renderAll() {
    if (!mobileState.data) return;
    const inventory = mobileState.data.inventario;
    if (inventory.categoria === "MATERIA_PRIMA" && mobileState.routeContext.system !== "MATERIAL") {
        mobileState.routeContext.system = "MATERIAL";
        localStorage.setItem(routeContextKey, JSON.stringify(mobileState.routeContext));
    }
    $("#inventory-code").textContent = inventory.codigo;
    $("#inventory-client").textContent = inventory.cliente;
    document.title = `${inventory.codigo} · Conteo móvil`;
    const canAdd = inventory.estado !== "Cerrado";
    $("#add-material").classList.toggle("hidden", !canAdd);
    $("#add-route-article").classList.toggle("hidden", !canAdd);
    const media = inventory.modalidad_conteo === "MEDIOS";
    mobileState.mode = media ? "MEDIA" : mobileState.mode;
    $("#route-mode").classList.toggle("hidden", media);
    $("#piece-mode").classList.add("hidden");
    $("#media-mode").classList.toggle("hidden", !media);
    $("#add-media-code").classList.toggle("hidden", !canAdd);
    renderSummary();
    if (media) {
        renderMediaResults();
        updateConnectionState();
        return;
    }
    renderRouteContext();
    renderRouteResults();
    renderRouteRecent();
    renderSheet();
    updateConnectionState();
}

function mediaValue(item, kind) {
    const value = item[`conteo_${kind}`];
    return value == null ? "" : String(value);
}

function renderMediaResults() {
    if (!mobileState.data || mobileState.data.inventario.modalidad_conteo !== "MEDIOS") return;
    const inventory = mobileState.data.inventario;
    const query = normalize($("#media-search").value);
    const items = inventory.items.filter((item) => !query || normalize(
        `${item.codigo_cliente} ${item.codigo} ${item.descripcion}`
    ).includes(query));
    $("#media-results").innerHTML = items.length ? `
        <div class="route-results-head"><strong>${query ? "Resultados" : "Códigos disponibles"}</strong><span>${items.length}</span></div>
        ${items.map((item) => {
            const complete = [item.conteo_vacios, item.conteo_llenos, item.conteo_rotos].every((value) => value != null);
            const total = complete ? Number(item.conteo_vacios) + Number(item.conteo_llenos) + Number(item.conteo_rotos) : null;
            const difference = total == null ? null : total - Number(item.stock_sistema || 0);
            return `<article class="media-inline-card ${complete ? "counted" : ""}" data-media-card="${item.id}">
                <div class="media-code-head">
                    <div><small>Código cliente</small><strong>${escapeHtml(item.codigo_cliente || "Sin código de cliente")}</strong><span>Interno: ${escapeHtml(item.codigo)}</span><p>${escapeHtml(item.descripcion || "Sin descripción")}</p></div>
                    ${inventory.estado === "Cerrado" ? "" : `<button type="button" data-delete-media="${item.id}" aria-label="Eliminar código">⌫</button>`}
                </div>
                <div class="media-fields">
                    ${["vacios", "llenos", "rotos"].map((kind) => `<label>${kind[0].toUpperCase() + kind.slice(1)}<input data-media-kind="${kind}" type="number" inputmode="decimal" min="0" step="any" value="${mediaValue(item, kind)}" ${inventory.estado === "Cerrado" ? "disabled" : ""}></label>`).join("")}
                    <button type="button" data-save-media="${item.id}" ${inventory.estado === "Cerrado" ? "disabled" : ""}>✓</button>
                </div>
                <div class="media-metrics">
                    <span>Sistema <strong>${formatNumber(item.stock_sistema)}</strong></span>
                    <span>Total <strong>${total == null ? "—" : formatNumber(total)}</strong></span>
                    <span>Utilizables <strong>${item.conteo_vacios == null ? "—" : formatNumber(item.conteo_vacios)}</strong></span>
                    <span class="${difference ? "bad" : ""}">Diferencia <strong>${difference == null ? "—" : signedNumber(difference)}</strong></span>
                </div>
            </article>`;
        }).join("")}
    ` : '<div class="route-empty">No encontré medios con esa búsqueda.</div>';
}

function saveMediaItem(itemId) {
    const item = itemById(itemId);
    const card = document.querySelector(`[data-media-card="${itemId}"]`);
    const values = {};
    for (const kind of ["vacios", "llenos", "rotos"]) {
        const input = card?.querySelector(`[data-media-kind="${kind}"]`);
        if (!input || input.value === "" || Number(input.value) < 0) {
            toast("Completá Vacíos, Llenos y Rotos con valores mayores o iguales a cero");
            input?.focus();
            return;
        }
        values[`conteo_${kind}`] = Number(input.value);
    }
    if (!item) return;
    mobileState.queue = mobileState.queue.filter((operation) => !(operation.kind === "MEDIA_SAVE" && operation.item_id === itemId));
    mobileState.queue.push({ kind: "MEDIA_SAVE", item_id: itemId, ...values });
    item.conteo_vacios = values.conteo_vacios;
    item.conteo_llenos = values.conteo_llenos;
    item.conteo_rotos = values.conteo_rotos;
    item.conteo_fisico = values.conteo_vacios + values.conteo_llenos + values.conteo_rotos;
    saveQueue();
    saveCache();
    renderAll();
    toast(navigator.onLine ? "Medio guardado" : "Medio guardado en el celular");
    if (navigator.onLine) syncQueue();
}

function physicalLabel(value) {
    return { DISPONIBLE: "Disponible", LINEA: "En línea", SCRAP: "Scrap" }[value] || "Disponible";
}

function systemLabel(value) {
    return { MATERIAL: "MP", PROCESO: "Proceso", TERMINADO: "Terminado" }[value] || "Terminado";
}

function setRouteContext(field, value) {
    mobileState.routeContext[field] = value;
    localStorage.setItem(routeContextKey, JSON.stringify(mobileState.routeContext));
    renderRouteContext();
    renderRouteResults();
    renderSummary();
    $("#route-item-search").focus();
}

function renderRouteContext() {
    const { physical, system } = mobileState.routeContext;
    $("#route-context-label").textContent = `${physicalLabel(physical)} · ${systemLabel(system)}`;
    document.querySelectorAll("[data-physical]").forEach((button) => (
        button.classList.toggle("active", button.dataset.physical === physical)
    ));
    document.querySelectorAll("[data-system]").forEach((button) => (
        button.classList.toggle("active", button.dataset.system === system)
    ));
    const rawMaterialOnly = mobileState.data?.inventario.categoria === "MATERIA_PRIMA";
    document.querySelectorAll("[data-system]").forEach((button) => {
        button.disabled = rawMaterialOnly && button.dataset.system !== "MATERIAL";
    });
    const isMaterial = system === "MATERIAL";
    $("#add-route-article").textContent = isMaterial ? "＋ Agregar código de MP" : "＋ Agregar código de pieza";
}

function routeItemCode(item) {
    return item.etapa === "MATERIAL" ? (item.codigo_material || item.codigo) : item.codigo;
}

function routeCountStatus(item) {
    const records = Number(item.cantidad_cajas || 0);
    if (records) return `${records} registro${records === 1 ? "" : "s"}`;
    return item.conteo_fisico !== null ? "Contado" : "Pendiente";
}

function canDeleteRouteCode(item) {
    if (item.etapa !== "MATERIAL") return true;
    return normalize(item.codigo) === normalize(item.codigo_material || item.codigo);
}

function routeStructureRole(item) {
    const codigoMaterial = normalize(item.codigo_material || (
        stageKey(item) === "MATERIAL" ? item.codigo : ""
    ));
    const piezas = new Set(
        mobileState.data.inventario.items
            .filter((candidate) => (
                candidate.etapa !== "MATERIAL"
                && codigoMaterial
                && normalize(candidate.codigo_material) === codigoMaterial
            ))
            .map((candidate) => candidate.codigo),
    );
    if (piezas.size > 1) return { key: "shared", label: "Grupo MP" };
    if (stageKey(item) === "MATERIAL") return { key: "material", label: "MP" };
    return structureRole(item.tipo_estructura);
}

function routeHistoryToolsHtml(item, soloLote = false) {
    const inventory = mobileState.data.inventario;
    if (inventory.estado === "Cerrado") return "";
    const isMaterialLot = item.etapa === "MATERIAL";
    const materialCode = String(item.codigo_material || item.codigo || "");
    const actions = `
        ${isMaterialLot && !soloLote ? `<button type="button" data-route-add-lot="${escapeHtml(materialCode)}" data-route-lot-piece="${escapeHtml(item.codigo)}">＋ Agregar lote</button>` : ""}
        ${isMaterialLot && item.lote ? `<button class="danger" type="button" data-route-delete-lot="${item.id}">Eliminar lote ${escapeHtml(item.lote)}</button>` : ""}
        ${!soloLote && canDeleteRouteCode(item) ? `<button class="danger" type="button" data-delete-route-code="${item.id}">Eliminar código</button>` : ""}
    `.trim();
    return actions ? `<div class="route-history-tools">${actions}</div>` : "";
}

function routeHistoryHtml(item, soloLote = false) {
    const boxes = mobileState.data.cajas
        .filter((box) => box.item_id === item.id && !box.pending_delete)
        .sort((left, right) => String(right.capturado_en).localeCompare(String(left.capturado_en)));
    const selecting = mobileState.selectingRouteItemId === Number(item.id);
    const rows = boxes.length
        ? boxes.map((box, index) => boxRow(box, boxes.length - index, selecting)).join("")
        : '<div class="route-history-empty">No hay registros móviles en este renglón.</div>';
    const physical = physicalLabel(mobileState.routeContext.physical);
    const selectedCount = boxes.filter((box) => mobileState.selectedRouteBoxes.has(String(box.id))).length;
    return `<div class="route-detail-summary">
        <span>Físico <strong>${item.conteo_fisico == null ? "—" : formatNumber(item.conteo_fisico)}</strong></span>
        <span>Sistema <strong>${formatNumber(item.stock_sistema)}</strong></span>
        <span>Registros <strong>${Number(item.cantidad_cajas || 0)}</strong></span>
    </div>
    <label class="route-inline-note">Observación para la próxima carga
        <input data-route-note type="text" maxlength="220" autocomplete="off" placeholder="${escapeHtml(physical)} · comentario opcional">
    </label>
    <div class="route-history-title"><div><strong>Registros cargados</strong><span>Ubicación física y cantidad</span></div>${boxes.length ? `<button type="button" data-route-select-mode="${item.id}">${selecting ? "Cancelar" : "Seleccionar"}</button>` : ""}</div>
    ${selecting ? `<div class="route-selection-tools">
        <button type="button" data-route-select-all="${item.id}">Seleccionar todos</button>
        <button type="button" data-route-select-same="${item.id}">Misma carga</button>
        <button class="danger" type="button" data-route-delete-selected="${item.id}" ${selectedCount ? "" : "disabled"}>Eliminar ${selectedCount || ""}</button>
    </div>` : ""}
    ${rows}
    ${routeHistoryToolsHtml(item, soloLote)}`;
}

function boxesForRouteItem(itemId) {
    return mobileState.data.cajas.filter((box) => (
        Number(box.item_id) === Number(itemId) && !box.pending_delete
    ));
}

function toggleRouteSelection(itemId) {
    if (mobileState.selectingRouteItemId === itemId) {
        mobileState.selectingRouteItemId = null;
        mobileState.selectedRouteBoxes.clear();
    } else {
        mobileState.selectingRouteItemId = itemId;
        mobileState.selectedRouteBoxes.clear();
    }
    refreshRouteItem(itemId);
}

function setRouteBoxSelected(boxId, selected) {
    if (selected) mobileState.selectedRouteBoxes.add(String(boxId));
    else mobileState.selectedRouteBoxes.delete(String(boxId));
    if (mobileState.selectingRouteItemId != null) {
        refreshRouteItem(mobileState.selectingRouteItemId);
    }
}

function selectAllRouteBoxes(itemId) {
    const boxes = boxesForRouteItem(itemId);
    const allSelected = boxes.length && boxes.every((box) => (
        mobileState.selectedRouteBoxes.has(String(box.id))
    ));
    mobileState.selectedRouteBoxes.clear();
    if (!allSelected) boxes.forEach((box) => mobileState.selectedRouteBoxes.add(String(box.id)));
    refreshRouteItem(itemId);
}

function selectSameRouteBatch(itemId) {
    const boxes = boxesForRouteItem(itemId);
    const selected = boxes.find((box) => mobileState.selectedRouteBoxes.has(String(box.id)));
    if (!selected) {
        toast("Marcá primero un registro de la carga que querés seleccionar");
        return;
    }
    const batchKey = `${selected.capturado_en}|${selected.cantidad}|${selected.observacion || ""}`;
    boxes.forEach((box) => {
        const candidateKey = `${box.capturado_en}|${box.cantidad}|${box.observacion || ""}`;
        if (candidateKey === batchKey) mobileState.selectedRouteBoxes.add(String(box.id));
    });
    refreshRouteItem(itemId);
}

function deleteSelectedRouteBoxes(itemId) {
    const selectedIds = [...mobileState.selectedRouteBoxes];
    deleteBoxesTogether(itemId, selectedIds);
}

async function toggleRouteHistory(itemId) {
    if (mobileState.expandedRouteItems.has(itemId)) {
        mobileState.expandedRouteItems.delete(itemId);
        refreshRouteItem(itemId);
        return;
    }
    mobileState.expandedRouteItems.add(itemId);
    refreshRouteItem(itemId);
    if (!navigator.onLine || mobileState.loadedRouteHistories.has(itemId)
        || mobileState.loadingRouteHistories.has(itemId)) return;
    mobileState.loadingRouteHistories.add(itemId);
    try {
        const response = await request(`/api/inventarios/${inventoryId}/conteo-movil/cajas/${itemId}`);
        const localPending = mobileState.data.cajas.filter((box) => (
            Number(box.item_id) === itemId && (box.pending_local || box.pending_delete)
        ));
        const pendingUids = new Set(localPending.map((box) => box.cliente_uid).filter(Boolean));
        const pendingIds = new Set(localPending.map((box) => String(box.id)));
        const remoteBoxes = (response.cajas || []).filter((box) => (
            !pendingUids.has(box.cliente_uid) && !pendingIds.has(String(box.id))
        ));
        mobileState.data.cajas = [
            ...localPending,
            ...remoteBoxes,
            ...mobileState.data.cajas.filter((box) => Number(box.item_id) !== itemId),
        ];
        mobileState.loadedRouteHistories.add(itemId);
        saveCache();
        refreshRouteItem(itemId);
    } catch (_error) {
        // El historial que ya está en el equipo sigue disponible si la señal falla.
    } finally {
        mobileState.loadingRouteHistories.delete(itemId);
    }
}

function routeInlineCardHtml(item) {
    const expanded = mobileState.expandedRouteItems.has(item.id);
    const role = routeStructureRole(item);
    const clientCode = item.codigo_cliente
        ? `<span class="route-client-code">Cliente ${escapeHtml(item.codigo_cliente)}</span>`
        : "";
    return `<article class="route-inline-card role-${role.key} ${item.conteo_fisico !== null ? "counted" : ""} ${expanded ? "expanded" : ""}" data-route-card="${item.id}">
        <div class="route-inline-main">
            <div class="route-inline-identity">
                <div class="route-inline-code"><strong>${escapeHtml(routeItemCode(item))}</strong><em class="structure-role role-${role.key}">${role.label}</em></div>
                <small>${escapeHtml(item.descripcion || "Sin descripción")}</small>
                <div class="route-inline-meta">${clientCode}<span>${escapeHtml(stageLabel(item))}</span><span>${routeCountStatus(item)}</span><span>Sist. ${formatNumber(item.stock_sistema)}</span></div>
            </div>
            <label>Cant.<input data-route-quantity type="number" inputmode="numeric" min="1" step="1" aria-label="Cantidad"></label>
            <label>Reg.<input data-route-count type="number" inputmode="numeric" min="1" max="100" step="1" value="1" aria-label="Registros iguales"></label>
            <button class="route-inline-add" type="button" data-route-add="${item.id}" aria-label="Guardar registro">＋</button>
            <button class="route-inline-toggle" type="button" data-route-toggle="${item.id}" aria-label="${expanded ? "Ocultar" : "Ver"} registros">⌄</button>
        </div>
        <div class="route-inline-history ${expanded ? "" : "hidden"}">${routeHistoryHtml(item)}</div>
    </article>`;
}

function routeMaterialLotCardHtml(item) {
    const expanded = mobileState.expandedRouteItems.has(item.id);
    const role = routeStructureRole(item);
    const description = materialLotDescription(item) || item.descripcion || "Sin descripción";
    return `<article class="route-inline-card material-lot-route role-${role.key} ${item.conteo_fisico !== null ? "counted" : ""} ${expanded ? "expanded" : ""}" data-route-card="${item.id}">
        <div class="route-inline-main">
            <div class="route-inline-identity">
                <div class="route-inline-code"><strong>Lote ${escapeHtml(item.lote || "Sin lote")}</strong></div>
                <small>${escapeHtml(description)}</small>
                <div class="route-inline-meta"><span>${routeCountStatus(item)}</span><span>Sist. ${formatNumber(item.stock_sistema)}</span><span>Fís. ${item.conteo_fisico == null ? "—" : formatNumber(item.conteo_fisico)}</span></div>
            </div>
            <label>Cant.<input data-route-quantity type="number" inputmode="numeric" min="1" step="1" aria-label="Cantidad"></label>
            <label>Reg.<input data-route-count type="number" inputmode="numeric" min="1" max="100" step="1" value="1" aria-label="Registros iguales"></label>
            <button class="route-inline-add" type="button" data-route-add="${item.id}" aria-label="Guardar registro">＋</button>
            <button class="route-inline-toggle" type="button" data-route-toggle="${item.id}" aria-label="${expanded ? "Ocultar" : "Ver"} registros">⌄</button>
        </div>
        <div class="route-inline-history ${expanded ? "" : "hidden"}">${routeHistoryHtml(item, true)}</div>
    </article>`;
}

function routeMaterialGroups(items, originalOrder, query) {
    const groups = new Map();
    items.forEach((item) => {
        if (item.etapa !== "MATERIAL") return;
        const code = normalize(item.codigo_material || item.codigo);
        if (!groups.has(code)) groups.set(code, { code, items: [], order: Number.MAX_SAFE_INTEGER });
        const group = groups.get(code);
        group.items.push(item);
        group.order = Math.min(
            group.order,
            originalOrder.get(Number(item.id)) ?? Number.MAX_SAFE_INTEGER,
        );
    });
    return [...groups.values()].filter((group) => (
        !query || group.items.some((item) => normalize(
            `${routeItemCode(item)} ${item.codigo} ${item.descripcion} ${item.lote} ${item.titulo_operacion}`,
        ).includes(query))
    )).sort((left, right) => left.order - right.order);
}

function routeMaterialSummaryCardHtml(group) {
    const expanded = mobileState.expandedRouteMaterials.has(group.code);
    const first = group.items[0];
    const role = routeStructureRole(first);
    const system = stockSistemaLineasMovil(group.items);
    const lotGroups = groupMaterialLotsMovil(group.items);
    const physicalValues = lotGroups.map((items) => {
        const values = items
            .map((item) => item.conteo_fisico)
            .filter((value) => value !== null)
            .map(Number);
        return values.length ? Math.max(...values) : null;
    });
    const complete = physicalValues.every((value) => value !== null);
    const physical = complete
        ? physicalValues.reduce((sum, value) => sum + Number(value), 0)
        : null;
    const records = group.items.reduce(
        (sum, item) => sum + Number(item.cantidad_cajas || 0),
        0,
    );
    const pieces = [...new Set(
        mobileState.data.inventario.items
            .filter((item) => item.etapa !== "MATERIAL" && normalize(item.codigo_material) === group.code)
            .map((item) => item.codigo),
    )];
    return `<article class="route-material-summary role-${role.key} ${complete ? "counted" : ""} ${expanded ? "expanded" : ""}">
        <div class="route-material-summary-main">
            <div class="route-inline-identity">
                <div class="route-inline-code"><strong>${escapeHtml(group.code)}</strong><em class="structure-role role-${role.key}">${role.label}</em></div>
                <small>${escapeHtml(materialLotDescription(first) || first.descripcion || "Sin descripción")}</small>
                ${pieces.length > 1 ? `<span class="route-shared-pieces">${pieces.map(escapeHtml).join(" · ")}</span>` : ""}
                <div class="route-inline-meta"><span>${lotGroups.length} lotes</span><span>${records} reg.</span>${pieces.length > 1 ? `<span>${pieces.length} piezas</span>` : ""}</div>
            </div>
            <div class="route-material-totals"><span>Sistema <strong>${formatNumber(system)}</strong></span><span>Físico <strong>${physical === null ? "—" : formatNumber(physical)}</strong></span></div>
            <button class="route-inline-toggle" type="button" data-route-toggle-material="${escapeHtml(group.code)}" aria-label="${expanded ? "Ocultar" : "Ver"} lotes">⌄</button>
        </div>
        <div class="route-material-lots ${expanded ? "" : "hidden"}">
            <div class="route-material-lots-head"><strong>Lotes de ${escapeHtml(group.code)}</strong><span>Elegí el lote antes de cargar</span></div>
            ${lotGroups.map((items) => [...items].sort((a, b) => (
                Number(b.stock_sistema || 0) - Number(a.stock_sistema || 0)
                || Number(b.cantidad_cajas || 0) - Number(a.cantidad_cajas || 0)
            ))[0]).map(routeMaterialLotCardHtml).join("")}
            ${mobileState.data.inventario.estado === "Cerrado" ? "" : `<button class="inline-add-lot" type="button" data-route-add-lot="${escapeHtml(group.code)}" data-route-lot-piece="${escapeHtml(first.codigo)}">＋ Agregar lote</button>`}
        </div>
    </article>`;
}

function groupMaterialLotsMovil(items) {
    const groups = new Map();
    items.forEach((item) => {
        const key = `${normalize(item.codigo_material || item.codigo)}::${item.lote || ""}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(item);
    });
    return [...groups.values()];
}

function stockSistemaLineasMovil(items) {
    const stocks = new Map();
    items.forEach((item) => {
        const key = `${normalize(item.codigo_material || item.codigo)}::${item.lote || ""}`;
        stocks.set(key, Math.max(stocks.get(key) || 0, Number(item.stock_sistema || 0)));
    });
    return [...stocks.values()].reduce((sum, value) => sum + value, 0);
}

function toggleRouteMaterial(code) {
    if (mobileState.expandedRouteMaterials.has(code)) {
        mobileState.expandedRouteMaterials.delete(code);
    } else {
        mobileState.expandedRouteMaterials.add(code);
    }
    renderRouteResults();
}

function refreshRouteItem(itemId) {
    const currentCard = document.querySelector(`[data-route-card="${itemId}"]`);
    const item = itemById(itemId);
    if (!item || stageKey(item) !== mobileState.routeContext.system) return;
    if (item.etapa === "MATERIAL") {
        renderRouteResults();
        return;
    }
    if (!currentCard) return;
    currentCard.outerHTML = routeInlineCardHtml(item);
}

function renderRouteResults() {
    if (!mobileState.data) return;
    const query = normalize($("#route-item-search").value);
    const system = mobileState.routeContext.system;
    const originalOrder = stableItemOrderMap();
    if (system === "MATERIAL") {
        const groups = routeMaterialGroups(
            mobileState.data.inventario.items,
            originalOrder,
            query,
        ).slice(0, 250);
        $("#route-results").innerHTML = groups.length ? `
            <div class="route-results-head"><strong>${query ? "Resultados" : "Códigos disponibles"}</strong><span>${groups.length}</span></div>
            ${groups.map(routeMaterialSummaryCardHtml).join("")}
        ` : '<div class="route-empty">No hay códigos de MP para esa búsqueda.</div>';
        return;
    }
    const matches = mobileState.data.inventario.items.filter((item) => (
        stageKey(item) === system
        && (!query || normalize(`${routeItemCode(item)} ${item.codigo} ${item.codigo_cliente} ${item.descripcion} ${item.operacion} ${item.lote}`).includes(query))
    )).sort((left, right) => (
        (originalOrder.get(Number(left.id)) ?? Number.MAX_SAFE_INTEGER)
        - (originalOrder.get(Number(right.id)) ?? Number.MAX_SAFE_INTEGER)
    )).slice(0, 250);
    $("#route-results").innerHTML = matches.length ? `
        <div class="route-results-head"><strong>${query ? "Resultados" : "Códigos disponibles"}</strong><span>${matches.length}</span></div>
        ${matches.map(routeInlineCardHtml).join("")}
    ` : `<div class="route-empty">No hay renglones de ${systemLabel(system)} para esa búsqueda.</div>`;
}

async function deleteInventoryCode(itemId) {
    const item = itemById(itemId);
    if (!item) return;
    const code = item.codigo;
    const itemIds = mobileState.data.inventario.items
        .filter((candidate) => normalize(candidate.codigo) === normalize(code))
        .map((candidate) => candidate.id);
    if (mobileState.data.inventario.modalidad_conteo === "MEDIOS" && itemIds.some((id) => {
        const candidate = itemById(id);
        return candidate && [candidate.conteo_vacios, candidate.conteo_llenos, candidate.conteo_rotos].some((value) => value != null);
    })) {
        toast("El código ya tiene conteo. Borrá sus valores desde la PC antes de eliminarlo.");
        return;
    }
    if (mobileState.queue.some((operation) => (
        operation.kind === "DELETE" && itemIds.includes(Number(operation.item_id))
    ))) {
        if (navigator.onLine) await syncQueue();
        if (mobileState.queue.some((operation) => (
            operation.kind === "DELETE" && itemIds.includes(Number(operation.item_id))
        ))) {
            toast("Primero sincronizá la eliminación de sus registros.");
            return;
        }
    }
    const hasRecords = mobileState.data.cajas.some((box) => (
        itemIds.includes(Number(box.item_id)) && !box.pending_delete
    )) || mobileState.queue.some((operation) => (
        operation.kind === "ADD" && itemIds.includes(Number(operation.item_id))
    ));
    if (hasRecords) {
        toast("El código tiene registros. Eliminalos primero y volvé a intentarlo.");
        return;
    }
    const detail = mobileState.data.inventario.modalidad_conteo === "MEDIOS"
        ? "Se quitará este medio del inventario."
        : "Se quitarán todos sus renglones de MP, Proceso y Terminado.";
    if (!window.confirm(`¿Eliminar ${code} del inventario?\n\n${detail}`)) return;
    try {
        const updated = await request(`/api/inventarios/${inventoryId}/eliminar-codigo-movil`, {
            method: "POST",
            body: JSON.stringify({ item_ids: itemIds }),
        });
        mobileState.data.inventario = updated;
        mobileState.data.cajas = mobileState.data.cajas.filter((box) => !itemIds.includes(Number(box.item_id)));
        itemIds.forEach((id) => mobileState.expandedRouteItems.delete(id));
        saveCache();
        renderAll();
        toast(`${code} fue eliminado del inventario`);
    } catch (error) {
        toast(error.message);
    }
}

function addRouteInlineRecord(itemId) {
    const item = itemById(itemId);
    const card = document.querySelector(`[data-route-card="${itemId}"]`);
    const quantity = Number(card?.querySelector("[data-route-quantity]")?.value);
    const boxCount = Number(card?.querySelector("[data-route-count]")?.value);
    if (!item || !Number.isInteger(quantity) || quantity <= 0) {
        toast("Ingresá una cantidad entera mayor que cero");
        card?.querySelector("[data-route-quantity]")?.focus();
        return;
    }
    if (!Number.isInteger(boxCount) || boxCount <= 0 || boxCount > 100) {
        toast("Ingresá entre 1 y 100 registros iguales");
        card?.querySelector("[data-route-count]")?.focus();
        return;
    }
    const userNote = card?.querySelector("[data-route-note]")?.value.trim() || "";
    const note = `[${mobileState.routeContext.physical}]${userNote ? ` ${userNote}` : ""}`.slice(0, 255);
    const capturedAt = localIsoNow();
    for (let index = 0; index < boxCount; index += 1) {
        const operation = {
            kind: "ADD",
            local_id: `local-${uniqueId()}`,
            cliente_uid: uniqueId(),
            item_id: item.id,
            cantidad: quantity,
            observacion: note,
            dispositivo: mobileState.device,
            capturado_en: capturedAt,
        };
        mobileState.queue.push(operation);
        mobileState.data.cajas.unshift({
            id: operation.local_id,
            cliente_uid: operation.cliente_uid,
            item_id: item.id,
            cantidad: quantity,
            observacion: note,
            capturado_en: capturedAt,
            pending_local: true,
        });
    }
    const addedTotal = quantity * boxCount;
    item.conteo_fisico = Number(item.conteo_fisico || 0) + addedTotal;
    item.total_cajas = Number(item.total_cajas || 0) + addedTotal;
    item.cantidad_cajas = Number(item.cantidad_cajas || 0) + boxCount;
    saveQueue();
    saveCache();
    refreshRouteItem(itemId);
    renderRouteRecent();
    renderSummary();
    updateConnectionState();
    const label = boxCount === 1 ? "Registro guardado" : `${boxCount} registros guardados`;
    toast(`${label} · ${physicalLabel(mobileState.routeContext.physical)} · físico ${formatNumber(item.conteo_fisico)}`);
    if (navigator.onLine) syncQueue();
}

function observationPhysicalState(observation) {
    const match = String(observation || "").match(/^\[(DISPONIBLE|LINEA|SCRAP)\]\s*/);
    return match ? match[1] : null;
}

function observationDisplay(observation) {
    const raw = String(observation || "").trim();
    const physical = observationPhysicalState(raw);
    const detail = raw.replace(/^\[(DISPONIBLE|LINEA|SCRAP)\]\s*/, "").trim();
    if (physical && detail) return `${physicalLabel(physical)} · ${detail}`;
    if (physical) return physicalLabel(physical);
    return detail || "Sin ubicación informada";
}

function renderRouteRecent() {
    if (!mobileState.data) return;
    const boxes = mobileState.data.cajas.filter((box) => !box.pending_delete).slice(0, 5);
    $("#route-recent").innerHTML = boxes.length ? `
        <div class="route-recent-head">Últimas cargas</div>
        ${boxes.map((box) => {
            const item = itemById(box.item_id);
            const physical = observationPhysicalState(box.observacion);
            return `<div class="route-recent-row"><span><strong>${escapeHtml(item ? routeItemCode(item) : "Código")}</strong><small>${physical ? physicalLabel(physical) : "Sin situación"} · ${item ? stageLabel(item) : "Renglón"}</small></span><strong>${formatNumber(box.cantidad)}</strong><button type="button" data-route-delete-box="${box.id}" ${box.pending_delete ? "disabled" : ""} aria-label="Eliminar registro">⌫</button></div>`;
        }).join("")}
    ` : "";
}

function renderSummary() {
    const items = mobileState.data.inventario.items;
    if (mobileState.routeContext.system === "MATERIAL") {
        const groups = routeMaterialGroups(items, stableItemOrderMap(), "");
        const counted = groups.filter((group) => (
            groupMaterialLotsMovil(group.items).every((lotItems) => (
                lotItems.some((item) => item.conteo_fisico !== null)
            ))
        )).length;
        $("#inventory-progress").textContent = `${counted} / ${groups.length}`;
    } else {
        const visible = items.filter((item) => stageKey(item) === mobileState.routeContext.system);
        const counted = visible.filter((item) => item.conteo_fisico !== null).length;
        $("#inventory-progress").textContent = `${counted} / ${visible.length}`;
    }
    const pending = mobileState.queue.length;
    const banner = $("#pending-banner");
    banner.classList.toggle("hidden", pending === 0);
    banner.textContent = pending
        ? `${pending} cambio${pending === 1 ? "" : "s"} pendiente${pending === 1 ? "" : "s"} de sincronizar. Podés seguir contando.`
        : "";
}

function renderItems() {
    if (!mobileState.data) return;
    const query = normalize($("#item-search").value);
    const inventory = mobileState.data.inventario;
    const groups = groupItemsByPiece(inventory.items).filter((group) => (
        !query || group.items.some((item) => itemHaystack(item).includes(query))
    ));
    $("#item-list").innerHTML = groups.length
        ? groups.map((group) => pieceGroupCard(
            group,
            inventory.estado === "Cerrado",
            Boolean(query) || mobileState.expandedGroups.has(group.key),
        )).join("")
        : '<div class="empty-state">No encontré piezas con esa búsqueda.</div>';
}

function groupItemsByPiece(items) {
    const groups = new Map();
    items.forEach((item) => {
        const key = String(item.codigo || item.id);
        if (!groups.has(key)) {
            groups.set(key, {
                key,
                codigo: item.codigo,
                codigo_cliente: item.codigo_cliente,
                descripcion: item.descripcion,
                tipo_estructura: "INDEPENDIENTE",
                codigos: [item.codigo],
                es_material_compartido: false,
                items: [],
            });
        }
        groups.get(key).items.push(item);
    });
    groups.forEach((group) => {
        group.items.sort(compareStages);
        group.tipo_estructura = group.items.find(
            (item) => item.etapa !== "MATERIAL",
        )?.tipo_estructura || group.items[0]?.tipo_estructura || "INDEPENDIENTE";
    });
    const result = [...groups.values()];
    if (mobileState.data.inventario.categoria !== "PIEZAS") return result;
    const byMaterial = new Map();
    result.forEach((group) => {
        const productive = group.items.find((item) => item.etapa !== "MATERIAL");
        const materialCode = normalize(productive?.codigo_material || "");
        if (!materialCode) return;
        if (!byMaterial.has(materialCode)) byMaterial.set(materialCode, []);
        byMaterial.get(materialCode).push(group);
    });
    const shared = new Map(
        [...byMaterial.entries()].filter(([, candidates]) => candidates.length > 1),
    );
    const consumed = new Set();
    const combined = [];
    result.forEach((group) => {
        if (consumed.has(group.key)) return;
        const productive = group.items.find((item) => item.etapa !== "MATERIAL");
        const materialCode = normalize(productive?.codigo_material || "");
        const candidates = shared.get(materialCode);
        if (!candidates) {
            combined.push(group);
            return;
        }
        candidates.forEach((candidate) => consumed.add(candidate.key));
        const codes = candidates.map((candidate) => candidate.codigo).sort();
        combined.push({
            key: `shared:${materialCode}:${codes.join("|")}`,
            codigo: codes.join(" + "),
            codigo_cliente: "",
            descripcion: `Materia prima ${materialCode}`,
            codigo_material: materialCode,
            tipo_estructura: "COMPARTIDA",
            codigos: codes,
            es_material_compartido: true,
            items: candidates.flatMap((candidate) => candidate.items).sort(compareStages),
        });
    });
    return combined;
}

function stageKey(item) {
    if (item.etapa === "MATERIAL") return "MATERIAL";
    if (item.etapa === "TERMINADO") return "TERMINADO";
    return "PROCESO";
}

function stageTitle(key) {
    if (key === "MATERIAL") return "Materia prima";
    if (key === "TERMINADO") return "Terminado";
    return "Proceso";
}

function structureRole(type) {
    const normalized = String(type || "INDEPENDIENTE").toUpperCase();
    const labels = {
        PADRE: "Padre",
        SUBCONJUNTO: "Subconjunto",
        HIJO: "Hijo",
        INDEPENDIENTE: "Independiente",
        COMPARTIDA: "MP compartida",
    };
    return {
        key: labels[normalized] ? normalized.toLowerCase() : "independiente",
        label: labels[normalized] || "Independiente",
    };
}

function compareStages(left, right) {
    const rank = { MATERIAL: 0, PROCESO_GLOBAL: 1, OPERACION: 1, TERMINADO: 2 };
    const stageDifference = (rank[left.etapa] ?? 9) - (rank[right.etapa] ?? 9);
    if (stageDifference) return stageDifference;
    return String(left.operacion || "").localeCompare(String(right.operacion || ""));
}

function itemHaystack(item) {
    return normalize([
        item.codigo,
        item.codigo_cliente,
        item.codigo_material,
        item.descripcion,
        item.operacion,
        item.titulo_operacion,
        item.lote,
    ].join(" "));
}

function pieceGroupCard(group, closed, expanded) {
    const boxes = group.items.reduce(
        (total, item) => total + Number(item.cantidad_cajas || 0),
        0,
    );
    const counted = group.items.filter((item) => item.conteo_fisico !== null).length;
    const role = structureRole(group.tipo_estructura);
    const materialStocks = new Map();
    const productiveSystem = group.items.reduce((total, item) => {
        if (item.etapa !== "MATERIAL") return total + Number(item.stock_sistema || 0);
        const key = `${normalize(item.codigo_material || item.codigo)}::${item.lote || ""}`;
        materialStocks.set(
            key,
            Math.max(materialStocks.get(key) || 0, Number(item.stock_sistema || 0)),
        );
        return total;
    }, 0);
    const system = productiveSystem + [...materialStocks.values()].reduce(
        (total, value) => total + value,
        0,
    );
    const complete = group.items.length > 0
        && group.items.every((item) => item.conteo_fisico !== null);
    const physical = complete
        ? group.items.reduce((total, item) => total + Number(item.conteo_fisico || 0), 0)
        : null;
    const difference = physical === null ? null : physical - system;
    return `
        <article class="piece-group role-${role.key} ${expanded ? "expanded" : ""}">
            <button
                class="piece-group-head"
                type="button"
                data-toggle-group="${escapeHtml(group.key)}"
                aria-expanded="${expanded ? "true" : "false"}"
            >
                <span class="piece-group-copy">
                    <span class="piece-code-line"><strong>${group.es_material_compartido ? `MP ${escapeHtml(group.codigo_material)}` : escapeHtml(group.codigo)}</strong><em class="structure-role role-${role.key}">${role.label}</em></span>
                    ${group.es_material_compartido
                        ? `<span class="shared-mobile-codes">${group.codigos.map((code) => escapeHtml(code)).join(" · ")}</span>`
                        : `${group.codigo_cliente ? `<small>Cliente ${escapeHtml(group.codigo_cliente)}</small>` : ""}<span>${escapeHtml(group.descripcion || "Sin descripción")}</span>`}
                </span>
                <span class="piece-group-summary">
                    <strong>${boxes}</strong>
                    <small>registro${boxes === 1 ? "" : "s"}</small>
                    <span class="piece-chevron" aria-hidden="true">⌄</span>
                </span>
            </button>
            <div class="piece-stage-list ${expanded ? "" : "hidden"}">
                <div class="piece-stage-meta">
                    <span>${counted} de ${group.items.length} renglones contados</span>
                    <strong>Sist. ${formatNumber(system)} · Fís. ${physical === null ? "—" : formatNumber(physical)} · Dif. ${difference === null ? "—" : formatNumber(difference)}</strong>
                </div>
                ${["MATERIAL", "PROCESO", "TERMINADO"].map((stage) => {
                    const items = group.items.filter((item) => stageKey(item) === stage);
                    return items.length ? stageSection(group, stage, items, closed) : "";
                }).join("")}
            </div>
        </article>
    `;
}

function stageSection(group, stage, items, closed) {
    const key = `${group.key}::${stage}`;
    const expanded = mobileState.expandedStages.has(key);
    const counted = items.filter((item) => item.conteo_fisico !== null).length;
    const materialCode = stage === "MATERIAL"
        ? String(items[0].codigo_material || items[0].codigo || "")
        : "";
    return `<section class="stage-section stage-${stage.toLowerCase()} ${expanded ? "expanded" : ""}">
        <button class="stage-section-head" type="button" data-toggle-stage="${escapeHtml(key)}">
            <span><strong>${stageTitle(stage)}</strong><small>${counted}/${items.length} contados</small></span>
            <span class="stage-chevron">⌄</span>
        </button>
        <div class="stage-section-body ${expanded ? "" : "hidden"}">
            ${items.map((item) => itemCard(item, closed)).join("")}
            ${stage === "MATERIAL" && !closed
                ? `<button class="inline-add-lot" type="button" data-add-lot="${escapeHtml(materialCode)}" data-lot-piece="${escapeHtml(items[0].codigo)}">＋ Agregar lote</button>`
                : ""}
        </div>
    </section>`;
}

function itemCard(item, closed) {
    const physical = item.conteo_fisico === null ? "—" : formatNumber(item.conteo_fisico);
    const material = item.etapa === "MATERIAL" && item.codigo_material
        ? `<span class="material-code">MP ${escapeHtml(item.codigo_material)}</span>`
        : "";
    const materialDescription = materialLotDescription(item);
    return `
        <article class="item-card">
            <div class="item-card-main">
                <div class="item-identity">
                    <span class="stage-badge">${escapeHtml(stageLabel(item))}</span>
                    ${material}
                    ${item.lote ? `<p>Lote ${escapeHtml(item.lote)}</p>` : ""}
                    ${materialDescription ? `<small class="material-description">${escapeHtml(materialDescription)}</small>` : ""}
                </div>
                <div class="item-count">
                    <small>Físico</small>
                    <strong>${physical}</strong>
                    <span>${Number(item.cantidad_cajas || 0)} registro${Number(item.cantidad_cajas || 0) === 1 ? "" : "s"}</span>
                </div>
            </div>
            <div class="item-card-footer">
                <p>Sistema <strong>${formatNumber(item.stock_sistema)}</strong></p>
                <div class="item-card-actions">
                    ${item.etapa === "MATERIAL" && item.lote && !closed
                        ? `<button class="delete-lot" data-delete-lot="${item.id}" type="button">Eliminar lote</button>`
                        : ""}
                    <button data-open-item="${item.id}" ${closed ? "disabled" : ""}>＋ Registro</button>
                </div>
            </div>
        </article>
    `;
}

function toggleGroup(key) {
    if (mobileState.expandedGroups.has(key)) {
        mobileState.expandedGroups.delete(key);
    } else {
        mobileState.expandedGroups.add(key);
    }
    renderItems();
}

function toggleStage(key) {
    if (mobileState.expandedStages.has(key)) mobileState.expandedStages.delete(key);
    else mobileState.expandedStages.add(key);
    renderItems();
}

function openItem(itemId, quickEntry = false) {
    mobileState.selectedItemId = itemId;
    mobileState.quickEntry = quickEntry;
    mobileState.entryPhysicalState = quickEntry ? mobileState.routeContext.physical : null;
    renderSheet();
    $("#entry-sheet").classList.toggle("quick-entry", quickEntry);
    $("#entry-sheet").classList.remove("hidden");
    $("#entry-sheet").setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    const lastQuantity = localStorage.getItem(`last-box-quantity-${itemId}`) || "";
    $("#box-quantity").value = lastQuantity;
    $("#box-count").value = "1";
    $("#box-note").value = "";
    $("#add-box").textContent = quickEntry ? "Guardar y siguiente" : "＋ Agregar registro";
    updateBatchSummary();
    window.setTimeout(() => $("#box-quantity").focus(), 80);
}

function closeSheet() {
    $("#entry-sheet").classList.add("hidden");
    $("#entry-sheet").setAttribute("aria-hidden", "true");
    $("#entry-sheet").classList.remove("quick-entry");
    document.body.style.overflow = "";
    mobileState.quickEntry = false;
    mobileState.entryPhysicalState = null;
}

function openMaterialSheet() {
    const inventory = mobileState.data.inventario;
    const material = mobileState.mode === "ROUTE"
        ? mobileState.routeContext.system === "MATERIAL"
        : inventory.categoria === "MATERIA_PRIMA";
    mobileState.articleType = material ? "MATERIA_PRIMA" : "PIEZA";
    $("#article-source").textContent = material ? "Materia prima · mtprim01" : "Piezas · produc01";
    $("#article-help").textContent = material
        ? "Buscá un material por código o descripción"
        : "Buscá una pieza por código o descripción";
    $("#material-search").value = "";
    $("#material-suggestions").innerHTML = '<div class="suggestion-empty">Escribí un código o descripción.</div>';
    $("#material-sheet").classList.remove("hidden");
    $("#material-sheet").setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    window.setTimeout(() => $("#material-search").focus(), 80);
}

function closeMaterialSheet() {
    window.clearTimeout(mobileState.materialTimer);
    $("#material-sheet").classList.add("hidden");
    $("#material-sheet").setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
}

function scheduleMaterialSearch() {
    window.clearTimeout(mobileState.materialTimer);
    const query = $("#material-search").value.trim();
    if (query.length < 2) {
        $("#material-suggestions").innerHTML = '<div class="suggestion-empty">Escribí al menos 2 caracteres.</div>';
        return;
    }
    mobileState.materialTimer = window.setTimeout(() => searchMaterials(query), 230);
}

async function searchMaterials(query) {
    try {
        const material = mobileState.articleType === "MATERIA_PRIMA";
        const resource = material ? "materiales" : "piezas";
        const data = await request(`/api/busqueda/${resource}?q=${encodeURIComponent(query)}&limite=12`);
        const existing = new Set(
            mobileState.data.inventario.items
                .filter((item) => material ? item.etapa === "MATERIAL" : item.etapa !== "MATERIAL")
                .map((item) => normalize(material ? (item.codigo_material || item.codigo) : item.codigo)),
        );
        const results = (data.resultados || []).filter((item) => !existing.has(normalize(item.codigo)));
        $("#material-suggestions").innerHTML = results.length
            ? results.map((item) => {
                const media = mobileState.mode === "MEDIA";
                const clientCode = String(item.codigo_cliente || "").trim();
                return `<button type="button" data-material-code="${escapeHtml(item.codigo)}">
                    <strong>${escapeHtml(media && clientCode ? clientCode : item.codigo)}</strong>
                    <span>${media && clientCode ? `Interno: ${escapeHtml(item.codigo)} · ` : ""}${escapeHtml(item.descripcion || "Sin descripción")}</span>
                </button>`;
            }).join("")
            : `<div class="suggestion-empty">No encontré ${material ? "materiales" : "piezas"} nuevos.</div>`;
    } catch (error) {
        $("#material-suggestions").innerHTML = `<div class="suggestion-empty">${escapeHtml(error.message)}</div>`;
    }
}

async function addMaterialToInventory(code) {
    try {
        const material = mobileState.articleType === "MATERIA_PRIMA";
        await request(`/api/inventarios/${inventoryId}/articulos`, {
            method: "POST",
            body: JSON.stringify({ codigo: code, tipo_articulo: mobileState.articleType, contar_material: material, tipo_conteo: "GLOBAL" }),
        });
        closeMaterialSheet();
        await loadInventory();
        const group = mobileState.data.inventario.items.find((item) => normalize(material ? (item.codigo_material || item.codigo) : item.codigo) === normalize(code));
        if (group) {
            const groupKey = String(group.codigo || group.id);
            mobileState.expandedGroups.add(groupKey);
            mobileState.expandedStages.add(`${groupKey}::${material ? "MATERIAL" : mobileState.routeContext.system}`);
            renderItems();
        }
        toast(`${code} fue agregado`);
    } catch (error) {
        toast(error.message);
    }
}

function materialLotDescription(item) {
    if (item.etapa !== "MATERIAL") return "";
    const title = String(item.titulo_operacion || "");
    const separator = title.indexOf(" · ");
    return separator >= 0 ? title.slice(separator + 3).trim() : "";
}

function openLotSheet(code, pieceCode = "") {
    const item = mobileState.data.inventario.items.find(
        (row) => row.etapa === "MATERIAL"
            && normalize(row.codigo_material || row.codigo) === normalize(code)
            && (!pieceCode || normalize(row.codigo) === normalize(pieceCode)),
    );
    if (!item) return;
    mobileState.lotMaterialCode = code;
    mobileState.lotPieceCode = pieceCode || item.codigo;
    $("#lot-material-code").textContent = code;
    $("#lot-material-description").textContent = materialLotDescription(item)
        || item.descripcion
        || "Sin descripción";
    $("#lot-number").value = "";
    $("#lot-sheet").classList.remove("hidden");
    $("#lot-sheet").setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    window.setTimeout(() => $("#lot-number").focus(), 80);
}

function closeLotSheet() {
    $("#lot-sheet").classList.add("hidden");
    $("#lot-sheet").setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    mobileState.lotMaterialCode = null;
    mobileState.lotPieceCode = null;
}

async function addLotToInventory(event) {
    event.preventDefault();
    const lot = $("#lot-number").value.trim();
    if (!/^\d{5}$/.test(lot)) {
        toast("El lote debe tener exactamente 5 dígitos");
        return;
    }
    try {
        await request(
            `/api/inventarios/${inventoryId}/materiales/${encodeURIComponent(mobileState.lotMaterialCode)}/lotes`,
            {
                method: "POST",
                body: JSON.stringify({
                    lote: lot,
                    codigo_pieza: mobileState.lotPieceCode,
                }),
            },
        );
        closeLotSheet();
        await loadInventory();
        toast(`Lote ${lot} agregado`);
    } catch (error) {
        toast(error.message);
    }
}

async function deleteLot(itemId) {
    const item = itemById(itemId);
    if (!item?.lote) return;
    if (Number(item.cantidad_cajas || 0) > 0 || item.conteo_fisico !== null) {
        toast("Eliminá primero los registros cargados en este lote");
        return;
    }
    if (!window.confirm(`¿Eliminar el lote ${item.lote}?`)) return;
    try {
        await request(`/api/inventarios/${inventoryId}/lotes/${itemId}`, {
            method: "DELETE",
        });
        await loadInventory();
        toast(`Lote ${item.lote} eliminado`);
    } catch (error) {
        toast(error.message);
    }
}

function renderSheet() {
    const item = itemById(mobileState.selectedItemId);
    if (!item) return;
    $("#sheet-stage").textContent = mobileState.entryPhysicalState
        ? `${physicalLabel(mobileState.entryPhysicalState)} · ${stageLabel(item)}`
        : stageLabel(item);
    $("#sheet-title").textContent = item.codigo;
    $("#sheet-description").textContent = item.descripcion || "Sin descripción";
    $("#sheet-system").textContent = formatNumber(item.stock_sistema);
    $("#sheet-physical").textContent = item.conteo_fisico === null
        ? "—"
        : formatNumber(item.conteo_fisico);
    $("#sheet-box-count").textContent = Number(item.cantidad_cajas || 0);
    const boxes = mobileState.data.cajas
        .filter((box) => box.item_id === item.id)
        .sort((a, b) => String(b.capturado_en).localeCompare(String(a.capturado_en)));
    $("#recent-boxes").innerHTML = boxes.length
        ? boxes.map((box, index) => boxRow(box, boxes.length - index)).join("")
        : '<div class="empty-state">Todavía no cargaste registros en este renglón.</div>';
}

function boxRow(box, number, selectable = false) {
    const classes = [
        "box-row",
        box.pending_local ? "pending-sync" : "",
        box.pending_delete ? "pending-delete" : "",
    ].filter(Boolean).join(" ");
    const status = box.pending_delete
        ? "Pendiente de eliminar"
        : (box.pending_local ? "Pendiente de sincronizar" : formatTime(box.capturado_en));
    const action = selectable
        ? `<label class="box-selector" aria-label="Seleccionar registro"><input type="checkbox" data-route-select-box="${box.id}" ${mobileState.selectedRouteBoxes.has(String(box.id)) ? "checked" : ""}><span></span></label>`
        : `<button data-delete-box="${box.id}" ${box.pending_delete ? "disabled" : ""} aria-label="Eliminar registro">⌫</button>`;
    return `
        <div class="${classes}">
            <span class="box-number">${number}</span>
            <p>
                <strong>${escapeHtml(observationDisplay(box.observacion))}</strong>
                <small>${status}</small>
            </p>
            <strong>${formatNumber(box.cantidad)}</strong>
            ${action}
        </div>
    `;
}

async function addBox(event) {
    event.preventDefault();
    const item = itemById(mobileState.selectedItemId);
    const quantity = Number($("#box-quantity").value);
    const boxCount = Number($("#box-count").value);
    if (!item || !Number.isInteger(quantity) || quantity <= 0) {
        toast("Ingresá una cantidad entera mayor que cero");
        return;
    }
    if (!Number.isInteger(boxCount) || boxCount <= 0 || boxCount > 100) {
        toast("Ingresá entre 1 y 100 registros iguales");
        return;
    }
    const userNote = $("#box-note").value.trim();
    const note = (mobileState.entryPhysicalState
        ? `[${mobileState.entryPhysicalState}]${userNote ? ` ${userNote}` : ""}`
        : userNote).slice(0, 255);
    const capturedAt = localIsoNow();
    for (let index = 0; index < boxCount; index += 1) {
        const operation = {
            kind: "ADD",
            local_id: `local-${uniqueId()}`,
            cliente_uid: uniqueId(),
            item_id: item.id,
            cantidad: quantity,
            observacion: note,
            dispositivo: mobileState.device,
            capturado_en: capturedAt,
        };
        mobileState.queue.push(operation);
        mobileState.data.cajas.unshift({
            id: operation.local_id,
            cliente_uid: operation.cliente_uid,
            item_id: item.id,
            cantidad: operation.cantidad,
            observacion: operation.observacion,
            capturado_en: operation.capturado_en,
            pending_local: true,
        });
    }
    const addedTotal = quantity * boxCount;
    item.conteo_fisico = Number(item.conteo_fisico || 0) + addedTotal;
    item.total_cajas = Number(item.total_cajas || 0) + addedTotal;
    item.cantidad_cajas = Number(item.cantidad_cajas || 0) + boxCount;
    localStorage.setItem(`last-box-quantity-${item.id}`, String(quantity));
    saveQueue();
    saveCache();
    renderAll();
    $("#box-note").value = "";
    $("#box-count").value = "1";
    updateBatchSummary();
    $("#box-quantity").select();
    const label = boxCount === 1 ? "Registro guardado" : `${boxCount} registros guardados`;
    toast(navigator.onLine ? label : `${label} en el celular`);
    if (navigator.onLine) syncQueue();
    if (mobileState.quickEntry) {
        closeSheet();
        $("#route-item-search").value = "";
        renderRouteResults();
        renderRouteRecent();
        window.setTimeout(() => $("#route-item-search").focus(), 80);
    }
}

function updateBatchSummary() {
    const quantity = Number($("#box-quantity").value);
    const boxCount = Number($("#box-count").value);
    const valid = Number.isInteger(quantity) && quantity > 0
        && Number.isInteger(boxCount) && boxCount > 0 && boxCount <= 100;
    const summary = $("#batch-summary");
    const button = $("#add-box");
    if (!valid) {
        summary.textContent = "Ingresá la cantidad y el número de registros iguales";
        button.textContent = mobileState.quickEntry ? "Guardar y siguiente" : "＋ Agregar registro";
        return;
    }
    const total = quantity * boxCount;
    summary.innerHTML = `<strong>${boxCount} × ${formatNumber(quantity)} = ${formatNumber(total)}</strong> unidades`;
    button.textContent = mobileState.quickEntry
        ? "Guardar y siguiente"
        : (boxCount === 1 ? "＋ Agregar registro" : `＋ Agregar ${boxCount} registros`);
}

function deleteBox(boxId) {
    const box = mobileState.data.cajas.find(
        (candidate) => String(candidate.id) === String(boxId)
    );
    if (!box || box.pending_delete) return;
    if (!window.confirm(`¿Quitar el registro de ${formatNumber(box.cantidad)} unidades?`)) return;
    const item = itemById(box.item_id);
    if (box.pending_local) {
        mobileState.queue = mobileState.queue.filter(
            (operation) => operation.cliente_uid !== box.cliente_uid
        );
        mobileState.data.cajas = mobileState.data.cajas.filter(
            (candidate) => candidate.cliente_uid !== box.cliente_uid
        );
    } else {
        mobileState.queue.push({
            kind: "DELETE",
            local_id: `delete-${box.id}`,
            box_id: box.id,
            item_id: box.item_id,
            cantidad: box.cantidad,
        });
        box.pending_delete = true;
    }
    item.conteo_fisico = Math.max(0, Number(item.conteo_fisico || 0) - Number(box.cantidad));
    item.total_cajas = Math.max(0, Number(item.total_cajas || 0) - Number(box.cantidad));
    item.cantidad_cajas = Math.max(0, Number(item.cantidad_cajas || 0) - 1);
    saveQueue();
    saveCache();
    refreshRouteItem(item.id);
    renderRouteRecent();
    renderSummary();
    renderSheet();
    updateConnectionState();
    toast(`Registro eliminado · físico ${formatNumber(item.conteo_fisico)}`);
    if (navigator.onLine) syncQueue();
}

function deleteBoxesTogether(itemId, boxIds) {
    const boxes = boxesForRouteItem(itemId).filter((box) => (
        boxIds.includes(String(box.id))
    ));
    if (!boxes.length) {
        toast("Seleccioná al menos un registro");
        return;
    }
    const total = boxes.reduce((sum, box) => sum + Number(box.cantidad), 0);
    if (!window.confirm(`¿Eliminar ${boxes.length} registros por un total de ${formatNumber(total)} unidades?`)) return;
    const item = itemById(itemId);
    const remoteBoxes = [];
    boxes.forEach((box) => {
        if (box.pending_local) {
            mobileState.queue = mobileState.queue.filter(
                (operation) => operation.cliente_uid !== box.cliente_uid
            );
            mobileState.data.cajas = mobileState.data.cajas.filter(
                (candidate) => candidate.cliente_uid !== box.cliente_uid
            );
        } else {
            box.pending_delete = true;
            remoteBoxes.push({
                box_id: Number(box.id),
                cantidad: Number(box.cantidad),
            });
        }
    });
    if (remoteBoxes.length) {
        mobileState.queue.push({
            kind: "DELETE_BATCH",
            local_id: `delete-batch-${uniqueId()}`,
            item_id: itemId,
            boxes: remoteBoxes,
        });
    }
    item.conteo_fisico = Math.max(0, Number(item.conteo_fisico || 0) - total);
    item.total_cajas = Math.max(0, Number(item.total_cajas || 0) - total);
    item.cantidad_cajas = Math.max(0, Number(item.cantidad_cajas || 0) - boxes.length);
    mobileState.selectingRouteItemId = null;
    mobileState.selectedRouteBoxes.clear();
    saveQueue();
    saveCache();
    refreshRouteItem(itemId);
    renderRouteRecent();
    renderSummary();
    updateConnectionState();
    toast(`${boxes.length} registros eliminados · físico ${formatNumber(item.conteo_fisico)}`);
    if (navigator.onLine) syncQueue();
}

async function syncQueue() {
    if (mobileState.syncing || !navigator.onLine || !mobileState.queue.length) {
        updateConnectionState();
        return;
    }
    mobileState.syncing = true;
    updateConnectionState();
    const affectedItems = new Set();
    try {
        while (mobileState.queue.length && navigator.onLine) {
            const operation = mobileState.queue[0];
            affectedItems.add(Number(operation.item_id));
            if (operation.kind === "MEDIA_SAVE") {
                await request(`/api/inventarios/${inventoryId}/conteo-movil/medios/${operation.item_id}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        conteo_vacios: operation.conteo_vacios,
                        conteo_llenos: operation.conteo_llenos,
                        conteo_rotos: operation.conteo_rotos,
                    }),
                });
                mobileState.queue.shift();
            } else if (operation.kind === "ADD") {
                const batch = [];
                for (const candidate of mobileState.queue) {
                    if (candidate.kind !== "ADD" || batch.length >= 100) break;
                    batch.push(candidate);
                }
                const response = await request(`/api/inventarios/${inventoryId}/conteo-movil/cajas`, {
                    method: "POST",
                    body: JSON.stringify({ cajas: batch.map((box) => ({
                        cliente_uid: box.cliente_uid,
                        item_id: box.item_id,
                        cantidad: box.cantidad,
                        observacion: box.observacion,
                        dispositivo: box.dispositivo,
                        capturado_en: box.capturado_en,
                    })) }),
                });
                (response.cajas || []).forEach((savedBox) => {
                    const localBox = mobileState.data.cajas.find(
                        (box) => box.cliente_uid === savedBox.cliente_uid
                    );
                    if (localBox) Object.assign(localBox, savedBox, { pending_local: false });
                });
                mobileState.queue.splice(0, batch.length);
            } else if (operation.kind === "DELETE_BATCH") {
                await request(`/api/inventarios/${inventoryId}/conteo-movil/cajas/eliminar`, {
                    method: "POST",
                    body: JSON.stringify({ caja_ids: operation.boxes.map((box) => box.box_id) }),
                });
                const deletedIds = new Set(operation.boxes.map((box) => String(box.box_id)));
                mobileState.data.cajas = mobileState.data.cajas.filter(
                    (box) => !deletedIds.has(String(box.id))
                );
                mobileState.queue.shift();
            } else {
                await request(`/api/inventarios/${inventoryId}/conteo-movil/cajas/${operation.box_id}`, {
                    method: "DELETE",
                });
                mobileState.data.cajas = mobileState.data.cajas.filter(
                    (box) => String(box.id) !== String(operation.box_id)
                );
                mobileState.queue.shift();
            }
            saveQueue();
        }
        saveCache();
    } catch (error) {
        toast(error.message);
    } finally {
        mobileState.syncing = false;
        if (mobileState.data?.inventario.modalidad_conteo === "MEDIOS") {
            renderMediaResults();
        } else {
            affectedItems.forEach(refreshRouteItem);
            renderRouteRecent();
            renderSheet();
        }
        renderSummary();
        updateConnectionState();
    }
}

function updateConnectionState() {
    const status = $("#connection-status");
    const pending = mobileState.queue.length;
    if (!navigator.onLine) {
        status.className = "sync-state offline";
        status.textContent = pending ? `Sin red · ${pending} pend.` : "Sin conexión";
    } else if (mobileState.syncing) {
        status.className = "sync-state waiting";
        status.textContent = "Sincronizando…";
    } else if (pending) {
        status.className = "sync-state pending";
        status.textContent = `${pending} pendiente${pending === 1 ? "" : "s"}`;
    } else {
        status.className = "sync-state ok";
        status.textContent = "✓ Sincronizado";
    }
    $("#sync-now").disabled = mobileState.syncing || !navigator.onLine;
}

function renderFatal(message) {
    $("#item-list").innerHTML = `<div class="empty-state"><strong>No se pudo abrir el inventario</strong><br>${escapeHtml(message)}</div>`;
}

function itemById(itemId) {
    return mobileState.data?.inventario.items.find((item) => item.id === Number(itemId));
}

function stageLabel(item) {
    if (item.etapa === "MATERIAL") return item.lote ? `Material · Lote ${item.lote}` : "Material";
    if (item.etapa === "TERMINADO") return "Pieza terminada";
    if (item.etapa === "PROCESO_GLOBAL") return "En proceso";
    return item.titulo_operacion || (item.operacion ? `Operación ${item.operacion}` : "En proceso");
}

function saveQueue() {
    localStorage.setItem(queueKey, JSON.stringify(mobileState.queue));
    updateConnectionState();
}

function saveCache() {
    if (mobileState.data) localStorage.setItem(cacheKey, JSON.stringify(mobileState.data));
}

function readJson(key, fallback) {
    try {
        const value = localStorage.getItem(key);
        return value ? JSON.parse(value) : fallback;
    } catch (_error) {
        return fallback;
    }
}

function getDeviceId() {
    let value = localStorage.getItem(deviceKey);
    if (!value) {
        value = `cel-${uniqueId().slice(0, 8)}`;
        localStorage.setItem(deviceKey, value);
    }
    return value;
}

function uniqueId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
}

function localIsoNow() {
    const date = new Date();
    const pad = (value) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
        + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

function formatNumber(value) {
    return new Intl.NumberFormat("es-AR", { maximumFractionDigits: 3 }).format(Number(value || 0));
}

function signedNumber(value) {
    const number = Number(value || 0);
    return `${number > 0 ? "+" : ""}${formatNumber(number)}`;
}

function formatTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? "Sin hora"
        : date.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

let toastTimer;
function toast(message) {
    const element = $("#mobile-toast");
    element.textContent = message;
    element.classList.remove("hidden");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => element.classList.add("hidden"), 2600);
}
