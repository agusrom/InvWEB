const state = { formats: [], current: null, config: null };
const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", () => {
    $("#save-format").addEventListener("click", saveFormat);
    $("#fit-widths").addEventListener("click", fitWidths);
    $("#source-version").addEventListener("change", selectSourceVersion);
    $("#version-name").addEventListener("input", () => {
        if (state.config) state.config.nombre = $("#version-name").value;
    });
    $("#font-size").addEventListener("input", () => {
        if (!state.config) return;
        const size = Number($("#font-size").value);
        state.config.tamano_fuente_pt = size;
        state.config.columnas.forEach((column) => {
            column.tamano_fuente_pt = size;
        });
        renderColumns();
        renderPreview();
    });
    [
        "#orientation", "#row-height", "#show-signatures",
        "#margin-top", "#margin-right", "#margin-bottom", "#margin-left",
    ].forEach((selector) => {
        $(selector).addEventListener("input", readGeneralSettings);
    });
    loadFormats();
});

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(body?.detail || "No se pudo completar la operación");
    return body;
}

async function loadFormats() {
    try {
        const data = await api("/api/formatos-impresion");
        state.formats = data.formatos || [];
        renderFormatList();
        if (state.formats.length) await selectFormat(state.formats[0].codigo);
    } catch (error) {
        toast(error.message, true);
    }
}

function renderFormatList() {
    $("#format-list").innerHTML = state.formats.map((format) => `
        <button class="format-option ${format.codigo === state.current?.codigo ? "active" : ""}"
            data-code="${escapeHtml(format.codigo)}" type="button">
            <strong>${escapeHtml(format.nombre)}</strong>
            <small>${escapeHtml(format.descripcion)}</small>
        </button>
    `).join("");
    document.querySelectorAll(".format-option").forEach((button) => {
        button.addEventListener("click", () => selectFormat(button.dataset.code));
    });
}

async function selectFormat(code) {
    try {
        setLoading(true);
        state.current = await api(`/api/formatos-impresion/${encodeURIComponent(code)}`);
        state.config = structuredClone(state.current.configuracion);
        renderFormatList();
        renderVersionList();
        writeControls();
        renderColumns();
        renderPreview();
    } catch (error) {
        toast(error.message, true);
    } finally {
        setLoading(false);
    }
}

function renderVersionList() {
    const versions = state.current?.versiones || [];
    $("#source-version").innerHTML = versions.map((version) => `
        <option value="${version.id}" ${version.id === state.config?.id ? "selected" : ""}>
            ${escapeHtml(version.nombre)} · v${version.numero}
        </option>
    `).join("");
}

function selectSourceVersion(event) {
    const versionId = Number(event.target.value);
    const version = (state.current?.versiones || []).find(
        (item) => item.id === versionId
    );
    if (!version) return;
    state.config = structuredClone(version);
    writeControls();
    renderColumns();
    renderPreview();
}

function writeControls() {
    const config = state.config;
    $("#version-badge").textContent = `${config.nombre} · v${config.numero}`;
    $("#source-version").value = String(config.id);
    $("#version-name").value = config.nombre;
    $("#orientation").value = config.orientacion;
    $("#font-size").value = config.tamano_fuente_pt;
    $("#row-height").value = config.altura_fila_mm;
    $("#show-signatures").checked = config.mostrar_firmas;
    $("#margin-top").value = config.margen_superior_mm;
    $("#margin-right").value = config.margen_derecho_mm;
    $("#margin-bottom").value = config.margen_inferior_mm;
    $("#margin-left").value = config.margen_izquierdo_mm;
}

function readGeneralSettings() {
    if (!state.config) return;
    state.config.orientacion = $("#orientation").value;
    state.config.tamano_fuente_pt = Number($("#font-size").value);
    state.config.altura_fila_mm = Number($("#row-height").value);
    state.config.mostrar_firmas = $("#show-signatures").checked;
    state.config.margen_superior_mm = Number($("#margin-top").value);
    state.config.margen_derecho_mm = Number($("#margin-right").value);
    state.config.margen_inferior_mm = Number($("#margin-bottom").value);
    state.config.margen_izquierdo_mm = Number($("#margin-left").value);
    renderPreview();
}

function renderColumns() {
    $("#column-list").innerHTML = state.config.columnas.map((column, index) => `
        <div class="column-row ${column.visible ? "" : "hidden-column"}" data-index="${index}">
            <input class="visibility" type="checkbox" ${column.visible ? "checked" : ""} aria-label="Mostrar columna">
            <input class="column-title" type="text" maxlength="100" value="${escapeHtml(column.titulo)}">
            <label class="width-box">
                <input class="column-width" type="number" min="2" max="80" step="0.5" value="${round(column.ancho_pct)}">
                <b>%</b>
            </label>
            <label class="font-box" title="Tamaño de fuente de esta columna">
                <input class="column-font-size" type="number" min="5" max="18" step="0.5"
                    value="${round(column.tamano_fuente_pt ?? state.config.tamano_fuente_pt)}">
                <b>pt</b>
            </label>
            <label class="bold-box" title="Texto en negrita">
                <input class="column-bold" type="checkbox" ${column.negrita ? "checked" : ""}>
                <b>B</b>
            </label>
            <div class="move-buttons">
                <button class="move-up" type="button" aria-label="Subir">▲</button>
                <button class="move-down" type="button" aria-label="Bajar">▼</button>
            </div>
        </div>
    `).join("");

    document.querySelectorAll(".column-row").forEach((row) => {
        const index = Number(row.dataset.index);
        row.querySelector(".visibility").addEventListener("change", (event) => {
            state.config.columnas[index].visible = event.target.checked;
            renderColumns();
            renderPreview();
        });
        row.querySelector(".column-title").addEventListener("input", (event) => {
            state.config.columnas[index].titulo = event.target.value;
            renderPreview();
        });
        row.querySelector(".column-width").addEventListener("input", (event) => {
            state.config.columnas[index].ancho_pct = Number(event.target.value);
            updateTotal();
            renderPreview();
        });
        row.querySelector(".column-font-size").addEventListener("input", (event) => {
            state.config.columnas[index].tamano_fuente_pt = Number(event.target.value);
            renderPreview();
        });
        row.querySelector(".column-bold").addEventListener("change", (event) => {
            state.config.columnas[index].negrita = event.target.checked;
            renderPreview();
        });
        row.querySelector(".move-up").addEventListener("click", () => moveColumn(index, -1));
        row.querySelector(".move-down").addEventListener("click", () => moveColumn(index, 1));
    });
    updateTotal();
}

function moveColumn(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= state.config.columnas.length) return;
    const [column] = state.config.columnas.splice(index, 1);
    state.config.columnas.splice(target, 0, column);
    renderColumns();
    renderPreview();
}

function visibleColumns() {
    return state.config.columnas.filter((column) => column.visible);
}

function updateTotal() {
    const total = visibleColumns().reduce((sum, column) => sum + Number(column.ancho_pct), 0);
    $("#width-total").textContent = `${round(total)}%`;
    $("#width-total").classList.toggle("warning", Math.abs(total - 100) > 0.2);
}

function fitWidths() {
    const columns = visibleColumns();
    if (!columns.length) return;
    const total = columns.reduce((sum, column) => sum + Number(column.ancho_pct), 0);
    columns.forEach((column) => {
        column.ancho_pct = total > 0
            ? (Number(column.ancho_pct) / total) * 100
            : 100 / columns.length;
    });
    renderColumns();
    renderPreview();
}

function renderPreview() {
    if (!state.config) return;
    const columns = visibleColumns();
    const paper = $("#paper");
    paper.classList.toggle("portrait", state.config.orientacion === "VERTICAL");
    paper.style.padding = `${Math.max(8, state.config.margen_superior_mm * 1.35)}px ${Math.max(8, state.config.margen_derecho_mm * 1.35)}px ${Math.max(8, state.config.margen_inferior_mm * 1.35)}px ${Math.max(8, state.config.margen_izquierdo_mm * 1.35)}px`;
    $("#preview-title").textContent = state.current.nombre;
    $("#preview-cols").innerHTML = columns.map((column) =>
        `<col style="width:${column.ancho_pct}%">`
    ).join("");
    $("#preview-head").innerHTML = columns.map((column, index) => `
        <th data-index="${index}">
            ${escapeHtml(column.titulo)}
            ${index < columns.length - 1 ? '<span class="resize-handle"></span>' : ""}
        </th>
    `).join("");
    const samples = [0, 1, 2];
    $("#preview-body").innerHTML = samples.map((row) => `
        <tr>${columns.map((column) => `
            <td style="
                height:${Math.max(22, state.config.altura_fila_mm * 2.15)}px;
                font-size:${Math.max(5, (column.tamano_fuente_pt ?? state.config.tamano_fuente_pt) * .78)}px;
                font-weight:${column.negrita ? 700 : 400}
            ">
                ${escapeHtml(sampleValue(column.clave, row))}
            </td>
        `).join("")}</tr>
    `).join("");
    $("#preview-signatures").classList.toggle("hidden", !state.config.mostrar_firmas);
    bindResizeHandles();
    updateTotal();
}

function bindResizeHandles() {
    document.querySelectorAll(".resize-handle").forEach((handle) => {
        handle.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            const visible = visibleColumns();
            const visibleIndex = Number(handle.parentElement.dataset.index);
            const left = visible[visibleIndex];
            const right = visible[visibleIndex + 1];
            const startX = event.clientX;
            const startLeft = Number(left.ancho_pct);
            const startRight = Number(right.ancho_pct);
            const tableWidth = $("#preview-table").getBoundingClientRect().width;

            const move = (moveEvent) => {
                const delta = ((moveEvent.clientX - startX) / tableWidth) * 100;
                const limited = Math.max(
                    2 - startLeft,
                    Math.min(startRight - 2, delta)
                );
                left.ancho_pct = startLeft + limited;
                right.ancho_pct = startRight - limited;
                renderPreview();
            };
            const up = () => {
                document.removeEventListener("pointermove", move);
                document.removeEventListener("pointerup", up);
                renderColumns();
            };
            document.addEventListener("pointermove", move);
            document.addEventListener("pointerup", up);
        });
    });
}

async function saveFormat() {
    const visible = visibleColumns();
    if (visible.length < 2) {
        toast("Dejá al menos dos columnas visibles.", true);
        return;
    }
    fitWidths();
    const payload = {
        nombre: $("#version-name").value.trim(),
        orientacion: state.config.orientacion,
        margen_superior_mm: state.config.margen_superior_mm,
        margen_derecho_mm: state.config.margen_derecho_mm,
        margen_inferior_mm: state.config.margen_inferior_mm,
        margen_izquierdo_mm: state.config.margen_izquierdo_mm,
        tamano_fuente_pt: state.config.tamano_fuente_pt,
        altura_fila_mm: state.config.altura_fila_mm,
        mostrar_firmas: state.config.mostrar_firmas,
        columnas: state.config.columnas.map((column) => ({
            clave: column.clave,
            titulo: column.titulo.trim(),
            visible: column.visible,
            ancho_pct: Number(column.ancho_pct),
            tamano_fuente_pt: Number(
                column.tamano_fuente_pt ?? state.config.tamano_fuente_pt
            ),
            negrita: Boolean(column.negrita),
        })),
    };
    if (!payload.nombre) {
        toast("Ingresá un nombre para guardar el diseño.", true);
        $("#version-name").focus();
        return;
    }
    try {
        setLoading(true);
        const result = await api(
            `/api/formatos-impresion/${encodeURIComponent(state.current.codigo)}`,
            { method: "PUT", body: JSON.stringify(payload) }
        );
        state.config = result.configuracion;
        state.current.configuracion = result.configuracion;
        state.current.version_actual = result.configuracion.numero;
        state.current.versiones = [
            result.configuracion,
            ...(state.current.versiones || []),
        ];
        const listed = state.formats.find(
            (item) => item.codigo === state.current.codigo
        );
        if (listed) listed.version_actual = result.configuracion.numero;
        renderVersionList();
        writeControls();
        renderColumns();
        renderPreview();
        toast(result.mensaje);
    } catch (error) {
        toast(error.message, true);
    } finally {
        setLoading(false);
    }
}

function sampleValue(key, row) {
    const values = {
        numero: String(row + 1), codigo: ["551804", "551805", "551806"][row],
        codigo_cliente: ["CLIENTE-018", "CLIENTE-022", "CLIENTE-031"][row],
        descripcion: ["Conjunto manubrio", "Soporte de línea", "Pieza terminada"][row],
        uso: row === 0 ? "1" : "2", etapa: "En proceso", operacion: "OP 20 · Soldadura",
        proveedor: "Proveedor", ubicacion: "Rack A3", nivel: `N${row}`,
        padre: row ? "551804" : "—", abastecimiento: "", despacho: "",
        linea: "", scrap: "", stock_final: "", conteo: "", observaciones: "",
        vacios: "", llenos: "", rotos: "",
    };
    return values[key] ?? "";
}

function setLoading(active) { $("#loading").classList.toggle("hidden", !active); }
function toast(message, error = false) {
    const element = $("#toast");
    element.textContent = message;
    element.classList.toggle("error", error);
    element.classList.remove("hidden");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => element.classList.add("hidden"), 3400);
}
function round(value) { return Math.round(Number(value) * 10) / 10; }
function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
    })[char]);
}
