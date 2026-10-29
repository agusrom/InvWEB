const editorState = {
    templateId: Number(document.body.dataset.templateId) || null,
    category: "PIEZAS",
    items: [],
    structure: null,
    inventoryTypes: [],
};

const autocompleteState = {
    results: [],
    activeIndex: -1,
    timer: null,
    controller: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

document.addEventListener("DOMContentLoaded", async () => {
    $("#add-piece").addEventListener("click", addPiece);
    $("#piece-code").addEventListener("input", scheduleItemSuggestions);
    $("#piece-code").addEventListener("keydown", handleItemSuggestionKeydown);
    $("#piece-code").addEventListener("focus", scheduleItemSuggestions);
    document.addEventListener("mousedown", (event) => {
        if (!event.target.closest(".autocomplete-control")) {
            hideItemSuggestions();
        }
    });
    $("#template-form").addEventListener("submit", saveTemplate);
    $("#template-category").addEventListener("change", changeCategory);
    $("#template-inventory-type").addEventListener(
        "change",
        applyInventoryType
    );
    $("#template-category").disabled = true;

    await loadInventoryTypes();
    if (editorState.templateId) {
        await loadTemplate();
    } else {
        applyCategoryUI();
        renderPieces();
        if (editorState.category === "CICLICO" && editorState.items.length) {
            await loadStructure(editorState.items[0].codigo);
        }
        $("#template-name").focus();
    }
});

async function loadInventoryTypes() {
    try {
        const data = await requestJson("/api/catalogos");
        editorState.inventoryTypes = (data.tipos_inventario || []).filter(
            (tipo) => tipo.motor !== "CICLICO"
        );
        $("#template-inventory-type").innerHTML =
            editorState.inventoryTypes.map((tipo) => `
                <option value="${escapeHtml(tipo.codigo)}">
                    ${escapeHtml(tipo.nombre)}${tipo.activo ? "" : " · INACTIVO"}
                </option>
            `).join("");
        if (!editorState.templateId) applyInventoryType();
    } catch (error) {
        showStatus(error.message, true);
    }
}

function applyInventoryType() {
    const tipo = editorState.inventoryTypes.find(
        (item) => item.codigo === $("#template-inventory-type").value
    );
    if (!tipo) return;
    $("#template-category").value = tipo.motor;
    changeCategory();
}

async function requestJson(url, options = {}) {
    setLoading(true);
    try {
        const response = await fetch(url, {
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {}),
            },
            ...options,
        });
        const contentType = response.headers.get("content-type") || "";
        const body = contentType.includes("application/json")
            ? await response.json()
            : null;
        if (!response.ok) {
            throw new Error(body?.detail || "No se pudo completar la operación");
        }
        return body;
    } finally {
        setLoading(false);
    }
}

async function loadTemplate() {
    try {
        const template = await requestJson(
            `/api/plantillas/${editorState.templateId}`
        );
        $("#template-name").value = template.nombre;
        $("#template-client").value = template.cliente;
        $("#template-description").value = template.descripcion || "";
        $("#template-inventory-type").value =
            template.tipo_inventario_codigo || (
                template.categoria === "MATERIA_PRIMA"
                    ? "MATERIA_PRIMA"
                    : "PIEZAS_PROCESO"
            );
        const categoria = template.categoria === "CICLICO"
            ? "PIEZAS"
            : (template.categoria || "PIEZAS");
        $("#template-category").value = categoria;
        editorState.category = $("#template-category").value;
        $("#template-count-type").value = template.tipo_conteo;
        $("#template-controls-delivery-notes").checked =
            Boolean(template.controla_remitos);
        $("#template-active").checked = template.activa !== false;
        $("#template-created-at").textContent =
            formatDateTime(template.creada_en);
        $("#template-updated-at").textContent =
            formatDateTime(template.actualizada_en);
        $("#template-dates").classList.remove("hidden");
        editorState.items = template.items.map((item) => ({
            ...item,
            ubicacion: item.ubicacion || "",
            contar_material:
                Boolean(item.codigo_material)
                && item.contar_material !== false,
        }));
        applyCategoryUI();
        renderPieces();
        if (template.categoria === "CICLICO") {
            showStatus(
                "Esta era una plantilla cíclica del modo anterior. "
                + "Al guardarla pasará a ser una plantilla normal; "
                + "ahora el modo cíclico se elige al crear el inventario."
            );
        }
    } catch (error) {
        showStatus(error.message, true);
    }
}

async function addPiece() {
    const input = $("#piece-code");
    const code = input.value.trim().toUpperCase();

    if (!code) {
        showStatus(
            editorState.category === "MATERIA_PRIMA"
                ? "Ingresá un código de materia prima."
                : "Ingresá un código de pieza.",
            true
        );
        input.focus();
        return;
    }
    if (editorState.items.some((item) => normalCode(item.codigo) === code)) {
        showStatus(`El código ${code} ya está incluido.`, true);
        input.select();
        return;
    }
    if (editorState.category === "CICLICO" && editorState.items.length) {
        showStatus(
            "La plantilla cíclica admite una sola pieza raíz. Quitá la actual para cambiarla.",
            true
        );
        input.select();
        return;
    }

    const button = $("#add-piece");
    button.disabled = true;
    button.textContent = "Buscando…";
    try {
        const endpoint = editorState.category === "MATERIA_PRIMA"
            ? "/api/materiales/"
            : "/api/piezas/";
        const item = await requestJson(`${endpoint}${encodeURIComponent(code)}`);
        let structure = null;
        if (editorState.category === "CICLICO") {
            structure = await requestJson(
                `/api/estructuras/${encodeURIComponent(item.codigo)}`
            );
        }
        editorState.items.push({
            ...item,
            ubicacion: "",
            contar_material:
                editorState.category === "MATERIA_PRIMA"
                || Boolean(item.codigo_material),
        });
        editorState.structure = structure;
        input.value = "";
        hideItemSuggestions();
        renderPieces();
        if (structure) {
            renderStructure();
            showStatus(
                `Raíz ${item.codigo} agregada. Se detectaron ${structure.cantidad_codigos} códigos en la estructura.`
            );
        } else {
            showStatus(
                `${itemTypeName()} ${item.codigo} agregado correctamente.`
            );
        }
        input.focus();
    } catch (error) {
        showStatus(error.message, true);
        input.select();
    } finally {
        button.disabled = false;
        button.textContent = "Buscar y agregar";
    }
}

function scheduleItemSuggestions() {
    window.clearTimeout(autocompleteState.timer);
    const termino = $("#piece-code").value.trim();
    if (termino.length < 2) {
        hideItemSuggestions();
        return;
    }
    autocompleteState.timer = window.setTimeout(
        () => loadItemSuggestions(termino),
        250
    );
}

async function loadItemSuggestions(termino) {
    autocompleteState.controller?.abort();
    autocompleteState.controller = new AbortController();
    const endpoint = editorState.category === "MATERIA_PRIMA"
        ? "/api/busqueda/materiales"
        : "/api/busqueda/piezas";
    try {
        const response = await fetch(
            `${endpoint}?q=${encodeURIComponent(termino)}&limite=10`,
            { signal: autocompleteState.controller.signal }
        );
        if (!response.ok) throw new Error("No se pudieron buscar códigos");
        const data = await response.json();
        if ($("#piece-code").value.trim().toUpperCase()
            !== termino.toUpperCase()) {
            return;
        }
        autocompleteState.results = data.resultados || [];
        autocompleteState.activeIndex =
            autocompleteState.results.length ? 0 : -1;
        renderItemSuggestions();
    } catch (error) {
        if (error.name !== "AbortError") hideItemSuggestions();
    }
}

function renderItemSuggestions() {
    const menu = $("#piece-suggestions");
    const input = $("#piece-code");
    if (!autocompleteState.results.length) {
        menu.innerHTML = `
            <div class="autocomplete-empty">Sin coincidencias</div>
        `;
    } else {
        const esMaterial = editorState.category === "MATERIA_PRIMA";
        menu.innerHTML = autocompleteState.results.map((item, index) => {
            const auxiliar = esMaterial
                ? [item.unidad, item.espesor ? `Esp. ${item.espesor}` : ""]
                    .filter(Boolean).join(" · ")
                : [
                    item.codigo_cliente
                        ? `Cliente ${item.codigo_cliente}`
                        : "",
                    item.codigo_material
                        ? `MP ${item.codigo_material}`
                        : "Sin MP",
                ].filter(Boolean).join(" · ");
            return `
                <button
                    type="button"
                    class="autocomplete-option ${index === autocompleteState.activeIndex ? "active" : ""}"
                    data-suggestion-index="${index}"
                    role="option"
                    aria-selected="${index === autocompleteState.activeIndex}"
                >
                    <strong>${escapeHtml(item.codigo)}</strong>
                    <span>${escapeHtml(item.descripcion || "Sin descripción")}</span>
                    <small>${escapeHtml(auxiliar || "Sin datos adicionales")}</small>
                </button>
            `;
        }).join("");
        menu.querySelectorAll(".autocomplete-option").forEach((option) => {
            option.addEventListener("mousedown", (event) => {
                event.preventDefault();
                selectItemSuggestion(Number(option.dataset.suggestionIndex));
            });
        });
    }
    menu.classList.remove("hidden");
    input.setAttribute("aria-expanded", "true");
}

function handleItemSuggestionKeydown(event) {
    const menuVisible = !$("#piece-suggestions").classList.contains("hidden");
    if (menuVisible && autocompleteState.results.length) {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const direction = event.key === "ArrowDown" ? 1 : -1;
            const length = autocompleteState.results.length;
            autocompleteState.activeIndex =
                (autocompleteState.activeIndex + direction + length) % length;
            renderItemSuggestions();
            $("#piece-suggestions .autocomplete-option.active")
                ?.scrollIntoView({ block: "nearest" });
            return;
        }
        if (event.key === "Enter") {
            event.preventDefault();
            selectItemSuggestion(autocompleteState.activeIndex);
            return;
        }
    }
    if (event.key === "Escape") {
        hideItemSuggestions();
        return;
    }
    if (event.key === "Enter") {
        event.preventDefault();
        addPiece();
    }
}

function selectItemSuggestion(index) {
    const item = autocompleteState.results[index];
    if (!item) return;
    $("#piece-code").value = item.codigo;
    hideItemSuggestions();
    $("#piece-code").focus();
}

function hideItemSuggestions() {
    window.clearTimeout(autocompleteState.timer);
    autocompleteState.controller?.abort();
    autocompleteState.results = [];
    autocompleteState.activeIndex = -1;
    $("#piece-suggestions")?.classList.add("hidden");
    $("#piece-code")?.setAttribute("aria-expanded", "false");
}

function renderPieces() {
    const count = editorState.items.length;
    const esCiclico = editorState.category === "CICLICO";
    const singular = editorState.category === "MATERIA_PRIMA"
        ? "material"
        : (esCiclico ? "raíz" : "pieza");
    const plural = editorState.category === "MATERIA_PRIMA"
        ? "materiales"
        : (esCiclico ? "raíces" : "piezas");
    $("#piece-count").textContent =
        `${count} ${count === 1 ? singular : plural}`;
    $("#empty-pieces").classList.toggle("hidden", count > 0);

    $("#pieces-list").innerHTML = editorState.items.map((item, index) => {
        const esMaterial = editorState.category === "MATERIA_PRIMA";
        const datoUnoTitulo = esMaterial ? "Medidas" : "Código cliente";
        const datoUno = esMaterial
            ? medidasMaterial(item)
            : (item.codigo_cliente || "—");
        const datoDosTitulo = esMaterial ? "Unidad" : "Material";
        const datoDos = esMaterial
            ? (item.unidad || "—")
            : (item.codigo_material || "Sin material");
        const tieneMaterial = Boolean((item.codigo_material || "").trim());
        const controlaMaterial = item.contar_material !== false;

        return `
        <article class="piece-row ${esMaterial ? "" : "with-material-control"}" data-piece-index="${index}">
            <span class="piece-order">${index + 1}</span>

            <div class="piece-main">
                <strong class="piece-code">${escapeHtml(item.codigo)}</strong>
                ${esMaterial ? "" : structureRoleHtml(item.tipo_estructura)}
                <span class="piece-description">
                    ${escapeHtml(item.descripcion || "Sin descripción")}
                </span>
            </div>

            <div class="piece-data">
                <small>${datoUnoTitulo}</small>
                <span>${escapeHtml(datoUno)}</span>
            </div>

            <div class="piece-data">
                <small>${datoDosTitulo}</small>
                <span class="material-code">
                    ${escapeHtml(datoDos)}
                </span>
            </div>

            ${esMaterial ? "" : `
                <label class="material-count-control ${tieneMaterial ? "" : "unavailable"}">
                    <input
                        class="count-material-input"
                        data-index="${index}"
                        type="checkbox"
                        ${tieneMaterial && controlaMaterial ? "checked" : ""}
                        ${tieneMaterial ? "" : "disabled"}
                    >
                    <span>
                        <strong>${tieneMaterial ? "Contar materia prima" : "Sin MP asociada"}</strong>
                        <small>
                            ${tieneMaterial
                                ? "Genera la fila de material sin usar"
                                : "produc01 no informa MATE_"}
                        </small>
                    </span>
                </label>
            `}

            <input
                class="location-input"
                data-index="${index}"
                value="${escapeHtml(item.ubicacion || "")}"
                placeholder="Ubicación opcional"
                aria-label="Ubicación de ${escapeHtml(item.codigo)}"
            >

            <button
                type="button"
                class="remove-piece"
                data-index="${index}"
                title="Quitar pieza"
                aria-label="Quitar ${escapeHtml(item.codigo)}"
            >×</button>
        </article>
    `;
    }).join("");

    $$(".location-input").forEach((input) => {
        input.addEventListener("input", () => {
            editorState.items[Number(input.dataset.index)].ubicacion = input.value;
        });
    });
    $$(".count-material-input").forEach((input) => {
        input.addEventListener("change", () => {
            editorState.items[Number(input.dataset.index)].contar_material =
                input.checked;
        });
    });
    $$(".remove-piece").forEach((button) => {
        button.addEventListener("click", () => {
            const removed = editorState.items.splice(
                Number(button.dataset.index),
                1
            )[0];
            if (editorState.category === "CICLICO") {
                editorState.structure = null;
                renderStructure();
            }
            renderPieces();
            showStatus(
                `${itemTypeName()} ${removed.codigo} quitado de la plantilla.`
            );
        });
    });

    if (count) {
        $("#pieces-list")
            .querySelector(`[data-piece-index="${count - 1}"]`)
            ?.scrollIntoView?.({ block: "nearest" });
    }
}

async function loadStructure(code) {
    try {
        editorState.structure = await requestJson(
            `/api/estructuras/${encodeURIComponent(code)}`
        );
        renderStructure();
    } catch (error) {
        editorState.structure = null;
        renderStructure();
        showStatus(error.message, true);
    }
}

function renderStructure() {
    const panel = $("#structure-preview");
    const structure = editorState.structure;
    const visible = editorState.category === "CICLICO" && Boolean(structure);
    panel.classList.toggle("hidden", !visible);
    if (!visible) {
        $("#structure-list").innerHTML = "";
        return;
    }

    $("#structure-title").textContent = `Raíz ${structure.codigo_raiz}`;
    $("#structure-count").textContent =
        `${structure.cantidad_codigos} códigos`;
    $("#structure-list").innerHTML = structure.nodos.map((node) => `
        <div class="structure-node" style="--level:${Math.min(Number(node.nivel) || 0, 8)}">
            <span class="structure-level">N${escapeHtml(node.nivel)}</span>
            <div>
                <strong>${escapeHtml(node.codigo)}</strong>
                <small>
                    ${node.codigo_padre
                        ? `Depende de ${escapeHtml(node.codigo_padre)}`
                        : "Pieza raíz"}
                </small>
            </div>
            <span class="structure-usage">
                Uso ${formatUsage(node.uso_acumulado)}
            </span>
        </div>
    `).join("");
}

async function saveTemplate(event) {
    event.preventDefault();
    if (!editorState.items.length) {
        showStatus(
            editorState.category === "MATERIA_PRIMA"
                ? "Agregá al menos una materia prima antes de guardar."
                : (editorState.category === "CICLICO"
                    ? "Elegí una pieza raíz antes de guardar."
                    : "Agregá al menos una pieza antes de guardar."),
            true
        );
        $("#piece-code").focus();
        return;
    }

    const payload = {
        nombre: $("#template-name").value.trim(),
        cliente: $("#template-client").value.trim(),
        descripcion: $("#template-description").value.trim(),
        categoria: editorState.category,
        tipo_inventario_codigo: $("#template-inventory-type").value,
        tipo_conteo: editorState.category === "MATERIA_PRIMA"
            ? "GLOBAL"
            : $("#template-count-type").value,
        controla_remitos: $("#template-controls-delivery-notes").checked,
        activa: $("#template-active").checked,
        formato_impresion: "FLUJO_HORIZONTAL",
        items: editorState.items.map((item) => ({
            codigo: item.codigo,
            ubicacion: item.ubicacion || "",
            contar_material: editorState.category === "MATERIA_PRIMA"
                ? true
                : Boolean(item.contar_material),
        })),
    };

    const button = $("#save-template");
    button.disabled = true;
    button.textContent = "Guardando…";
    try {
        await requestJson(
            editorState.templateId
                ? `/api/plantillas/${editorState.templateId}`
                : "/api/plantillas",
            {
                method: editorState.templateId ? "PUT" : "POST",
                body: JSON.stringify(payload),
            }
        );
        window.location.href = "/plantillas";
    } catch (error) {
        showStatus(error.message, true);
        button.disabled = false;
        button.textContent = editorState.templateId
            ? "Guardar cambios"
            : "Guardar plantilla";
    }
}

function changeCategory(event) {
    const newCategory = event.target.value;
    if (editorState.items.length) {
        const confirmed = window.confirm(
            "Al cambiar el tipo se quitarán los códigos ya agregados. ¿Continuar?"
        );
        if (!confirmed) {
            event.target.value = editorState.category;
            return;
        }
    }
    editorState.category = newCategory;
    hideItemSuggestions();
    editorState.items = [];
    editorState.structure = null;
    applyCategoryUI();
    renderPieces();
    renderStructure();
    $("#piece-code").value = "";
    $("#piece-status").classList.add("hidden");
}

function applyCategoryUI() {
    const esMaterial = editorState.category === "MATERIA_PRIMA";
    const esCiclico = editorState.category === "CICLICO";
    $("#item-search-title").textContent = esMaterial
        ? "Agregar materias primas"
        : (esCiclico ? "Elegir pieza raíz" : "Agregar piezas");
    $("#item-search-help").textContent = esMaterial
        ? "Los códigos se validan contra mtprim01 y se completan automáticamente."
        : (esCiclico
            ? "La raíz se valida en produc01 y su estructura completa se recorre desde produc10."
            : "Los códigos se validan contra produc01 antes de incorporarlos.");
    $("#item-code-label").textContent = esMaterial
        ? "Código de materia prima"
        : (esCiclico ? "Código de pieza raíz" : "Código de pieza");
    $("#piece-code").placeholder = esMaterial
        ? "Ej. CA2-02.00-06"
        : "Ej. 284994";
    $("#items-title").textContent = esMaterial
        ? "Materias primas incluidas"
        : (esCiclico ? "Pieza raíz seleccionada" : "Piezas incluidas");
    $("#empty-items-title").textContent = esMaterial
        ? "Todavía no agregaste materias primas"
        : (esCiclico
            ? "Todavía no elegiste la pieza raíz"
            : "Todavía no agregaste piezas");
    $("#count-type-field").classList.toggle("hidden", esMaterial);
    renderStructure();
}

function medidasMaterial(item) {
    const partes = [
        item.diametro ? `Ø ${item.diametro}` : "",
        item.largo ? `L ${item.largo}` : "",
        item.espesor ? `Esp. ${item.espesor}` : "",
    ].filter(Boolean);
    return partes.length ? partes.join(" · ") : "Sin medidas";
}

function itemTypeName() {
    if (editorState.category === "MATERIA_PRIMA") return "Material";
    if (editorState.category === "CICLICO") return "Raíz";
    return "Pieza";
}

function formatUsage(value) {
    return new Intl.NumberFormat("es-AR", {
        maximumFractionDigits: 4,
    }).format(Number(value) || 0);
}

function structureRoleHtml(type) {
    const normalized = String(type || "INDEPENDIENTE").toUpperCase();
    const labels = {
        PADRE: "Padre",
        SUBCONJUNTO: "Subconjunto",
        HIJO: "Hijo",
        INDEPENDIENTE: "Independiente",
    };
    return `
        <span class="structure-role role-${normalized.toLowerCase()}">
            ${labels[normalized] || "Independiente"}
        </span>
    `;
}

function formatDateTime(value) {
    if (!value) return "Sin registro";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("es-AR", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(date);
}

function showStatus(message, isError = false) {
    const status = $("#piece-status");
    status.textContent = message;
    status.classList.toggle("error", isError);
    status.classList.remove("hidden");
}

function setLoading(value) {
    $("#page-loading").classList.toggle("hidden", !value);
}

function normalCode(value) {
    return String(value || "").trim().toUpperCase();
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
    })[character]);
}
