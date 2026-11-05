/* Configuración al crear; resultados al revisar. Los controles conservan sus eventos. */
function registerWorkspaceEvents() {
    const dialog = $("#analysis-configuration-dialog");
    $("#edit-analysis-configuration").addEventListener("click", () => {
        if (state.busy || mutationPending) return toast("Esperá a que termine la operación actual", true);
        if (state.timers.size || noteSavesPending || [...failedNoteSaves].some((key) => key.startsWith(`${inventoryId}:`)) || document.querySelector(".remittance-group.dirty")) return toast("Guardá las ediciones pendientes antes de cambiar períodos", true);
        $("#selector-message").textContent = "";
        $("#selector-message").classList.remove("error");
        if (!dialog.open) dialog.showModal();
    });
    const restoreSelection = () => {
        if (!state.calculation) return;
        const ids = state.calculation.escenarios.map((p) => p.inicial.id);
        document.querySelectorAll("#initial-options input").forEach((input) => { input.checked = ids.includes(Number(input.value)); });
        renderSnapshotState();
    };
    const close = () => { if (!state.busy) { restoreSelection(); dialog.close(); } };
    $("#close-analysis-configuration").addEventListener("click", close);
    $("#cancel-analysis-configuration").addEventListener("click", close);
    dialog.addEventListener("cancel", (event) => { if (state.busy) event.preventDefault(); else restoreSelection(); });
    dialog.addEventListener("close", () => {
        // Un evento de cierre anterior no debe tocar una configuración reabierta.
        if (dialog.open) return;
        restoreSelection();
        $("#edit-analysis-configuration").focus({ preventScroll: true });
    });
    const menu = $("#analysis-export-menu");
    document.addEventListener("click", (event) => {
        if (!event.target.closest("#analysis-export-menu") || event.target.closest("#analysis-export-menu button")) menu.open = false;
    });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") menu.open = false; });
    if (typeof ResizeObserver !== "undefined") {
        new ResizeObserver(() => {
            const toolbar = $(".review-toolbar");
            document.documentElement.style.setProperty("--review-toolbar-height", `${toolbar.getBoundingClientRect().height}px`);
        }).observe($(".review-toolbar"));
    }
}

function syncWorkspaceLayout() {
    const reviewing = Boolean(state.calculation);
    const dialog = $("#analysis-configuration-dialog");
    const configuration = $("#analysis-configuration");
    const host = $(reviewing ? "#analysis-configuration-dialog-host" : "#analysis-configuration-host");
    if (configuration.parentElement !== host) host.append(configuration);
    const calculate = $("#calculate");
    const actions = reviewing ? $(".configuration-dialog-footer") : configuration.querySelector(".selector-actions");
    if (calculate.parentElement !== actions) actions.append(calculate);
    if (!state.busy) calculate.textContent = reviewing ? "Aplicar y recalcular" : "Calcular escenarios";
    // Un cálculo correcto aplica la configuración y devuelve el foco a los resultados.
    if (dialog.open) dialog.close();
    document.body.classList.toggle("analysis-review", reviewing);
    $("#analysis-configuration-host").classList.toggle("hidden", reviewing);
    $("#edit-analysis-configuration").classList.toggle("hidden", !reviewing);
    $("#refresh-final").disabled = !state.setup;
    $("#analysis-period-context").textContent = reviewing
        ? `${state.calculation.escenarios.length} ${state.calculation.escenarios.length === 1 ? "inventario inicial" : "inventarios iniciales"} → ${state.calculation.inventario_final?.codigo || state.setup.final.codigo}`
        : "Elegí los inventarios para comenzar";
    if (reviewing && state.analysisName) {
        $("#analysis-title").textContent = state.analysisName;
        document.title = `${state.analysisName} · Análisis de stock`;
    }
}
