const causeState = { causes: [] };
const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", () => {
    $("#new-cause").addEventListener("click", () => openCauseModal());
    $("#cause-search").addEventListener("input", renderCauses);
    $("#cause-status").addEventListener("change", renderCauses);
    $("#cause-form").addEventListener("submit", saveCause);
    $("#close-cause-modal").addEventListener("click", closeCauseModal);
    $("#cancel-cause").addEventListener("click", closeCauseModal);
    $("#cause-modal").addEventListener("mousedown", (event) => {
        if (event.target === $("#cause-modal")) closeCauseModal();
    });
    loadCauses();
});

async function requestJson(url, options = {}) {
    setLoading(true);
    try {
        const response = await fetch(url, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        const body = response.status === 204
            ? null
            : await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error(body?.detail || "No se pudo completar la operación");
        }
        return body;
    } finally {
        setLoading(false);
    }
}

async function loadCauses() {
    try {
        const data = await requestJson("/api/causas-diferencia");
        causeState.causes = data.causas || [];
        renderCauses();
    } catch (error) {
        toast(error.message, true);
    }
}

function renderCauses() {
    const term = $("#cause-search").value.trim().toLowerCase();
    const status = $("#cause-status").value;
    const filtered = causeState.causes.filter((cause) => {
        const matches = [
            cause.codigo,
            cause.nombre,
            cause.descripcion,
            categoryLabel(cause.categoria),
        ].join(" ").toLowerCase().includes(term);
        const matchesStatus =
            status === "TODAS"
            || (status === "ACTIVAS" && cause.activa)
            || (status === "INACTIVAS" && !cause.activa);
        return matches && matchesStatus;
    });

    $("#metric-total").textContent = causeState.causes.length;
    $("#metric-active").textContent =
        causeState.causes.filter((cause) => cause.activa).length;
    $("#metric-used").textContent =
        causeState.causes.filter((cause) => cause.usos > 0).length;
    $("#causes-empty").classList.toggle("hidden", filtered.length > 0);
    $("#causes-table").innerHTML = filtered.map((cause) => `
        <tr>
            <td>${cause.orden}</td>
            <td class="cause-name">
                <strong>${escapeHtml(cause.nombre)}</strong>
                <small>${escapeHtml(cause.codigo)}</small>
            </td>
            <td><span class="category">${escapeHtml(categoryLabel(cause.categoria))}</span></td>
            <td class="description">${escapeHtml(cause.descripcion || "Sin descripción")}</td>
            <td>${cause.usos}</td>
            <td>
                <span class="status ${cause.activa ? "active" : "inactive"}">
                    ${cause.activa ? "Activa" : "Inactiva"}
                </span>
            </td>
            <td>
                <div class="row-actions">
                    <button class="row-action edit" data-code="${escapeHtml(cause.codigo)}" type="button">Editar</button>
                    <button class="row-action delete" data-code="${escapeHtml(cause.codigo)}" type="button" ${cause.usos ? "disabled title='Tiene historial asociado'" : ""}>Eliminar</button>
                </div>
            </td>
        </tr>
    `).join("");

    document.querySelectorAll(".row-action.edit").forEach((button) => {
        button.addEventListener("click", () => {
            openCauseModal(
                causeState.causes.find((cause) => cause.codigo === button.dataset.code)
            );
        });
    });
    document.querySelectorAll(".row-action.delete:not(:disabled)").forEach((button) => {
        button.addEventListener("click", () => deleteCause(button.dataset.code));
    });
}

function openCauseModal(cause = null) {
    $("#cause-code").value = cause?.codigo || "";
    $("#cause-name").value = cause?.nombre || "";
    $("#cause-category").value = cause?.categoria || "OTRA";
    $("#cause-order").value = cause?.orden ?? nextOrder();
    $("#cause-description").value = cause?.descripcion || "";
    $("#cause-active").checked = cause?.activa ?? true;
    $("#cause-modal-title").textContent = cause ? "Editar causa" : "Nueva causa";
    $("#save-cause").textContent = cause ? "Guardar cambios" : "Crear causa";
    $("#cause-code-note").textContent = cause
        ? `Código histórico: ${cause.codigo}`
        : "El código interno se generará automáticamente a partir del nombre.";
    $("#cause-code-note").classList.remove("hidden");
    $("#cause-error").classList.add("hidden");
    $("#cause-modal").classList.remove("hidden");
    $("#cause-name").focus();
}

function closeCauseModal() {
    $("#cause-modal").classList.add("hidden");
}

async function saveCause(event) {
    event.preventDefault();
    const code = $("#cause-code").value;
    const payload = {
        nombre: $("#cause-name").value.trim(),
        descripcion: $("#cause-description").value.trim(),
        categoria: $("#cause-category").value,
        orden: Number($("#cause-order").value) || 0,
        activa: $("#cause-active").checked,
    };
    try {
        await requestJson(
            code
                ? `/api/causas-diferencia/${encodeURIComponent(code)}`
                : "/api/causas-diferencia",
            {
                method: code ? "PUT" : "POST",
                body: JSON.stringify(payload),
            }
        );
        closeCauseModal();
        await loadCauses();
        toast(code ? "Causa actualizada" : "Causa creada");
    } catch (error) {
        $("#cause-error").textContent = error.message;
        $("#cause-error").classList.remove("hidden");
    }
}

async function deleteCause(code) {
    const cause = causeState.causes.find((item) => item.codigo === code);
    if (!cause || !window.confirm(`¿Eliminar la causa "${cause.nombre}"?`)) return;
    try {
        await requestJson(`/api/causas-diferencia/${encodeURIComponent(code)}`, {
            method: "DELETE",
        });
        await loadCauses();
        toast("Causa eliminada");
    } catch (error) {
        toast(error.message, true);
    }
}

function nextOrder() {
    return causeState.causes.length
        ? Math.max(...causeState.causes.map((cause) => Number(cause.orden) || 0)) + 10
        : 10;
}

function categoryLabel(value) {
    return {
        PRODUCCION: "Producción",
        DOCUMENTACION: "Documentación",
        CONTEO: "Conteo",
        UBICACION: "Ubicación",
        SISTEMA: "Sistema",
        OTRA: "Otra",
    }[value] || value;
}

function setLoading(value) {
    $("#loading").classList.toggle("hidden", !value);
}

function toast(message, isError = false) {
    const element = $("#toast");
    element.textContent = message;
    element.classList.toggle("error", isError);
    element.classList.remove("hidden");
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => element.classList.add("hidden"), 2600);
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
