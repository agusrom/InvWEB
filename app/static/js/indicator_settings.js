const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", () => {
    $("#indicator-settings-form").addEventListener("submit", saveSettings);
    loadSettings();
});

async function requestJson(url, options = {}) {
    setLoading(true);
    try {
        const response = await fetch(url, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        const body = await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error(body?.detail || "No se pudo completar la operación");
        }
        return body;
    } finally {
        setLoading(false);
    }
}

async function loadSettings() {
    try {
        const data = await requestJson("/api/configuracion/indicadores");
        $("#setting-tolerance").value = data.tolerancia_pct;
        $("#setting-target").value = data.objetivo_confiabilidad_pct;
        $("#setting-client-alert").value = data.alerta_cliente_pct;
        $("#setting-minimum-sample").value = data.minimo_renglones_alerta;
    } catch (error) {
        toast(error.message, true);
    }
}

async function saveSettings(event) {
    event.preventDefault();
    const errorElement = $("#indicator-settings-error");
    errorElement.classList.add("hidden");
    const payload = {
        tolerancia_pct: Number($("#setting-tolerance").value),
        objetivo_confiabilidad_pct: Number($("#setting-target").value),
        alerta_cliente_pct: Number($("#setting-client-alert").value),
        minimo_renglones_alerta: Number($("#setting-minimum-sample").value),
    };
    if (payload.alerta_cliente_pct > payload.objetivo_confiabilidad_pct) {
        errorElement.textContent =
            "La alerta por cliente no puede superar el objetivo.";
        errorElement.classList.remove("hidden");
        return;
    }
    try {
        await requestJson("/api/configuracion/indicadores", {
            method: "PUT",
            body: JSON.stringify(payload),
        });
        toast("Configuración de indicadores actualizada");
    } catch (error) {
        errorElement.textContent = error.message;
        errorElement.classList.remove("hidden");
    }
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
    toast.timer = window.setTimeout(
        () => element.classList.add("hidden"),
        2600
    );
}
