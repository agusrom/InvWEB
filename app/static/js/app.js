const state = {
    plantillas: [],
    inventarios: [],
    programaciones: [],
    conciliaciones: [],
    causasDiferencia: [],
    tiposInventario: [],
    personas: [],
    configuracionIndicadores: {
        tolerancia_pct: 5,
        objetivo_confiabilidad_pct: 90,
        alerta_cliente_pct: 85,
        minimo_renglones_alerta: 3,
    },
    inventarioSeleccionado: null,
    conciliacionSeleccionada: null,
    vistaInventarios: "EN_CURSO",
    vistaProgramaciones: "LISTA",
    periodoCalendario: "MES",
    fechaCalendario: new Date(),
    vistaConteo: "PIEZA",
    datosInventarioAbiertos: false,
    remitosAbiertos: false,
    focoDiferenciasAbierto: false,
    countRecordsItemId: null,
    countRecordsMaterialIds: [],
};

const cyclicAutocompleteState = {
    results: [],
    activeIndex: -1,
    timer: null,
    controller: null,
};

const manualAutocompleteState = {
    results: [],
    activeIndex: -1,
    timer: null,
    controller: null,
    error: "",
};

const addArticleAutocompleteState = {
    timer: null,
    controller: null,
};

let manualInventoryArticles = [];

const autosave = {
    conteo: { timer: null, running: false, dirty: false, failed: false },
    conciliacion: { timer: null, running: false, dirty: false, failed: false },
};

function estadoAutoguardado(tipo, estado, mensaje = "") {
    const elemento = document.querySelector(`#${tipo}-autosave-status`);
    if (!elemento) return;
    elemento.className = `autosave-status ${estado}`;
    elemento.textContent = mensaje || ({
        saved: "✓ Guardado", saving: "● Guardando…",
        error: "⚠ No se pudo guardar",
    }[estado]);
}

function hayAutoguardadoPendiente() {
    return Object.values(autosave).some(
        (item) => item.running || item.dirty || item.failed || item.timer
    );
}

window.addEventListener("beforeunload", (event) => {
    if (!hayAutoguardadoPendiente()) return;
    event.preventDefault();
    event.returnValue = "";
});

function programarAutoguardado(tipo, demora = 700) {
    const control = autosave[tipo];
    if (tipo === "conteo" && state.inventarioSeleccionado) {
        control.context = {
            id: state.inventarioSeleccionado.id,
            payload: datosConteoActuales(),
        };
    }
    if (tipo === "conciliacion" && state.conciliacionSeleccionada) {
        control.context = {
            id: state.conciliacionSeleccionada.id,
            payload: {
                items: movimientosConciliacion(),
                controles_ingreso: controlesIngresoConciliacion(),
                controles_egreso: controlesEgresoConciliacion(),
            },
        };
    }
    control.dirty = true;
    control.failed = false;
    estadoAutoguardado(tipo, "saving", "● Pendiente…");
    window.clearTimeout(control.timer);
    control.timer = window.setTimeout(() => ejecutarAutoguardado(tipo), demora);
}

async function ejecutarAutoguardado(tipo) {
    const control = autosave[tipo];
    control.timer = null;
    if (control.running || !control.dirty) return;
    control.running = true;
    control.dirty = false;
    estadoAutoguardado(tipo, "saving");
    try {
        const contexto = control.context;
        let guardado = null;
        if (tipo === "conteo") guardado = await guardarConteo({
            automatico: true, inventarioId: contexto.id, payload: contexto.payload,
        });
        if (tipo === "conciliacion") guardado = await guardarConciliacion({
            automatico: true, conciliacionId: contexto.id, payload: contexto.payload,
        });
        if (tipo === "conteo" && control.dirty && guardado
            && control.context?.id === contexto.id) {
            control.context.payload.revision_conteo = guardado.conteo_modificado_en;
        }
        control.failed = false;
        if (!control.dirty) estadoAutoguardado(tipo, "saved");
    } catch (_error) {
        control.failed = true;
        estadoAutoguardado(tipo, "error");
    } finally {
        control.running = false;
        if (control.dirty) ejecutarAutoguardado(tipo);
    }
}

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

document.addEventListener("DOMContentLoaded", async () => {
    try {
        state.vistaConteo =
            window.localStorage.getItem("vistaConteo") || "PIEZA";
    } catch (_error) {
        state.vistaConteo = "PIEZA";
    }
    registrarEventos();
    $("#inventario-fecha").value = fechaHoyLocal();
    $("#programacion-fecha").value = fechaHoyLocal();
    await cargarInicio();
    const vistaInicial = document.body.dataset.initialView
        || new URLSearchParams(window.location.search).get("view");
    if (["inventarios", "plantillas", "programados", "conciliaciones"].includes(vistaInicial)) {
        mostrarVista(vistaInicial);
    }
});

function registrarEventos() {
    $("#inventario-fecha").addEventListener("change", () => {
        actualizarMesSugerido(
            $("#inventario-fecha"),
            $("#inventario-mes-cierre")
        );
    });
    $("#inventario-mes-cierre").addEventListener("input", (event) => {
        if (event.isTrusted) event.currentTarget.dataset.automatico = "false";
    });
    $("#programacion-fecha").addEventListener("change", () => {
        actualizarMesSugerido(
            $("#programacion-fecha"),
            $("#programacion-mes-cierre")
        );
    });
    $("#programacion-mes-cierre").addEventListener("input", (event) => {
        if (event.isTrusted) event.currentTarget.dataset.automatico = "false";
    });
    $$("button.nav-button[data-view], button.brand[data-view]").forEach((boton) => {
        boton.addEventListener("click", () => mostrarVista(boton.dataset.view));
    });

    $("#btn-nuevo-inventario").addEventListener(
        "click",
        () => abrirModalInventario()
    );
    $("#btn-nueva-programacion").addEventListener(
        "click",
        () => abrirModalProgramacion()
    );
    $("#btn-nueva-plantilla").addEventListener("click", () => {
        window.location.href = "/plantillas/nueva";
    });
    $("#buscar-plantilla").addEventListener("input", renderPlantillas);
    $("#btn-nueva-conciliacion").addEventListener(
        "click",
        abrirModalConciliacion
    );
    $("#form-conciliacion").addEventListener(
        "submit",
        crearConciliacion
    );
    $("#btn-guardar-conciliacion").addEventListener(
        "click",
        guardarConciliacion
    );
    $("#btn-recalcular-conciliacion").addEventListener(
        "click",
        recalcularMovimientosConciliacion
    );
    $("#btn-eliminar-conciliacion").addEventListener(
        "click",
        eliminarConciliacion
    );
    $("#btn-agregar-ingreso-manual").addEventListener(
        "click",
        abrirModalIngresoManual
    );
    $("#form-ingreso-manual").addEventListener(
        "submit",
        agregarIngresoManual
    );
    $("#btn-agregar-egreso-manual").addEventListener(
        "click",
        abrirModalEgresoManual
    );
    $("#form-egreso-manual").addEventListener(
        "submit",
        agregarEgresoManual
    );
    $("#btn-volver").addEventListener("click", () => mostrarVista("inventarios"));
    $$("#count-view-tabs button").forEach((button) => {
        button.addEventListener("click", () => cambiarVistaConteo(
            button.dataset.countView
        ));
    });
    $("#btn-excel").addEventListener("click", exportarExcel);
    $("#btn-agregar-articulo").addEventListener(
        "click",
        abrirModalAgregarArticulo
    );
    $("#btn-actualizar-stock").addEventListener("click", abrirModalActualizarStock);
    $("#btn-stock-mysql").addEventListener("click", actualizarStockMysql);
    $("#form-stock-excel").addEventListener("submit", actualizarStockExcel);
    $("#form-count-records-add").addEventListener(
        "submit",
        agregarRegistrosDesdePC,
    );
    $("#btn-confirm-count-zero").addEventListener(
        "click",
        confirmarConteoCeroDesdePC,
    );
    $("#btn-back-material-lots").addEventListener("click", () => {
        abrirDetalleLotesMaterial(state.countRecordsMaterialIds);
    });
    $("#count-records-list").addEventListener("click", async (event) => {
        const abrir = event.target.closest("[data-open-lot-records]");
        if (abrir) {
            abrirDetalleRegistrosConteo(
                Number(abrir.dataset.openLotRecords),
                true,
            );
            return;
        }
        const agregar = event.target.closest("[data-modal-add-material-lot]");
        if (agregar) {
            await agregarLoteMaterialDesdeConteo(agregar);
            const codigo = agregar.dataset.modalAddMaterialLot;
            const lineas = state.inventarioSeleccionado?.items.filter((item) => (
                item.etapa === "MATERIAL"
                && String(item.codigo_material || item.codigo) === codigo
            )) || [];
            if (lineas.length) abrirDetalleLotesMaterial(lineas.map((item) => item.id));
            return;
        }
        const eliminar = event.target.closest("[data-modal-delete-material-lot]");
        if (eliminar) {
            const item = state.inventarioSeleccionado?.items.find(
                (linea) => linea.id === Number(eliminar.dataset.modalDeleteMaterialLot),
            );
            const codigo = String(item?.codigo_material || item?.codigo || "");
            await eliminarLoteMaterialDesdeConteo({
                dataset: { deleteMaterialLot: eliminar.dataset.modalDeleteMaterialLot },
            });
            const lineas = state.inventarioSeleccionado?.items.filter((linea) => (
                linea.etapa === "MATERIAL"
                && String(linea.codigo_material || linea.codigo) === codigo
            )) || [];
            if (lineas.length) abrirDetalleLotesMaterial(lineas.map((linea) => linea.id));
            return;
        }
        const eliminarRegistro = event.target.closest("[data-delete-count-record]");
        if (eliminarRegistro) {
            await eliminarRegistroConteoDesdePC(eliminarRegistro);
        }
    });
    $("#btn-guardar-conteo").addEventListener("click", guardarConteo);
    $("#btn-conteo-movil").addEventListener("click", () => {
        const inventario = state.inventarioSeleccionado;
        if (!inventario) return;
        window.location.href = `/inventarios/${inventario.id}/movil`;
    });
    $("#btn-difusion").addEventListener("click", () => {
        const inventario = state.inventarioSeleccionado;
        if (!inventario) return;
        window.open(
            `/inventarios/${inventario.id}/difusion`,
            "_blank",
            "noopener"
        );
    });
    $("#btn-preconciliacion").addEventListener("click", () => {
        const inventario = state.inventarioSeleccionado;
        if (!inventario) return;
        window.location.href = `/analisis-stock?inventario=${inventario.id}`;
    });
    $("#btn-guardar-datos").addEventListener("click", guardarDatosInventario);
    ["#detalle-ambito", "#detalle-comentario", "#remito-ingreso", "#remito-egreso"].forEach((selector) => {
        const input = $(selector);
        if (!input) return;
        input.addEventListener(input.tagName === "SELECT" ? "change" : "input", () => {
            programarAutoguardado("conteo");
        });
    });
    $("#detalle-mes-cierre").addEventListener("change", () => {
        guardarDatosInventario({ automatico: true }).catch(() => {});
    });
    $("#btn-toggle-inventory-data").addEventListener(
        "click",
        alternarDatosInventario
    );
    $("#btn-toggle-difference-focus").addEventListener(
        "click",
        alternarFocoDiferencias
    );
    $("#btn-toggle-remittances").addEventListener(
        "click",
        alternarControlRemitos
    );
    $("#btn-eliminar-inventario").addEventListener("click", eliminarInventario);
    $("#btn-cerrar").addEventListener("click", cerrarInventario);
    $("#btn-reabrir").addEventListener("click", reabrirInventario);
    $("#form-reabrir").addEventListener("submit", confirmarReaperturaInventario);
    $("#btn-iniciar-reconteo").addEventListener("click", abrirModalReconteo);
    $("#form-reconteo").addEventListener("submit", crearReconteo);
    $("#reconteo-seleccion").addEventListener("change", renderSeleccionReconteo);
    $("#reconteo-stock").addEventListener("change", (event) => {
        $("#reconteo-stock-ayuda").textContent = event.target.value === "ACTUALIZADO"
            ? "Se consultará una nueva fotografía. La comparación final distinguirá ambos stocks."
            : "Permite comparar ambos conteos bajo la misma fotografía.";
    });
    $$(".action-menu").forEach((menu) => {
        menu.addEventListener("toggle", () => {
            if (!menu.open) return;
            $$(".action-menu").forEach((otro) => {
                if (otro !== menu) otro.open = false;
            });
        });
    });
    document.addEventListener("click", (event) => {
        const menu = event.target.closest(".action-menu");
        if (menu) {
            if (event.target.closest(".action-menu-popover button")) {
                window.setTimeout(() => {
                    menu.open = false;
                }, 0);
            }
            return;
        }
        $$(".action-menu").forEach((menu) => {
            menu.open = false;
        });
    }, true);
    $("#buscar-inventario").addEventListener("input", renderInventarios);
    $("#filtro-estado").addEventListener("change", renderInventarios);
    $("#filtro-programacion").addEventListener("change", renderProgramaciones);
    $$(".schedule-view-tab").forEach((boton) => {
        boton.addEventListener("click", () => {
            cambiarVistaProgramaciones(boton.dataset.scheduleView);
        });
    });
    $$(".calendar-period").forEach((boton) => {
        boton.addEventListener("click", () => {
            state.periodoCalendario = boton.dataset.calendarPeriod;
            $$(".calendar-period").forEach((item) => {
                item.classList.toggle("active", item === boton);
            });
            renderCalendario();
        });
    });
    $("#calendar-prev").addEventListener("click", () => moverCalendario(-1));
    $("#calendar-next").addEventListener("click", () => moverCalendario(1));
    $("#calendar-today").addEventListener("click", () => {
        state.fechaCalendario = parsearFechaISO(fechaHoyLocal());
        renderCalendario();
    });
    $("#btn-imprimir-cronograma").addEventListener(
        "click",
        imprimirCronograma
    );
    $("#btn-copiar-tabla").addEventListener(
        "click",
        copiarTablaCronograma
    );
    $("#btn-copiar-imagen").addEventListener(
        "click",
        copiarImagenCronograma
    );
    $$(".inventory-tab").forEach((boton) => {
        boton.addEventListener("click", () => {
            state.vistaInventarios = boton.dataset.inventoryTab;
            $$(".inventory-tab").forEach((item) => {
                item.classList.toggle("active", item === boton);
            });
            $("#filtro-estado").value = "Todos";
            renderInventarios();
        });
    });
    $("#inventario-plantilla").addEventListener("change", renderResumenPlantilla);
    $("#inventario-modo").addEventListener("change", cambiarModoInventario);
    $("#inventario-tipo-inventario").addEventListener(
        "change",
        sincronizarTipoInventario
    );
    $("#validar-raiz-ciclica").addEventListener("click", validarRaizCiclica);
    $("#inventario-codigo-raiz").addEventListener(
        "keydown",
        handleCyclicSuggestionKeydown
    );
    $("#inventario-codigo-raiz").addEventListener("input", () => {
        $("#resumen-raiz-ciclica").classList.add("hidden");
        scheduleCyclicSuggestions();
    });
    $("#inventario-codigo-raiz").addEventListener(
        "focus",
        scheduleCyclicSuggestions
    );
    $("#inventario-tipo-articulo-manual").addEventListener(
        "change",
        actualizarOpcionesManual
    );
    $("#inventario-codigo-manual").addEventListener("input", () => {
        programarSugerenciasManual();
    });
    $("#inventario-codigo-manual").addEventListener(
        "focus",
        programarSugerenciasManual
    );
    $("#inventario-codigo-manual").addEventListener(
        "keydown",
        handleManualSuggestionKeydown
    );
    $("#validar-codigo-manual").addEventListener(
        "click",
        validarCodigoManual
    );
    $("#agregar-tipo-articulo").addEventListener(
        "change",
        actualizarOpcionesAgregarArticulo
    );
    $("#agregar-codigo-articulo").addEventListener(
        "input",
        programarSugerenciasAgregarArticulo
    );
    $("#form-agregar-articulo").addEventListener(
        "submit",
        agregarArticuloAInventario
    );
    document.addEventListener("mousedown", (event) => {
        if (!event.target.closest(".autocomplete-control")) {
            hideCyclicSuggestions();
            hideManualSuggestions();
        }
    });
    $("#form-inventario").addEventListener("submit", crearInventario);
    $("#form-programacion").addEventListener("submit", guardarProgramacion);
    $$(".modal-close, .modal-cancel").forEach((boton) => {
        boton.addEventListener("click", cerrarModales);
    });
    $$(".backdrop").forEach((fondo) => {
        fondo.addEventListener("mousedown", (event) => {
            if (event.target === fondo) cerrarModales();
        });
    });
}

async function api(url, options = {}) {
    mostrarLoading(true);
    try {
        const esFormulario = options.body instanceof FormData;
        const response = await fetch(url, {
            ...options,
            headers: esFormulario
                ? { ...(options.headers || {}) }
                : {
                    "Content-Type": "application/json",
                    ...(options.headers || {}),
                },
        });
        const tipo = response.headers.get("content-type") || "";
        const body = tipo.includes("application/json") ? await response.json() : null;
        if (!response.ok) throw new Error(body?.detail || "No se pudo completar la operación");
        return body;
    } finally {
        mostrarLoading(false);
    }
}

function scheduleCyclicSuggestions() {
    window.clearTimeout(cyclicAutocompleteState.timer);
    const termino = $("#inventario-codigo-raiz").value.trim();
    if (termino.length < 2) {
        hideCyclicSuggestions();
        return;
    }
    cyclicAutocompleteState.timer = window.setTimeout(
        () => loadCyclicSuggestions(termino),
        250
    );
}

async function loadCyclicSuggestions(termino) {
    cyclicAutocompleteState.controller?.abort();
    cyclicAutocompleteState.controller = new AbortController();
    try {
        const response = await fetch(
            `/api/busqueda/piezas?q=${encodeURIComponent(termino)}&limite=10`,
            { signal: cyclicAutocompleteState.controller.signal }
        );
        if (!response.ok) throw new Error("No se pudieron buscar códigos");
        const data = await response.json();
        if ($("#inventario-codigo-raiz").value.trim().toUpperCase()
            !== termino.toUpperCase()) {
            return;
        }
        cyclicAutocompleteState.results = data.resultados || [];
        cyclicAutocompleteState.activeIndex =
            cyclicAutocompleteState.results.length ? 0 : -1;
        renderCyclicSuggestions();
    } catch (error) {
        if (error.name !== "AbortError") hideCyclicSuggestions();
    }
}

function renderCyclicSuggestions() {
    const menu = $("#cyclic-root-suggestions");
    const input = $("#inventario-codigo-raiz");
    if (!cyclicAutocompleteState.results.length) {
        menu.innerHTML = `
            <div class="autocomplete-empty">Sin coincidencias</div>
        `;
    } else {
        menu.innerHTML = cyclicAutocompleteState.results.map((item, index) => {
            const auxiliar = [
                item.codigo_cliente ? `Cliente ${item.codigo_cliente}` : "",
                item.codigo_material ? `MP ${item.codigo_material}` : "Sin MP",
            ].filter(Boolean).join(" · ");
            return `
                <button
                    type="button"
                    class="autocomplete-option ${index === cyclicAutocompleteState.activeIndex ? "active" : ""}"
                    data-cyclic-suggestion-index="${index}"
                    role="option"
                    aria-selected="${index === cyclicAutocompleteState.activeIndex}"
                >
                    <strong>${escapeHtml(item.codigo)}</strong>
                    <span>${escapeHtml(item.descripcion || "Sin descripción")}</span>
                    <small>${escapeHtml(auxiliar)}</small>
                </button>
            `;
        }).join("");
        menu.querySelectorAll(".autocomplete-option").forEach((option) => {
            option.addEventListener("mousedown", (event) => {
                event.preventDefault();
                selectCyclicSuggestion(
                    Number(option.dataset.cyclicSuggestionIndex)
                );
            });
        });
    }
    menu.classList.remove("hidden");
    input.setAttribute("aria-expanded", "true");
}

function handleCyclicSuggestionKeydown(event) {
    const menuVisible =
        !$("#cyclic-root-suggestions").classList.contains("hidden");
    if (menuVisible && cyclicAutocompleteState.results.length) {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const direction = event.key === "ArrowDown" ? 1 : -1;
            const length = cyclicAutocompleteState.results.length;
            cyclicAutocompleteState.activeIndex =
                (cyclicAutocompleteState.activeIndex + direction + length)
                % length;
            renderCyclicSuggestions();
            $("#cyclic-root-suggestions .autocomplete-option.active")
                ?.scrollIntoView({ block: "nearest" });
            return;
        }
        if (event.key === "Enter") {
            event.preventDefault();
            selectCyclicSuggestion(cyclicAutocompleteState.activeIndex);
            return;
        }
    }
    if (event.key === "Escape") {
        hideCyclicSuggestions();
        return;
    }
    if (event.key === "Enter") {
        event.preventDefault();
        validarRaizCiclica();
    }
}

function selectCyclicSuggestion(index) {
    const item = cyclicAutocompleteState.results[index];
    if (!item) return;
    $("#inventario-codigo-raiz").value = item.codigo;
    hideCyclicSuggestions();
    $("#inventario-codigo-raiz").focus();
}

function hideCyclicSuggestions() {
    window.clearTimeout(cyclicAutocompleteState.timer);
    cyclicAutocompleteState.controller?.abort();
    cyclicAutocompleteState.results = [];
    cyclicAutocompleteState.activeIndex = -1;
    $("#cyclic-root-suggestions")?.classList.add("hidden");
    $("#inventario-codigo-raiz")?.setAttribute("aria-expanded", "false");
}

async function cargarInicio() {
    try {
        const data = await api("/api/inicio");
        state.plantillas = data.plantillas;
        state.inventarios = data.inventarios;
        state.programaciones = data.programaciones || [];
        state.conciliaciones = data.conciliaciones || [];
        state.causasDiferencia = data.causas_diferencia || [];
        state.tiposInventario = data.tipos_inventario || [];
        state.personas = data.personas || [];
        state.configuracionIndicadores = {
            ...state.configuracionIndicadores,
            ...(data.configuracion_indicadores || {}),
        };
        actualizarEtiquetasIndicadores();
        renderTodo();
    } catch (error) {
        toast(error.message, true);
    }
}

function renderTodo() {
    renderMetricas();
    renderInventarios();
    renderProgramaciones();
    renderCalendario();
    renderPlantillas();
    renderConciliaciones();
    cargarSelectPlantillas();
    cargarSelectPersonas();
    cargarSelectTiposInventario();
}

function cargarSelectPersonas() {
    const opciones = state.personas.map((persona) => `
        <option value="${persona.id}">
            ${escapeHtml(persona.nombre)}
            ${persona.sector ? ` · ${escapeHtml(persona.sector)}` : ""}
        </option>
    `).join("");
    [
        "#inventario-responsable",
        "#inventario-colaboradores",
        "#programacion-responsable",
        "#programacion-colaboradores",
    ].forEach((selector) => {
        const actual = valoresSeleccionados($(selector));
        $(selector).innerHTML = opciones;
        seleccionarValores($(selector), actual);
    });
}

function cargarSelectTiposInventario() {
    $("#inventario-tipo-inventario").innerHTML = state.tiposInventario.map(
        (tipo) => `
            <option value="${escapeHtml(tipo.codigo)}">
                ${escapeHtml(tipo.nombre)}
            </option>
        `
    ).join("");
    actualizarDisponibilidadModalidadMedios();
}

function valoresSeleccionados(selector) {
    if (!selector) return [];
    return [...selector.selectedOptions].map((option) => option.value);
}

function seleccionarValores(selector, valores) {
    const buscados = new Set(
        Array.isArray(valores) ? valores : [valores]
    );
    [...selector.options].forEach((option) => {
        option.selected = buscados.has(option.value);
    });
}

function colaboradoresTexto(selector) {
    return valoresSeleccionados(selector)
        .map((id) => state.personas.find(
            (persona) => String(persona.id) === String(id)
        )?.nombre)
        .filter(Boolean)
        .join(", ");
}

function responsableTexto(selector) {
    const persona = state.personas.find(
        (item) => String(item.id) === String(selector.value)
    );
    return persona?.nombre || "";
}

function idsPersonasPorNombres(texto) {
    const nombres = new Set(
        String(texto || "")
            .split(",")
            .map((nombre) => nombre.trim().toLowerCase())
            .filter(Boolean)
    );
    return state.personas
        .filter((persona) => nombres.has(persona.nombre.toLowerCase()))
        .map((persona) => String(persona.id));
}

function renderMetricas() {
    $("#metric-preparacion").textContent = state.inventarios.filter((x) => x.estado === "En preparación").length;
    $("#metric-conteo").textContent = state.inventarios.filter((x) => x.estado === "En conteo").length;
    $("#metric-cerrados").textContent = state.inventarios.filter((x) => x.estado === "Cerrado").length;
    $("#metric-diferencias").textContent = state.inventarios
        .flatMap((x) => x.items)
        .filter((x) => x.diferencia !== null && x.diferencia !== 0).length;
}

function renderInventarios() {
    const texto = $("#buscar-inventario").value.trim().toLowerCase();
    const estado = $("#filtro-estado").value;
    const filtrados = state.inventarios.filter((item) => {
        const coincideTexto = [
            item.codigo,
            item.cliente,
            item.responsable,
            item.colaboradores,
            item.observaciones,
            ambitoInventarioLabel(item.ambito),
        ].join(" ").toLowerCase().includes(texto);
        const coincideEstado = estado === "Todos" || item.estado === estado;
        const coincideVista =
            state.vistaInventarios === "TODOS"
            || (state.vistaInventarios === "REALIZADOS" && item.estado === "Cerrado")
            || (state.vistaInventarios === "EN_CURSO" && item.estado !== "Cerrado");
        return coincideTexto && coincideEstado && coincideVista;
    });

    $("#inventarios-total").textContent = `${filtrados.length} inventarios en esta vista`;
    $("#inventarios-vacio").classList.toggle("hidden", filtrados.length !== 0);
    $("#tabla-inventarios").innerHTML = filtrados.map((item) => `
        <tr data-id="${item.id}">
            <td><button class="link">${escapeHtml(item.codigo)}</button></td>
            <td>
                <strong>${escapeHtml(item.cliente)}</strong>
                <small class="inventory-scope ${item.ambito === "CLIENTE" ? "client" : ""}">
                    ${escapeHtml(ambitoInventarioLabel(item.ambito))}
                </small>
            </td>
            <td>
                <strong>${formatearFecha(item.fecha)}</strong>
                ${item.fecha_programada ? `
                    <small class="secondary-code">
                        Programado: ${formatearFecha(item.fecha_programada)}
                    </small>
                ` : ""}
                <small class="secondary-code">
                    Cierre: ${formatearMesCierre(item.mes_cierre || item.fecha)}
                </small>
            </td>
            <td>
                <div class="progress">
                    <span>${item.progreso}%</span>
                    <i><b style="width:${item.progreso}%"></b></i>
                </div>
            </td>
            <td>${confiabilidadHtml(item)}</td>
            <td>${statusHtml(item.estado)}</td>
            <td>
                ${escapeHtml(item.responsable)}
                ${item.colaboradores ? `
                    <small class="secondary-code">
                        Con ${escapeHtml(item.colaboradores)}
                    </small>
                ` : ""}
            </td>
            <td><button class="more" aria-label="Abrir">⋮</button></td>
        </tr>
    `).join("");

    $$("#tabla-inventarios tr").forEach((fila) => {
        fila.addEventListener("click", () => abrirDetalle(Number(fila.dataset.id)));
    });
}

function renderProgramaciones() {
    const filtro = $("#filtro-programacion").value;
    const filtradas = state.programaciones.filter((item) => {
        if (filtro === "PENDIENTES") {
            return ["Vencida", "Para hoy"].includes(item.estado);
        }
        if (filtro === "ACTIVAS") return item.activa;
        return true;
    });

    $("#programados-vencidos").textContent =
        state.programaciones.filter((x) => x.estado === "Vencida").length;
    $("#programados-hoy").textContent =
        state.programaciones.filter((x) => x.estado === "Para hoy").length;
    $("#programados-proximos").textContent =
        state.programaciones.filter((x) => x.estado === "Próxima").length;
    $("#programados-activos").textContent =
        state.programaciones.filter((x) => x.activa).length;
    $("#programaciones-total").textContent =
        `${state.programaciones.length} programaciones registradas`;
    $("#programaciones-vacio").classList.toggle(
        "hidden",
        filtradas.length !== 0
    );

    $("#tabla-programaciones").innerHTML = filtradas.map((item) => {
        const ultimoInventario = obtenerUltimoInventarioProgramacion(item.id);
        return `
        <tr>
            <td>
                <strong>${escapeHtml(item.plantilla_nombre)}</strong>
                <small class="secondary-code">${tipoInventarioLabel(item.tipo_inventario_codigo, item.categoria)}</small>
            </td>
            <td>${escapeHtml(item.cliente)}</td>
            <td>
                <strong>${formatearFecha(item.fecha_proxima)}</strong>
                <small class="secondary-code">
                    Cierre: ${formatearMesCierre(item.mes_cierre_proximo)}
                </small>
                ${item.ultima_ejecucion ? `
                    <small class="secondary-code">
                        Última: ${formatearFecha(item.ultima_ejecucion)}
                    </small>
                ` : ""}
            </td>
            <td>${frecuenciaLabel(item.frecuencia)}</td>
            <td>
                ${escapeHtml(item.responsable)}
                ${item.colaboradores ? `
                    <small class="secondary-code">
                        Con ${escapeHtml(item.colaboradores)}
                    </small>
                ` : ""}
            </td>
            <td>${estadoProgramacionHtml(item.estado)}</td>
            <td>
                ${ultimoInventario ? `
                    <button
                        type="button"
                        class="schedule-last-inventory"
                        data-inventory-id="${ultimoInventario.id}"
                    >
                        <strong>${escapeHtml(ultimoInventario.codigo)}</strong>
                        <small>${escapeHtml(ultimoInventario.estado)}</small>
                    </button>
                ` : `
                    <span class="schedule-never-run">Todavía no generado</span>
                `}
                <small class="secondary-code">${item.ejecuciones} generado${item.ejecuciones === 1 ? "" : "s"}</small>
            </td>
            <td>
                <button
                    type="button"
                    class="schedule-generate"
                    data-id="${item.id}"
                    ${item.activa ? "" : "disabled"}
                >Generar inventario</button>
            </td>
            <td>
                <div class="schedule-actions">
                    <button type="button" class="schedule-edit" data-id="${item.id}">Editar</button>
                    <button
                        type="button"
                        class="schedule-toggle"
                        data-id="${item.id}"
                        ${item.estado === "Completada" ? "disabled" : ""}
                    >${item.activa ? "Pausar" : "Reanudar"}</button>
                    <button type="button" class="schedule-delete" data-id="${item.id}">Eliminar</button>
                </div>
            </td>
        </tr>
    `;
    }).join("");

    $$(".schedule-generate").forEach((boton) => {
        boton.addEventListener("click", () => {
            generarInventarioProgramado(Number(boton.dataset.id));
        });
    });
    $$(".schedule-last-inventory").forEach((boton) => {
        boton.addEventListener("click", () => {
            abrirDetalle(Number(boton.dataset.inventoryId));
        });
    });
    $$(".schedule-edit").forEach((boton) => {
        boton.addEventListener("click", () => {
            abrirModalProgramacion(Number(boton.dataset.id));
        });
    });
    $$(".schedule-toggle").forEach((boton) => {
        boton.addEventListener("click", () => {
            alternarProgramacion(Number(boton.dataset.id));
        });
    });
    $$(".schedule-delete").forEach((boton) => {
        boton.addEventListener("click", () => {
            eliminarProgramacion(Number(boton.dataset.id));
        });
    });
}

function cambiarVistaProgramaciones(vista) {
    state.vistaProgramaciones = vista;
    $$(".schedule-view-tab").forEach((boton) => {
        boton.classList.toggle(
            "active",
            boton.dataset.scheduleView === vista
        );
    });
    $("#programaciones-lista").classList.toggle("hidden", vista !== "LISTA");
    $("#programaciones-calendario").classList.toggle(
        "hidden",
        vista !== "CALENDARIO"
    );
    if (vista === "CALENDARIO") renderCalendario();
}

function moverCalendario(direccion) {
    const fecha = state.fechaCalendario;
    state.fechaCalendario = state.periodoCalendario === "MES"
        ? new Date(fecha.getFullYear(), fecha.getMonth() + direccion, 1)
        : sumarDias(fecha, direccion * 7);
    renderCalendario();
}

function renderCalendario() {
    const { inicio, fin, dias, titulo } = rangoCalendario();
    const eventos = obtenerEventosCalendario(inicio, fin);
    const eventosPorFecha = new Map();
    eventos.forEach((evento) => {
        if (!eventosPorFecha.has(evento.fecha)) {
            eventosPorFecha.set(evento.fecha, []);
        }
        eventosPorFecha.get(evento.fecha).push(evento);
    });

    $("#calendar-title").textContent = titulo;
    $("#calendar-print-title").textContent = `Inventarios · ${titulo}`;
    $("#calendar-print-date").textContent =
        `Emitido el ${formatearFecha(fechaHoyLocal())}`;
    $("#calendar-empty").classList.toggle("hidden", eventos.length !== 0);
    $("#calendar-grid").classList.toggle(
        "week-view",
        state.periodoCalendario === "SEMANA"
    );
    $("#calendar-grid").innerHTML = dias.map((fecha) => {
        const iso = fechaISO(fecha);
        const fueraMes = state.periodoCalendario === "MES"
            && fecha.getMonth() !== state.fechaCalendario.getMonth();
        const eventosDia = eventosPorFecha.get(iso) || [];
        return `
            <article class="calendar-day ${fueraMes ? "outside-month" : ""} ${iso === fechaHoyLocal() ? "today" : ""}">
                <header>
                    <span>${state.periodoCalendario === "SEMANA"
                        ? nombreDiaCorto(fecha)
                        : ""}</span>
                    <strong>${fecha.getDate()}</strong>
                </header>
                <div class="calendar-events">
                    ${eventosDia.map(eventoCalendarioHtml).join("")}
                </div>
            </article>
        `;
    }).join("");

    $$(".calendar-event").forEach((boton) => {
        boton.addEventListener("click", () => {
            const inventarioId = Number(boton.dataset.inventoryId) || null;
            const programacionId = Number(boton.dataset.scheduleId) || null;
            if (inventarioId) {
                abrirDetalle(inventarioId);
            } else if (programacionId) {
                abrirModalProgramacion(programacionId);
            }
        });
    });

    renderCalendario.datos = { inicio, fin, titulo, eventos };
}

function eventoCalendarioHtml(evento) {
    const clase = {
        PROGRAMADO: "planned",
        VENCIDO: "overdue",
        EN_CURSO: "progress",
        REALIZADO: "done",
        PAUSADO: "paused",
    }[evento.estado] || "planned";
    const referencia = evento.codigo
        ? `${evento.codigo} · ${evento.estado_label}`
        : evento.estado_label;
    const colaboradores = (evento.colaboradores || "").trim();
    return `
        <button
            type="button"
            class="calendar-event ${clase}"
            data-schedule-id="${evento.programacion_id || ""}"
            data-inventory-id="${evento.inventario_id || ""}"
            title="${escapeHtml(evento.cliente)} · Responsable: ${escapeHtml(
                evento.responsable
            )}${colaboradores
                ? ` · Colaboradores: ${escapeHtml(colaboradores)}`
                : ""}"
        >
            <strong>${escapeHtml(evento.plantilla_nombre)}</strong>
            <span>${escapeHtml(evento.cliente)}</span>
            <small class="calendar-event-category">
                ${escapeHtml(tipoInventarioLabel(evento.tipo_inventario_codigo, evento.categoria))}
            </small>
            <small class="calendar-event-people">
                <b>Resp.</b> ${escapeHtml(evento.responsable)}
            </small>
            ${colaboradores ? `
                <small class="calendar-event-people calendar-collaborators">
                    <b>Colab.</b> ${escapeHtml(colaboradores)}
                </small>
            ` : ""}
            <em>${escapeHtml(referencia)}</em>
        </button>
    `;
}

function obtenerEventosCalendario(inicio, fin) {
    const inicioIso = fechaISO(inicio);
    const finIso = fechaISO(fin);
    const programacionesPorId = new Map(
        state.programaciones.map((item) => [item.id, item])
    );
    const eventos = [];
    const ocupados = new Set();

    state.inventarios
        .filter((item) => (
            item.fecha_programada
            && item.fecha_programada >= inicioIso
            && item.fecha_programada <= finIso
        ))
        .forEach((inventario) => {
            const programacion = programacionesPorId.get(
                inventario.programacion_id
            );
            if (inventario.programacion_id) {
                ocupados.add(
                    `${inventario.programacion_id}|${inventario.fecha_programada}`
                );
            }
            eventos.push({
                fecha: inventario.fecha_programada,
                programacion_id: inventario.programacion_id,
                inventario_id: inventario.id,
                plantilla_nombre: programacion?.plantilla_nombre
                    || `Inventario ${inventario.codigo}`,
                cliente: inventario.cliente,
                categoria: inventario.categoria,
                tipo_inventario_codigo: inventario.tipo_inventario_codigo,
                responsable: inventario.responsable,
                colaboradores: inventario.colaboradores || "",
                codigo: inventario.codigo,
                estado: inventario.estado === "Cerrado"
                    ? "REALIZADO"
                    : "EN_CURSO",
                estado_label: inventario.estado === "Cerrado"
                    ? `Realizado ${formatearFecha(inventario.fecha)}`
                    : `En curso desde ${formatearFecha(inventario.fecha)}`,
            });
        });

    state.programaciones.forEach((programacion) => {
        const agregar = (fecha, estado) => {
            const iso = fechaISO(fecha);
            const clave = `${programacion.id}|${iso}`;
            if (
                iso < inicioIso
                || iso > finIso
                || ocupados.has(clave)
            ) return;
            eventos.push({
                fecha: iso,
                programacion_id: programacion.id,
                inventario_id: null,
                plantilla_nombre: programacion.plantilla_nombre,
                cliente: programacion.cliente,
                categoria: programacion.categoria,
                tipo_inventario_codigo: programacion.tipo_inventario_codigo,
                responsable: programacion.responsable,
                colaboradores: programacion.colaboradores || "",
                codigo: "",
                estado,
                estado_label: {
                    PROGRAMADO: "Programado",
                    VENCIDO: "Fecha vencida",
                    PAUSADO: "Programación pausada",
                }[estado],
            });
        };

        let fecha = parsearFechaISO(programacion.fecha_proxima);
        if (!programacion.activa) {
            if (programacion.estado === "Pausada") agregar(fecha, "PAUSADO");
            return;
        }

        if (programacion.frecuencia === "UNA_VEZ") {
            agregar(fecha, estadoFechaProgramada(fecha));
            return;
        }

        while (fecha < inicio) {
            fecha = siguienteOcurrencia(fecha, programacion);
        }
        while (fecha <= fin) {
            agregar(fecha, estadoFechaProgramada(fecha));
            fecha = siguienteOcurrencia(fecha, programacion);
        }
    });

    return eventos.sort((a, b) => (
        a.fecha.localeCompare(b.fecha)
        || a.cliente.localeCompare(b.cliente)
        || a.plantilla_nombre.localeCompare(b.plantilla_nombre)
    ));
}

function estadoFechaProgramada(fecha) {
    return fechaISO(fecha) < fechaHoyLocal() ? "VENCIDO" : "PROGRAMADO";
}

function siguienteOcurrencia(fecha, programacion) {
    if (programacion.frecuencia === "SEMANAL") return sumarDias(fecha, 7);
    return sumarMesConDia(fecha, Number(programacion.dia_mes) || fecha.getDate());
}

function rangoCalendario() {
    if (state.periodoCalendario === "SEMANA") {
        const inicio = inicioSemana(state.fechaCalendario);
        const fin = sumarDias(inicio, 6);
        return {
            inicio,
            fin,
            dias: rangoDias(inicio, 7),
            titulo: tituloSemana(inicio, fin),
        };
    }

    const referencia = state.fechaCalendario;
    const primerDia = new Date(
        referencia.getFullYear(),
        referencia.getMonth(),
        1
    );
    const inicio = sumarDias(
        primerDia,
        -((primerDia.getDay() + 6) % 7)
    );
    const fin = sumarDias(inicio, 41);
    return {
        inicio,
        fin,
        dias: rangoDias(inicio, 42),
        titulo: new Intl.DateTimeFormat("es-AR", {
            month: "long",
            year: "numeric",
        }).format(primerDia),
    };
}

function datosCronogramaActual() {
    renderCalendario();
    const { titulo, eventos } = renderCalendario.datos;
    if (!eventos.length) {
        toast("No hay inventarios en el período seleccionado", true);
        return null;
    }
    return { titulo, eventos };
}

function textoCronograma(titulo, eventos) {
    const lineas = eventos.map((evento) => (
        `• ${nombreDiaCorto(parsearFechaISO(evento.fecha))} `
        + `${formatearFecha(evento.fecha)} · ${evento.cliente} · `
        + `${evento.plantilla_nombre} · ${evento.responsable} · `
        + `${evento.colaboradores || "Sin colaboradores"} · `
        + `${evento.estado_label}`
    ));
    return [
        `CRONOGRAMA DE INVENTARIOS — ${titulo.toUpperCase()}`,
        "",
        ...lineas,
    ].join("\n");
}

function tablaCronogramaHtml(titulo, eventos) {
    const filas = eventos.map((evento) => `
        <tr>
            <td>${escapeHtml(nombreDiaCorto(parsearFechaISO(evento.fecha)))}</td>
            <td>${escapeHtml(formatearFecha(evento.fecha))}</td>
            <td>${escapeHtml(evento.cliente)}</td>
            <td>${escapeHtml(evento.plantilla_nombre)}</td>
            <td>${escapeHtml(tipoInventarioLabel(evento.tipo_inventario_codigo, evento.categoria))}</td>
            <td>${escapeHtml(evento.responsable)}</td>
            <td>${escapeHtml(evento.colaboradores || "—")}</td>
            <td>${escapeHtml(evento.estado_label)}</td>
        </tr>
    `).join("");
    return `
        <div>
            <h2 style="font-family:Arial,sans-serif;color:#244f7e">
                CRONOGRAMA DE INVENTARIOS — ${escapeHtml(titulo.toUpperCase())}
            </h2>
            <table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px">
                <thead>
                    <tr style="background:#244f7e;color:#fff">
                        <th style="border:1px solid #1f3650;padding:8px">Día</th>
                        <th style="border:1px solid #1f3650;padding:8px">Fecha</th>
                        <th style="border:1px solid #1f3650;padding:8px">Cliente</th>
                        <th style="border:1px solid #1f3650;padding:8px">Inventario</th>
                        <th style="border:1px solid #1f3650;padding:8px">Tipo</th>
                        <th style="border:1px solid #1f3650;padding:8px">Responsable</th>
                        <th style="border:1px solid #1f3650;padding:8px">Colaboradores</th>
                        <th style="border:1px solid #1f3650;padding:8px">Estado</th>
                    </tr>
                </thead>
                <tbody>${filas}</tbody>
            </table>
        </div>
    `.replaceAll("<td>", '<td style="border:1px solid #b9c5d2;padding:7px">');
}

async function copiarTablaCronograma() {
    const datos = datosCronogramaActual();
    if (!datos) return;
    const texto = textoCronograma(datos.titulo, datos.eventos);
    const html = tablaCronogramaHtml(datos.titulo, datos.eventos);
    try {
        await copiarHtml(html, texto);
        toast("Tabla copiada para pegar en mail, Word o Teams");
    } catch {
        toast("No se pudo copiar la tabla", true);
    }
}

async function copiarImagenCronograma() {
    const datos = datosCronogramaActual();
    if (!datos) return;
    mostrarLoading(true);
    try {
        const imagen = await crearImagenCronograma();
        if (navigator.clipboard?.write && window.ClipboardItem) {
            try {
                await navigator.clipboard.write([
                    new ClipboardItem({ "image/png": imagen }),
                ]);
                toast("Imagen copiada para compartir");
                return;
            } catch {
                // Firefox y algunas políticas empresariales bloquean PNG.
            }
        }
        descargarBlob(
            imagen,
            `cronograma-inventarios-${fechaHoyLocal()}.png`
        );
        toast("El navegador no permite copiar PNG: la imagen fue descargada");
    } catch {
        toast("No se pudo generar la imagen", true);
    } finally {
        mostrarLoading(false);
    }
}

function imprimirCronograma() {
    cambiarVistaProgramaciones("CALENDARIO");
    document.body.classList.add("calendar-printing");
    const limpiar = () => {
        document.body.classList.remove("calendar-printing");
    };
    window.addEventListener("afterprint", limpiar, { once: true });
    window.print();
    setTimeout(limpiar, 1000);
}

function renderPlantillas() {
    const texto = $("#buscar-plantilla").value.trim().toLowerCase();
    const plantillas = state.plantillas.filter((plantilla) => [
        plantilla.nombre,
        plantilla.cliente,
        plantilla.descripcion,
        categoriaPlantillaLabel(plantilla.categoria),
        ...plantilla.items.flatMap((item) => [
            item.codigo,
            item.codigo_cliente,
            item.codigo_material,
            item.descripcion,
        ]),
    ].join(" ").toLowerCase().includes(texto));

    $("#plantillas-resumen").textContent = texto
        ? `${plantillas.length} de ${state.plantillas.length} plantillas coinciden con la búsqueda.`
        : `${state.plantillas.length} plantillas configuradas para inventarios habituales.`;

    $("#plantillas-grid").innerHTML = plantillas.length
        ? plantillas.map((plantilla) => `
            <article class="template-row ${plantilla.activa ? "" : "inactive"}">
                <div class="template-row-summary">
                    <span class="template-row-icon">▤</span>

                    <div class="template-row-identity">
                        <div>
                            <h2>${escapeHtml(plantilla.nombre)}</h2>
                            <span class="template-active ${plantilla.activa ? "" : "inactive"}">
                                <i></i>${plantilla.activa ? "Activa" : "Inactiva"}
                            </span>
                        </div>
                        <p>${escapeHtml(plantilla.descripcion || "Sin descripción")}</p>
                        <small class="template-updated">
                            Actualizada ${formatearFechaHora(plantilla.actualizada_en)}
                        </small>
                    </div>

                    <div class="template-row-details">
                        <div>
                            <small>Cliente</small>
                            <strong>${escapeHtml(plantilla.cliente)}</strong>
                        </div>
                        <div>
                            <small>Artículos</small>
                            <strong>${plantilla.items.length}</strong>
                        </div>
                        <div class="template-row-tags">
                            <span>
                                ${plantilla.tipo_conteo === "POR_OPERACION"
                                    ? "Por operación"
                                    : "Proceso global"}
                            </span>
                            <span>${tipoInventarioLabel(plantilla.tipo_inventario_codigo, plantilla.categoria)}</span>
                            ${plantilla.controla_remitos
                                ? "<span>Controla remitos</span>"
                                : ""}
                        </div>
                    </div>

                    <div class="template-row-actions">
                        <button
                            class="template-use usar-plantilla"
                            data-id="${plantilla.id}"
                            ${plantilla.activa ? "" : "disabled"}
                        >
                            Usar
                        </button>
                        <button class="editar-plantilla" data-id="${plantilla.id}">
                            Editar
                        </button>
                        <button
                            class="programar-plantilla"
                            data-id="${plantilla.id}"
                            ${plantilla.activa ? "" : "disabled"}
                        >
                            Programar
                        </button>
                        <button
                            class="template-expand ver-codigos"
                            data-id="${plantilla.id}"
                            aria-expanded="false"
                            aria-controls="template-preview-${plantilla.id}"
                        >
                            Ver códigos
                        </button>
                        <button
                            class="template-delete eliminar-plantilla"
                            data-id="${plantilla.id}"
                            title="Eliminar plantilla"
                            aria-label="Eliminar ${escapeHtml(plantilla.nombre)}"
                        >
                            ×
                        </button>
                    </div>
                </div>

                <div
                    id="template-preview-${plantilla.id}"
                    class="template-row-preview hidden"
                >
                    ${plantilla.items.map((item, indice) => `
                        <div class="template-code-item">
                            <span>${indice + 1}</span>
                            <p>
                                <strong>${escapeHtml(item.codigo)}</strong>
                                <small>${escapeHtml(item.descripcion)}</small>
                            </p>
                            <em>
                                ${escapeHtml(item.codigo_material || "Sin material")}
                                ${item.codigo_material && item.contar_material === false
                                    ? " · MP no incluida"
                                    : ""}
                            </em>
                        </div>
                    `).join("")}
                </div>
            </article>
        `).join("")
        : `
            <div class="template-list-empty">
                <strong>No hay plantillas que coincidan</strong>
                <span>Probá buscar por otro nombre, cliente o código.</span>
            </div>
        `;

    $$(".ver-codigos").forEach((boton) => {
        boton.addEventListener("click", () => {
            const vista = $(`#template-preview-${boton.dataset.id}`);
            const abierta = !vista.classList.toggle("hidden");
            boton.setAttribute("aria-expanded", String(abierta));
            boton.textContent = abierta ? "Ocultar códigos" : "Ver códigos";
        });
    });

    $$(".usar-plantilla").forEach((boton) => {
        boton.addEventListener("click", () => {
            abrirModalInventario(Number(boton.dataset.id));
        });
    });
    $$(".editar-plantilla").forEach((boton) => {
        boton.addEventListener("click", () => {
            window.location.href = `/plantillas/${boton.dataset.id}/editar`;
        });
    });
    $$(".programar-plantilla").forEach((boton) => {
        boton.addEventListener("click", () => {
            abrirModalProgramacion(null, Number(boton.dataset.id));
        });
    });
    $$(".eliminar-plantilla").forEach((boton) => {
        boton.addEventListener("click", () => {
            eliminarPlantilla(Number(boton.dataset.id));
        });
    });
}

function renderConciliaciones() {
    const ultima = state.conciliaciones[0] || null;
    $("#metric-conciliaciones").textContent = state.conciliaciones.length;
    $("#metric-conciliacion-confianza").textContent = ultima
        ? formatearPorcentaje(ultima.confiabilidad)
        : "—";
    $("#metric-conciliacion-diferencia").textContent = ultima
        ? numeroConSigno(ultima.diferencia_total)
        : "—";
    $("#conciliaciones-vacio").classList.toggle(
        "hidden",
        state.conciliaciones.length > 0
    );
    $("#tabla-conciliaciones").innerHTML = state.conciliaciones.map((item) => `
        <tr data-id="${item.id}">
            <td>
                <strong>${escapeHtml(item.codigo)}</strong>
                <small class="secondary-code">${escapeHtml(item.nombre)}</small>
            </td>
            <td>${escapeHtml(item.inventario_inicial_codigo)}</td>
            <td>${escapeHtml(item.inventario_final_codigo)}</td>
            <td>${formatearFecha(item.fecha_inicial)} → ${formatearFecha(item.fecha_final)}</td>
            <td>${formatearPorcentaje(item.confiabilidad)}</td>
            <td class="${item.diferencia_total ? "warning" : ""}">
                ${numeroConSigno(item.diferencia_total)}
            </td>
            <td><button class="link">Abrir</button></td>
        </tr>
    `).join("");
    $$("#tabla-conciliaciones tr").forEach((fila) => {
        fila.addEventListener("click", () => {
            abrirConciliacion(Number(fila.dataset.id));
        });
    });
    if (state.conciliacionSeleccionada) {
        const actualizada = state.conciliaciones.find(
            (item) => item.id === state.conciliacionSeleccionada.id
        );
        state.conciliacionSeleccionada = actualizada || null;
        renderDetalleConciliacion();
    }
}

function abrirConciliacion(id) {
    state.conciliacionSeleccionada = state.conciliaciones.find(
        (item) => item.id === id
    );
    renderDetalleConciliacion();
    $("#conciliacion-detalle").scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}

function renderDetalleConciliacion() {
    const item = state.conciliacionSeleccionada;
    $("#conciliacion-detalle").classList.toggle("hidden", !item);
    if (!item) return;
    $("#conciliacion-titulo").textContent =
        `${item.codigo} · ${item.nombre}`;
    $("#conciliacion-subtitulo").textContent =
        `${item.inventario_inicial_codigo} → ${item.inventario_final_codigo}`
        + ` · ${item.items_ok}/${item.items_total} códigos dentro de ±`
        + `${formatearNumero(state.configuracionIndicadores.tolerancia_pct)}%`;
    const describirCriterio = (criterio) => ({
        REMITOS: "Cronológico: fechas ubicadas mediante ambos remitos",
        FECHAS: `Aproximado por fechas (${formatearFecha(item.fecha_inicial)} excluida → ${formatearFecha(item.fecha_final)} incluida)`,
        MIXTO_INICIAL_REMITO: `Mixto: inicio en la fecha del remito y final por fecha ${formatearFecha(item.fecha_final)} incluida`,
        MIXTO_FINAL_REMITO: `Mixto: inicio por fecha ${formatearFecha(item.fecha_inicial)} excluida y final en la fecha del remito`,
    })[criterio] || "Sin calcular";
    const criterioIngreso = describirCriterio(item.criterio_ingreso);
    const criterioEgreso = describirCriterio(item.criterio_egreso);
    $("#conciliacion-remitos").innerHTML = `
        <div>
            <span>Corte remitos de ingreso</span>
            <strong>
                ${escapeHtml(item.remito_ingreso_inicial || "Sin informar")}
                → ${escapeHtml(item.remito_ingreso_final || "Sin informar")}
            </strong>
            <small>${escapeHtml(criterioIngreso)}</small>
        </div>
        <div>
            <span>Corte remitos de egreso</span>
            <strong>
                ${escapeHtml(item.remito_egreso_inicial || "Sin informar")}
                → ${escapeHtml(item.remito_egreso_final || "Sin informar")}
            </strong>
            <small>${escapeHtml(criterioEgreso)}</small>
        </div>
        <div>
            <span>Movimientos calculados</span>
            <strong>${item.movimientos_calculados_en
                ? escapeHtml(formatearFechaHora(item.movimientos_calculados_en))
                : "Sin calcular"}</strong>
        </div>
    `;
    const advertencias = item.advertencias_movimientos || [];
    $("#conciliacion-advertencias").classList.toggle(
        "hidden",
        advertencias.length === 0
    );
    $("#conciliacion-advertencias").innerHTML = advertencias.map(
        (mensaje) => `<p>⚠ ${escapeHtml(mensaje)}</p>`
    ).join("");
    renderAuditoriaRemitos(item);
    $("#tabla-conciliacion-detalle").innerHTML = item.items.map((linea) => `
        <tr data-conciliation-item="${linea.id}">
            <td><strong>${escapeHtml(linea.codigo)}</strong></td>
            <td>${escapeHtml(linea.descripcion)}</td>
            <td>
                <strong>${formatearNumero(linea.stock_inicial)}</strong>
                <small class="reconciliation-trace">
                    ${escapeHtml(linea.detalle_inicial || "Sin origen")}
                </small>
            </td>
            <td>
                <input class="movement-input movement-in" type="number" min="0" step="any"
                    value="${linea.ingresos}" data-item-id="${linea.id}">
                <small class="movement-calculated">
                    Calculado: ${formatearNumero(linea.ingresos_calculados)}
                </small>
                ${detalleIngresosHtml(linea.detalle_ingresos)}
            </td>
            <td>
                <input class="movement-input movement-out" type="number" min="0" step="any"
                    value="${linea.egresos}" data-item-id="${linea.id}">
                <small class="movement-calculated">
                    Calculado: ${formatearNumero(linea.egresos_calculados)}
                </small>
                ${detalleEgresosHtml(linea.detalle_egresos)}
            </td>
            <td>
                <input class="movement-input movement-scrap" type="number" min="0" step="any"
                    value="${linea.scrap || 0}" data-item-id="${linea.id}">
            </td>
            <td data-expected="${linea.id}">${formatearNumero(linea.stock_esperado)}</td>
            <td>
                <strong>${formatearNumero(linea.stock_final)}</strong>
                <small class="reconciliation-trace">
                    ${escapeHtml(linea.detalle_final || "Sin origen")}
                </small>
            </td>
            <td data-reconciliation-difference="${linea.id}"
                class="${linea.diferencia ? "warning" : ""}">
                ${numeroConSigno(linea.diferencia)}
            </td>
            <td data-reconciliation-percentage="${linea.id}">
                ${porcentajeConteoHtml(linea)}
            </td>
            <td>
                <button type="button" class="danger compact delete-conciliation-row"
                    data-item-id="${linea.id}" data-item-code="${escapeHtml(linea.codigo)}">
                    Eliminar fila
                </button>
            </td>
        </tr>
    `).join("");
    $$(".movement-input").forEach((input) => {
        input.addEventListener("input", (event) => {
            recalcularConciliacionVisual(event);
            programarAutoguardado("conciliacion");
        });
    });
    $$(".delete-conciliation-row").forEach((boton) => {
        boton.addEventListener("click", () => eliminarFilaConciliacion(
            Number(boton.dataset.itemId), boton.dataset.itemCode
        ));
    });
}

async function eliminarFilaConciliacion(itemId, codigo) {
    const conciliacion = state.conciliacionSeleccionada;
    if (!conciliacion) return;
    const confirmar = window.confirm(
        `¿Eliminar ${codigo} de esta conciliación? No volverá a aparecer al recalcular.`
    );
    if (!confirmar) return;
    window.clearTimeout(autosave.conciliacion.timer);
    autosave.conciliacion.timer = null;
    autosave.conciliacion.dirty = false;
    autosave.conciliacion.failed = false;
    try {
        const actualizada = await api(
            `/api/conciliaciones/${conciliacion.id}/items/${itemId}`,
            { method: "DELETE" }
        );
        state.conciliaciones = state.conciliaciones.map((item) =>
            item.id === actualizada.id ? actualizada : item
        );
        state.conciliacionSeleccionada = actualizada;
        renderConciliaciones();
        toast(`${codigo} fue excluido de la conciliación`);
    } catch (error) {
        toast(error.message, true);
    }
}

function fechaMovimiento(fecha) {
    return fecha ? formatearFecha(String(fecha).slice(0, 10)) : "—";
}

function detalleIngresosHtml(filas) {
    if (!filas?.length) return "";
    return `
        <details class="movement-breakdown">
            <summary>${filas.length} línea${filas.length === 1 ? "" : "s"}</summary>
            ${filas.map((fila) => `
                <div>
                    <strong>${escapeHtml(fila.remito)}</strong>
                    <span>${fechaMovimiento(fila.fecha)} · ${formatearNumero(fila.cantidad)}</span>
                </div>
            `).join("")}
        </details>
    `;
}

function detalleEgresosHtml(filas) {
    if (!filas?.length) return "";
    return `
        <details class="movement-breakdown">
            <summary>${filas.length} origen${filas.length === 1 ? "" : "es"}</summary>
            ${filas.map((fila) => `
                <div>
                    <strong>${escapeHtml(fila.remito)} · ${escapeHtml(fila.pieza_origen)}</strong>
                    <span>
                        ${formatearNumero(fila.cantidad_pieza)} × ${formatearNumero(fila.uso)}
                        = ${formatearNumero(fila.cantidad_equivalente)}
                        ${fila.despacho_directo ? " · directo" : ""}
                    </span>
                </div>
            `).join("")}
        </details>
    `;
}

function agruparPorRemito(filas) {
    const grupos = new Map();
    filas.forEach((fila) => {
        const clave = fila.remito || "SIN REMITO";
        if (!grupos.has(clave)) grupos.set(clave, []);
        grupos.get(clave).push(fila);
    });
    return [...grupos.entries()];
}

function resumenGrupoRemito(remito, filas) {
    const fechas = [...new Set(filas.map((fila) => fechaMovimiento(fila.fecha)))];
    const verificados = filas.filter((fila) => fila.verificado).length;
    return `
        <strong>${escapeHtml(remito)}</strong>
        <span>${fechas.join(" · ")} · ${filas.length} línea${filas.length === 1 ? "" : "s"}
            · ${verificados}/${filas.length} verificadas</span>
    `;
}

function renderAuditoriaRemitos(item) {
    const ingresos = item.remitos_ingreso || [];
    const egresos = item.remitos_egreso || [];
    $("#tabla-remitos-ingreso").innerHTML = agruparPorRemito(ingresos).map(
        ([remito, filas]) => `
        <details class="remittance-group">
            <summary>${resumenGrupoRemito(remito, filas)}</summary>
            <div class="table-scroll"><table><thead><tr>
                <th>Fecha</th><th>Material</th><th>Pieza relacionada</th>
                <th>Cantidad</th><th>Verificado</th><th>Observación</th><th></th>
            </tr></thead><tbody>
            ${filas.map((fila) => `
                <tr data-ingreso-clave="${escapeHtml(fila.movimiento_clave)}" data-item-id="${fila.item_id}">
                    <td>${fechaMovimiento(fila.fecha)}</td>
                    <td>${escapeHtml(fila.codigo_material || fila.codigo)}</td>
                    <td>${escapeHtml(fila.codigo)}${fila.manual ? '<small class="manual-badge">MANUAL</small>' : ''}</td>
                    <td><input class="ingress-detail-qty" type="number" min="0" step="any" value="${fila.cantidad}">
                        ${fila.cantidad_modificada && !fila.manual ? `<small class="source-quantity">Origen: ${formatearNumero(fila.cantidad_original)}</small>` : ""}</td>
                    <td class="audit-check"><input class="ingress-detail-check" type="checkbox" ${fila.verificado ? "checked" : ""}></td>
                    <td><input class="ingress-detail-note" maxlength="1000" value="${escapeHtml(fila.observacion || "")}" placeholder="Observación"></td>
                    <td>${fila.manual ? '<button type="button" class="link danger-text delete-manual-income">Eliminar</button>' : ''}</td>
                </tr>
            `).join("")}
            </tbody></table></div>
        </details>`
    ).join("");
    $("#remitos-ingreso-vacio").classList.toggle("hidden", ingresos.length > 0);
    $("#tabla-remitos-egreso").innerHTML = agruparPorRemito(egresos).map(
        ([remito, filas]) => `
        <details class="remittance-group">
            <summary>${resumenGrupoRemito(remito, filas)}</summary>
            <div class="table-scroll"><table><thead><tr>
                <th>Fecha</th><th>Pieza despachada</th><th>Cantidad</th>
                <th>Componentes explotados</th><th>Verificado</th><th>Observación</th><th></th>
            </tr></thead><tbody>
            ${filas.map((fila) => `
                <tr data-egreso-clave="${escapeHtml(fila.movimiento_clave)}">
                    <td>${fechaMovimiento(fila.fecha)}</td>
                    <td>${escapeHtml(fila.codigo_pieza)}${fila.manual ? '<small class="manual-badge">MANUAL</small>' : ''}</td>
                    <td><input class="egress-detail-qty" type="number" min="0" step="any" value="${fila.cantidad}">
                        ${fila.cantidad_modificada && !fila.manual ? `<small class="source-quantity">Origen: ${formatearNumero(fila.cantidad_original)}</small>` : ""}</td>
                    <td class="movement-components">${(fila.componentes || []).map((componente) => `
                        <span data-egress-item-id="${componente.item_id}" data-egress-use="${componente.uso}">
                            ${escapeHtml(componente.codigo)}: ${formatearNumero(fila.cantidad)} × ${formatearNumero(componente.uso)}
                            = ${formatearNumero(Number(fila.cantidad) * Number(componente.uso))}
                            ${componente.despacho_directo ? " · despacho directo" : ""}
                        </span>`).join("") || "Sin estructura"}</td>
                    <td class="audit-check"><input class="egress-detail-check" type="checkbox" ${fila.verificado ? "checked" : ""}></td>
                    <td><input class="egress-detail-note" maxlength="1000" value="${escapeHtml(fila.observacion || "")}" placeholder="Observación"></td>
                    <td>${fila.manual ? '<button type="button" class="link danger-text delete-manual-egress">Eliminar</button>' : ''}</td>
                </tr>
            `).join("")}
            </tbody></table></div>
        </details>`
    ).join("");
    $("#remitos-egreso-vacio").classList.toggle("hidden", egresos.length > 0);
    $$(".ingress-detail-qty").forEach((input) => {
        input.addEventListener("input", (event) => {
            const itemId = Number(event.target.closest("tr").dataset.itemId);
            recalcularIngresoDesdeDetalle(itemId);
            programarAutoguardado("conciliacion");
        });
    });
    $$(".delete-manual-income").forEach((button) => {
        button.addEventListener("click", eliminarIngresoManual);
    });
    $$(".egress-detail-qty").forEach((input) => {
        input.addEventListener("input", () => {
            recalcularEgresosDesdeDetalle();
            programarAutoguardado("conciliacion");
        });
    });
    $$(".ingress-detail-check, .egress-detail-check").forEach((input) => {
        input.addEventListener("change", () => programarAutoguardado("conciliacion", 100));
    });
    $$(".ingress-detail-note, .egress-detail-note").forEach((input) => {
        input.addEventListener("input", () => programarAutoguardado("conciliacion"));
    });
    $$(".delete-manual-egress").forEach((button) => {
        button.addEventListener("click", eliminarEgresoManual);
    });
}

function controlesIngresoConciliacion() {
    return $$("#tabla-remitos-ingreso [data-ingreso-clave]").map((fila) => ({
        movimiento_clave: fila.dataset.ingresoClave,
        cantidad: Number(fila.querySelector(".ingress-detail-qty")?.value || 0),
        verificado: Boolean(fila.querySelector(".ingress-detail-check")?.checked),
        observacion: fila.querySelector(".ingress-detail-note")?.value.trim() || "",
    }));
}

function recalcularIngresoDesdeDetalle(itemId) {
    const total = $$(`#tabla-remitos-ingreso [data-item-id="${itemId}"]`)
        .reduce((suma, fila) => suma + Number(
            fila.querySelector(".ingress-detail-qty")?.value || 0
        ), 0);
    const input = document.querySelector(`.movement-in[data-item-id="${itemId}"]`);
    if (input) {
        input.value = String(total);
        input.dispatchEvent(new Event("input", { bubbles: true }));
    }
}

function controlesEgresoConciliacion() {
    return $$("#tabla-remitos-egreso [data-egreso-clave]").map((fila) => ({
        movimiento_clave: fila.dataset.egresoClave,
        cantidad: Number(fila.querySelector(".egress-detail-qty")?.value || 0),
        verificado: Boolean(fila.querySelector(".egress-detail-check")?.checked),
        observacion: fila.querySelector(".egress-detail-note")?.value.trim() || "",
    }));
}

function recalcularEgresosDesdeDetalle() {
    const totales = new Map();
    $$("#tabla-remitos-egreso [data-egreso-clave]").forEach((fila) => {
        const cantidad = Number(fila.querySelector(".egress-detail-qty")?.value || 0);
        fila.querySelectorAll("[data-egress-item-id]").forEach((componente) => {
            const itemId = Number(componente.dataset.egressItemId);
            const uso = Number(componente.dataset.egressUse || 0);
            totales.set(itemId, (totales.get(itemId) || 0) + cantidad * uso);
        });
    });
    state.conciliacionSeleccionada.items.forEach((item) => {
        const input = document.querySelector(`.movement-out[data-item-id="${item.id}"]`);
        if (input) {
            input.value = String(totales.get(item.id) || 0);
            input.dispatchEvent(new Event("input", { bubbles: true }));
        }
    });
}

function movimientosConciliacion() {
    return state.conciliacionSeleccionada.items.map((item) => ({
        item_id: item.id,
        ingresos: Number(
            document.querySelector(
                `.movement-in[data-item-id="${item.id}"]`
            )?.value || 0
        ),
        egresos: Number(
            document.querySelector(
                `.movement-out[data-item-id="${item.id}"]`
            )?.value || 0
        ),
        scrap: Number(
            document.querySelector(
                `.movement-scrap[data-item-id="${item.id}"]`
            )?.value || 0
        ),
    }));
}

function recalcularConciliacionVisual(event) {
    const id = Number(event.target.dataset.itemId);
    const item = state.conciliacionSeleccionada.items.find(
        (linea) => linea.id === id
    );
    const movimiento = movimientosConciliacion().find(
        (linea) => linea.item_id === id
    );
    const esperado = item.stock_inicial + movimiento.ingresos
        - movimiento.egresos - movimiento.scrap;
    const metricas = calcularMetricasConteo(item.stock_final, esperado);
    document.querySelector(`[data-expected="${id}"]`).textContent =
        formatearNumero(esperado);
    const diferencia = document.querySelector(
        `[data-reconciliation-difference="${id}"]`
    );
    diferencia.textContent = numeroConSigno(metricas.diferencia);
    diferencia.classList.toggle("warning", metricas.diferencia !== 0);
    document.querySelector(
        `[data-reconciliation-percentage="${id}"]`
    ).innerHTML = porcentajeConteoHtml(metricas);
}

function abrirModalConciliacion() {
    const completos = state.inventarios
        .filter((item) => item.progreso === 100)
        .sort((a, b) => a.fecha.localeCompare(b.fecha));
    if (completos.length < 2) {
        toast(
            "Necesitás al menos dos inventarios completamente contados",
            true
        );
        return;
    }
    const opciones = completos.map((item) => `
        <option value="${item.id}">
            ${escapeHtml(item.codigo)} · ${formatearFecha(item.fecha)} · ${escapeHtml(item.cliente)}
        </option>
    `).join("");
    $("#conciliacion-inicial").innerHTML = opciones;
    $("#conciliacion-final").innerHTML = opciones;
    $("#conciliacion-inicial").value = String(completos[0].id);
    $("#conciliacion-final").value = String(completos[completos.length - 1].id);
    $("#conciliacion-nombre").value = "";
    abrirModal("#modal-conciliacion");
}

async function crearConciliacion(event) {
    event.preventDefault();
    try {
        const creada = await api("/api/conciliaciones", {
            method: "POST",
            body: JSON.stringify({
                nombre: $("#conciliacion-nombre").value.trim(),
                inventario_inicial_id: Number($("#conciliacion-inicial").value),
                inventario_final_id: Number($("#conciliacion-final").value),
            }),
        });
        state.conciliaciones.unshift(creada);
        state.conciliacionSeleccionada = creada;
        cerrarModales();
        renderConciliaciones();
        abrirConciliacion(creada.id);
        toast("Conciliación creada");
    } catch (error) {
        toast(error.message, true);
    }
}

async function guardarConciliacion({
    automatico = false, conciliacionId = null, payload = null,
} = {}) {
    if (!automatico) {
        window.clearTimeout(autosave.conciliacion.timer);
        autosave.conciliacion.timer = null;
        autosave.conciliacion.dirty = false;
        autosave.conciliacion.failed = false;
        estadoAutoguardado("conciliacion", "saving");
    }
    const item = state.conciliacionSeleccionada;
    const id = conciliacionId || item?.id;
    if (!id) return;
    try {
        const guardada = await api(`/api/conciliaciones/${id}`, {
            method: "PUT",
            body: JSON.stringify(payload || {
                items: movimientosConciliacion(),
                controles_ingreso: controlesIngresoConciliacion(),
                controles_egreso: controlesEgresoConciliacion(),
            }),
        });
        state.conciliaciones = state.conciliaciones.map((actual) =>
            actual.id === guardada.id ? guardada : actual
        );
        if (state.conciliacionSeleccionada?.id === guardada.id) {
            state.conciliacionSeleccionada = guardada;
        }
        if (!automatico) {
            renderConciliaciones();
            estadoAutoguardado("conciliacion", "saved");
            toast("Movimientos guardados");
        }
        return guardada;
    } catch (error) {
        if (!automatico) {
            autosave.conciliacion.failed = true;
            estadoAutoguardado("conciliacion", "error");
            toast(error.message, true);
            return null;
        }
        throw error;
    }
}

function abrirModalIngresoManual() {
    const item = state.conciliacionSeleccionada;
    if (!item) return;
    $("#ingreso-manual-item").innerHTML = item.items.map((linea) => `
        <option value="${linea.id}">${escapeHtml(linea.codigo)} · ${escapeHtml(linea.descripcion)}</option>
    `).join("");
    $("#ingreso-manual-material").value = "";
    $("#ingreso-manual-remito").value = "MANUAL";
    $("#ingreso-manual-fecha").value = String(item.fecha_final).slice(0, 10);
    $("#ingreso-manual-cantidad").value = "";
    $("#ingreso-manual-observacion").value = "";
    abrirModal("#modal-ingreso-manual");
}

async function agregarIngresoManual(event) {
    event.preventDefault();
    const conciliacion = state.conciliacionSeleccionada;
    if (!conciliacion) return;
    try {
        const actualizada = await api(
            `/api/conciliaciones/${conciliacion.id}/ingresos-manuales`,
            {
                method: "POST",
                body: JSON.stringify({
                    item_id: Number($("#ingreso-manual-item").value),
                    codigo_material: $("#ingreso-manual-material").value.trim(),
                    remito: $("#ingreso-manual-remito").value.trim(),
                    fecha: $("#ingreso-manual-fecha").value,
                    cantidad: Number($("#ingreso-manual-cantidad").value),
                    observacion: $("#ingreso-manual-observacion").value.trim(),
                }),
            }
        );
        state.conciliaciones = state.conciliaciones.map((item) =>
            item.id === actualizada.id ? actualizada : item
        );
        state.conciliacionSeleccionada = actualizada;
        cerrarModales();
        renderConciliaciones();
        toast("Ingreso manual agregado");
    } catch (error) {
        toast(error.message, true);
    }
}

async function eliminarIngresoManual(event) {
    const fila = event.target.closest("tr[data-ingreso-clave]");
    const conciliacion = state.conciliacionSeleccionada;
    if (!fila || !conciliacion || !confirm("¿Eliminar este ingreso manual?")) return;
    try {
        const clave = encodeURIComponent(fila.dataset.ingresoClave);
        const actualizada = await api(
            `/api/conciliaciones/${conciliacion.id}/ingresos-manuales/${clave}`,
            { method: "DELETE" }
        );
        state.conciliaciones = state.conciliaciones.map((item) =>
            item.id === actualizada.id ? actualizada : item
        );
        state.conciliacionSeleccionada = actualizada;
        renderConciliaciones();
        toast("Ingreso manual eliminado");
    } catch (error) {
        toast(error.message, true);
    }
}

function abrirModalEgresoManual() {
    const item = state.conciliacionSeleccionada;
    if (!item) return;
    $("#egreso-manual-item").innerHTML = item.items.map((linea) => `
        <option value="${linea.id}">${escapeHtml(linea.codigo)} · ${escapeHtml(linea.descripcion)}</option>
    `).join("");
    $("#egreso-manual-remito").value = "MANUAL";
    $("#egreso-manual-fecha").value = String(item.fecha_final).slice(0, 10);
    $("#egreso-manual-cantidad").value = "";
    $("#egreso-manual-observacion").value = "";
    abrirModal("#modal-egreso-manual");
}

async function agregarEgresoManual(event) {
    event.preventDefault();
    const conciliacion = state.conciliacionSeleccionada;
    if (!conciliacion) return;
    try {
        const actualizada = await api(
            `/api/conciliaciones/${conciliacion.id}/egresos-manuales`,
            {
                method: "POST",
                body: JSON.stringify({
                    item_id: Number($("#egreso-manual-item").value),
                    remito: $("#egreso-manual-remito").value.trim(),
                    fecha: $("#egreso-manual-fecha").value,
                    cantidad: Number($("#egreso-manual-cantidad").value),
                    observacion: $("#egreso-manual-observacion").value.trim(),
                }),
            }
        );
        state.conciliaciones = state.conciliaciones.map((item) =>
            item.id === actualizada.id ? actualizada : item
        );
        state.conciliacionSeleccionada = actualizada;
        cerrarModales();
        renderConciliaciones();
        toast("Egreso manual agregado");
    } catch (error) {
        toast(error.message, true);
    }
}

async function eliminarEgresoManual(event) {
    const fila = event.target.closest("[data-egreso-clave]");
    const conciliacion = state.conciliacionSeleccionada;
    if (!fila || !conciliacion || !confirm("¿Eliminar este egreso manual?")) return;
    try {
        const clave = encodeURIComponent(fila.dataset.egresoClave);
        const actualizada = await api(
            `/api/conciliaciones/${conciliacion.id}/egresos-manuales/${clave}`,
            { method: "DELETE" }
        );
        state.conciliaciones = state.conciliaciones.map((item) =>
            item.id === actualizada.id ? actualizada : item
        );
        state.conciliacionSeleccionada = actualizada;
        renderConciliaciones();
        toast("Egreso manual eliminado");
    } catch (error) {
        toast(error.message, true);
    }
}

async function recalcularMovimientosConciliacion() {
    const item = state.conciliacionSeleccionada;
    if (!item) return;
    if (!confirm(
        "Se volverán a leer los remitos. Las verificaciones, correcciones "
        + "y movimientos manuales existentes se conservarán. ¿Continuar?"
    )) return;
    try {
        const actualizada = await api(
            `/api/conciliaciones/${item.id}/recalcular-movimientos`,
            { method: "POST" }
        );
        state.conciliaciones = state.conciliaciones.map((actual) =>
            actual.id === actualizada.id ? actualizada : actual
        );
        state.conciliacionSeleccionada = actualizada;
        renderConciliaciones();
        toast("Movimientos recalculados desde los remitos");
    } catch (error) {
        toast(error.message, true);
    }
}

async function eliminarConciliacion() {
    const item = state.conciliacionSeleccionada;
    if (!item || !confirm(`¿Eliminar ${item.codigo}?`)) return;
    try {
        await api(`/api/conciliaciones/${item.id}`, { method: "DELETE" });
        state.conciliaciones = state.conciliaciones.filter(
            (actual) => actual.id !== item.id
        );
        state.conciliacionSeleccionada = null;
        renderConciliaciones();
        toast("Conciliación eliminada");
    } catch (error) {
        toast(error.message, true);
    }
}

function cargarSelectPlantillas() {
    const opciones = state.plantillas.map((x) =>
        `<option value="${x.id}" ${x.activa ? "" : "disabled"}>
            ${escapeHtml(x.cliente)} · ${escapeHtml(x.nombre)}
            ${x.activa ? "" : " · INACTIVA"}
        </option>`
    ).join("");
    $("#inventario-plantilla").innerHTML = opciones;
    $("#programacion-plantilla").innerHTML = opciones;
    renderResumenPlantilla();
}

function renderResumenPlantilla() {
    const id = Number($("#inventario-plantilla").value);
    const plantilla = state.plantillas.find((x) => x.id === id);
    $("#plantilla-resumen").innerHTML = plantilla ? `
        <div class="selection-summary-overview">
            <span>▤</span>
            <div>
                <strong>${plantilla.items.length} artículos · ${escapeHtml(plantilla.nombre)}</strong>
                <p>
                    ${escapeHtml(plantilla.descripcion)}
                    ${plantilla.controla_remitos ? " · Controla remitos" : ""}
                </p>
            </div>
        </div>
        <div class="selection-preview-list">
            ${plantilla.items.map((item, indice) => `
                <div>
                    <b>${indice + 1}</b>
                    <p>
                        <strong>${escapeHtml(item.codigo)}</strong>
                        <small>${escapeHtml(item.descripcion)}</small>
                    </p>
                    <span>${escapeHtml(item.codigo_material || "Sin material")}</span>
                </div>
            `).join("")}
        </div>
    ` : "";
    actualizarDisponibilidadModalidadMedios();
}

function abrirDetalle(id) {
    state.inventarioSeleccionado = state.inventarios.find((x) => x.id === id);
    state.datosInventarioAbiertos = false;
    state.remitosAbiertos = false;
    state.focoDiferenciasAbierto = false;
    renderDetalle();
    mostrarVista("detalle");
}

function alternarDatosInventario() {
    if (state.datosInventarioAbiertos) {
        $("#inventory-data-summary").textContent =
            `${ambitoInventarioLabel($("#detalle-ambito").value)} · `
            + `Cierre ${formatearMesCierre($("#detalle-mes-cierre").value)} · `
            + ($("#detalle-comentario").value.trim() || "Sin comentario");
    }
    state.datosInventarioAbiertos = !state.datosInventarioAbiertos;
    renderEstadoDatosInventario();
}

function renderEstadoDatosInventario() {
    const abierto = state.datosInventarioAbiertos;
    const button = $("#btn-toggle-inventory-data");
    $("#inventory-data-fields").classList.toggle("hidden", !abierto);
    $("#btn-guardar-datos").classList.toggle("hidden", !abierto);
    $(".inventory-data-panel").classList.toggle("collapsed", !abierto);
    button.setAttribute("aria-expanded", String(abierto));
    button.innerHTML = abierto
        ? 'Ocultar datos <span>⌃</span>'
        : 'Mostrar datos <span>⌄</span>';
}

function resumenControlRemitos() {
    const ingreso = $("#remito-ingreso").value.trim() || "Sin ingreso";
    const egreso = $("#remito-egreso").value.trim() || "Sin egreso";
    return `Ingreso: ${ingreso} · Egreso: ${egreso}`;
}

function alternarControlRemitos() {
    if (state.remitosAbiertos) {
        $("#remittance-summary").textContent = resumenControlRemitos();
    }
    state.remitosAbiertos = !state.remitosAbiertos;
    renderEstadoControlRemitos();
}

function renderEstadoControlRemitos() {
    const abierto = state.remitosAbiertos;
    const button = $("#btn-toggle-remittances");
    $("#remittance-fields").classList.toggle("hidden", !abierto);
    $(".remittance-panel").classList.toggle("collapsed", !abierto);
    button.setAttribute("aria-expanded", String(abierto));
    button.innerHTML = abierto
        ? 'Ocultar remitos <span>⌃</span>'
        : 'Mostrar remitos <span>⌄</span>';
}

function cambiarVistaConteo(vista) {
    const inventario = state.inventarioSeleccionado;
    if (!inventario) return;
    capturarEdicionConteoLocal();
    state.vistaConteo = vista;
    try {
        window.localStorage.setItem("vistaConteo", vista);
    } catch (_error) {
        // La preferencia funciona durante la sesión aunque el navegador
        // bloquee el almacenamiento local.
    }
    renderDetalle();
}

function capturarEdicionConteoLocal() {
    const inventario = state.inventarioSeleccionado;
    if (!inventario) return;
    const items = new Map(inventario.items.map((item) => [item.id, item]));
    $$(".conteo-input").forEach((input) => {
        const item = items.get(Number(input.dataset.itemId));
        if (!item) return;
        item.conteo_fisico = input.value === "" ? null : Number(input.value);
        const metricas = item.conteo_fisico === null
            ? {
                diferencia: null,
                relacion_porcentaje: null,
                desvio_porcentaje: null,
                dentro_tolerancia: null,
            }
            : calcularMetricasConteo(item.conteo_fisico, item.stock_sistema);
        Object.assign(item, metricas);
        item.causa_diferencia_codigo =
            document.querySelector(
                `.cause-select[data-item-id="${item.id}"]`
            )?.value || null;
        item.ajustado_sistema = Boolean(
            document.querySelector(
                `.system-adjust-checkbox[data-item-id="${item.id}"]`
            )?.checked
        );
        item.observaciones =
            document.querySelector(
                `.item-observation[data-item-id="${item.id}"]`
            )?.value.trim() || "";
    });
    inventario.ambito = $("#detalle-ambito").value;
    inventario.observaciones = $("#detalle-comentario").value;
    inventario.ultimo_remito_ingreso = $("#remito-ingreso").value;
    inventario.ultimo_remito_egreso = $("#remito-egreso").value;
}

function agruparItemsPorPieza(items, combinarMaterialCompartido = false) {
    const grupos = new Map();
    items.forEach((item) => {
        if (!grupos.has(item.codigo)) {
            grupos.set(item.codigo, {
                codigo: item.codigo,
                codigo_cliente: item.codigo_cliente || "",
                descripcion: item.descripcion || "",
                codigo_material: item.codigo_material || "",
                codigos: [item.codigo],
                es_material_compartido: false,
                items: [],
            });
        }
        grupos.get(item.codigo).items.push(item);
    });
    const resultado = [...grupos.values()];
    if (!combinarMaterialCompartido) return resultado;

    const porMaterial = new Map();
    resultado.forEach((grupo) => {
        const productivo = grupo.items.find((item) => item.etapa !== "MATERIAL");
        const codigoMaterial = String(
            productivo?.codigo_material || grupo.codigo_material || "",
        ).trim().toUpperCase();
        if (!codigoMaterial) return;
        if (!porMaterial.has(codigoMaterial)) porMaterial.set(codigoMaterial, []);
        porMaterial.get(codigoMaterial).push(grupo);
    });

    const compartidos = new Map(
        [...porMaterial.entries()].filter(([, candidatos]) => candidatos.length > 1),
    );
    const consumidos = new Set();
    const combinados = [];
    resultado.forEach((grupo) => {
        if (consumidos.has(grupo.codigo)) return;
        const productivo = grupo.items.find((item) => item.etapa !== "MATERIAL");
        const codigoMaterial = String(
            productivo?.codigo_material || grupo.codigo_material || "",
        ).trim().toUpperCase();
        const relacionados = compartidos.get(codigoMaterial);
        if (!relacionados) {
            combinados.push(grupo);
            return;
        }
        relacionados.forEach((item) => consumidos.add(item.codigo));
        const codigos = relacionados.map((item) => item.codigo).sort();
        combinados.push({
            codigo: codigos.join(" + "),
            codigo_cliente: "",
            descripcion: `MP compartida ${codigoMaterial}`,
            codigo_material: codigoMaterial,
            codigos,
            es_material_compartido: true,
            subgrupos: relacionados,
            items: relacionados.flatMap((item) => item.items),
        });
    });
    return combinados;
}

function tituloEtapaConteoCorto(linea) {
    if (linea.etapa === "MATERIAL") {
        return linea.lote ? `MP · ${linea.lote}` : "MP";
    }
    if (linea.etapa === "TERMINADO") return "PT";
    if (linea.etapa === "PROCESO_GLOBAL") return "Proceso";
    if (linea.etapa === "OPERACION") {
        return linea.operacion ? `Proceso ${linea.operacion}` : "Proceso";
    }
    return etapaTexto(linea.etapa);
}

function descripcionMaterialLote(linea) {
    if (linea.etapa !== "MATERIAL") return "";
    const titulo = String(linea.titulo_operacion || "");
    const separador = titulo.indexOf(" · ");
    return separador >= 0 ? titulo.slice(separador + 3).trim() : "";
}

function inputConteoConsolidado(
    linea,
    cerrado,
    codigoGrupo,
    mostrarCodigoPieza = false,
) {
    const diferencia = linea.conteo_fisico === null
        ? null
        : linea.conteo_fisico - linea.stock_sistema;
    const descripcionMaterial = descripcionMaterialLote(linea);
    return `
        <div class="stage-line">
            <div>
                <small>${escapeHtml(tituloEtapaConteoCorto(linea))}</small>
                <span>Sistema <strong>${formatearNumero(linea.stock_sistema)}</strong></span>
                ${Number(linea.stock_asignado || 0) !== 0 ? `
                    <span class="assigned-stock">
                        Asignado <strong>${formatearNumero(linea.stock_asignado)}</strong>
                    </span>
                ` : ""}
                ${linea.etapa === "MATERIAL" && linea.lote && !cerrado ? `
                    <button
                        type="button"
                        class="stage-delete-lot"
                        data-delete-material-lot="${linea.id}"
                        title="Quitar lote ${escapeHtml(linea.lote)}"
                        aria-label="Quitar lote ${escapeHtml(linea.lote)}"
                    >×</button>
                ` : ""}
            </div>
            ${linea.etapa === "MATERIAL" ? `
                <p class="stage-material-description">
                    ${escapeHtml(linea.codigo_material || "MP")}
                    ${descripcionMaterial ? ` · ${escapeHtml(descripcionMaterial)}` : ""}
                </p>
            ` : ""}
            ${mostrarCodigoPieza && linea.etapa !== "MATERIAL" ? `
                <p class="stage-owner-code">Pieza ${escapeHtml(linea.codigo)}</p>
            ` : ""}
            <div class="count-input-detail">
                <label>
                    Físico
                    <input
                        class="conteo-input ${diferencia ? "has-difference" : ""}"
                        data-item-id="${linea.id}"
                        data-group-code="${escapeHtml(codigoGrupo)}"
                        data-stage="${linea.etapa}"
                        data-material-code="${escapeHtml(linea.codigo_material || "")}"
                        data-lot="${escapeHtml(linea.lote || "")}"
                        data-stock="${linea.stock_sistema}"
                        data-stock-pendiente="${linea.stock_pendiente}"
                        type="number"
                        min="0"
                        step="any"
                        value="${linea.conteo_fisico ?? ""}"
                        ${cerrado ? "disabled" : ""}
                    >
                </label>
                <button type="button" data-count-records="${linea.id}">Registros</button>
            </div>
            <span
                class="stage-line-difference ${diferencia ? "warning" : ""}"
                data-diferencia-id="${linea.id}"
            >${diferencia === null ? "—" : numeroConSigno(diferencia)}</span>
            <span class="hidden" data-porcentaje-id="${linea.id}"></span>
        </div>
    `;
}

function stockSistemaLineas(lineas) {
    const materiales = new Map();
    const productivo = lineas.reduce((suma, linea) => {
        if (linea.etapa !== "MATERIAL") return suma + linea.stock_sistema;
        const clave = `${linea.codigo_material || linea.codigo}::${linea.lote || ""}`;
        materiales.set(
            clave,
            Math.max(materiales.get(clave) || 0, Number(linea.stock_sistema || 0)),
        );
        return suma;
    }, 0);
    return productivo + [...materiales.values()].reduce(
        (suma, valor) => suma + valor,
        0,
    );
}

function gruposMaterialPorLote(lineas) {
    const grupos = new Map();
    lineas.forEach((linea) => {
        const clave = `${linea.codigo_material || linea.codigo}::${linea.lote || ""}`;
        if (!grupos.has(clave)) grupos.set(clave, []);
        grupos.get(clave).push(linea);
    });
    return [...grupos.values()];
}

function cantidadLotesMaterial(lineas) {
    return gruposMaterialPorLote(lineas).filter((grupo) => (
        grupo.some((linea) => String(linea.lote || "").trim() !== "")
    )).length;
}

function fisicoMaterialUnico(lineas) {
    const grupos = gruposMaterialPorLote(lineas);
    if (!grupos.length) return { completo: true, total: 0 };
    const valores = grupos.map((grupo) => {
        const contados = grupo
            .map((linea) => linea.conteo_fisico)
            .filter((valor) => valor !== null);
        return contados.length ? Math.max(...contados.map(Number)) : null;
    });
    return {
        completo: valores.every((valor) => valor !== null),
        total: valores.reduce((suma, valor) => suma + Number(valor || 0), 0),
    };
}

function celdaEstadioConsolidada(
    lineas,
    cerrado,
    codigoGrupo,
    mostrarCodigoPieza = false,
) {
    if (!lineas.length) {
        return '<span class="stage-not-applicable">No aplica</span>';
    }
    const esMaterial = lineas.every((linea) => linea.etapa === "MATERIAL");
    if (esMaterial) {
        return celdaMaterialResumen(lineas, cerrado, codigoGrupo);
    }
    const contenido = lineas.map(
        (linea) => inputConteoConsolidado(
            linea,
            cerrado,
            codigoGrupo,
            mostrarCodigoPieza,
        )
    ).join("");
    if (lineas.length === 1) return contenido;
    const fisicos = lineas.filter((linea) => linea.conteo_fisico !== null);
    return `
        <details class="stage-details">
            <summary>
                <span>Sistema ${formatearNumero(
                    stockSistemaLineas(lineas)
                )}</span>
                <strong>
                    ${fisicos.length === lineas.length
                        ? `Físico ${formatearNumero(
                            fisicos.reduce(
                                (suma, linea) => suma + linea.conteo_fisico,
                                0
                            )
                        )}`
                        : `${fisicos.length}/${lineas.length} contados`}
                </strong>
                <small>Ver ${lineas.length} renglones</small>
            </summary>
            <div class="stage-detail-lines">${contenido}</div>
        </details>
    `;
}

function celdaMaterialResumen(lineas, cerrado, codigoGrupo) {
    const sistema = stockSistemaLineas(lineas);
    const gruposLote = gruposMaterialPorLote(lineas);
    const fisicoUnico = fisicoMaterialUnico(lineas);
    const fisico = fisicoUnico.completo ? fisicoUnico.total : null;
    const diferencia = fisico === null ? null : fisico - sistema;
    const codigoMaterial = String(
        lineas[0].codigo_material || lineas[0].codigo || "",
    );
    const descripcion = descripcionMaterialLote(lineas[0]);
    const registros = lineas.reduce(
        (suma, linea) => suma + Number(linea.cantidad_cajas || 0),
        0,
    );
    const ids = lineas.map((linea) => linea.id).join(",");
    const ocultos = lineas.map((linea) => `
        <input
            class="conteo-input material-hidden-count"
            data-item-id="${linea.id}"
            data-group-code="${escapeHtml(codigoGrupo)}"
            data-stage="MATERIAL"
            data-material-code="${escapeHtml(linea.codigo_material || linea.codigo || "")}"
            data-lot="${escapeHtml(linea.lote || "")}"
            data-stock="${linea.stock_sistema}"
            data-stock-pendiente="${linea.stock_pendiente}"
            type="hidden"
            value="${linea.conteo_fisico ?? ""}"
        >
    `).join("");
    return `
        <div class="stage-line material-summary-card">
            ${ocultos}
            <div>
                <small>MP</small>
                <span>Sistema <strong>${formatearNumero(sistema)}</strong></span>
            </div>
            <p class="stage-material-description">
                ${escapeHtml(codigoMaterial)}${descripcion ? ` · ${escapeHtml(descripcion)}` : ""}
            </p>
            <div class="material-summary-values">
                <span><small>Físico</small><strong>${fisico === null ? "—" : formatearNumero(fisico)}</strong></span>
                <span><small>Lotes</small><strong>${cantidadLotesMaterial(lineas)}</strong></span>
            </div>
            <div class="count-input-detail">
                <button type="button" data-count-material="${ids}">
                    Registros${registros ? ` · ${registros}` : ""}
                </button>
            </div>
            <span class="stage-line-difference ${diferencia ? "warning" : ""}">
                ${diferencia === null ? "—" : numeroConSigno(diferencia)}
            </span>
        </div>
    `;
}

function metricasGrupoPieza(grupo) {
    const material = grupo.items.filter((item) => item.etapa === "MATERIAL");
    const proceso = grupo.items.filter((item) => (
        item.etapa === "PROCESO_GLOBAL" || item.etapa === "OPERACION"
    ));
    const terminadas = grupo.items.filter((item) => item.etapa === "TERMINADO");
    const productivos = [...proceso, ...terminadas];
    const comparables = [...material, ...productivos];
    const fisicoMaterial = fisicoMaterialUnico(material);
    const completo = comparables.length > 0
        && fisicoMaterial.completo
        && productivos.every((item) => item.conteo_fisico !== null);
    const sistema = stockSistemaLineas(comparables);
    const fisico = completo
        ? fisicoMaterial.total + productivos.reduce(
            (suma, item) => suma + Number(item.conteo_fisico || 0),
            0,
        )
        : null;
    const diferencia = fisico === null ? null : fisico - sistema;
    const metricasDesvio = fisico === null
        ? null
        : calcularMetricasConteo(fisico, sistema);
    const diferenciaProceso = proceso.every(
        (item) => item.conteo_fisico !== null
    )
        ? proceso.reduce(
            (suma, item) => suma + item.conteo_fisico - item.stock_sistema,
            0
        )
        : null;
    const diferenciaTerminada = terminadas.every(
        (item) => item.conteo_fisico !== null
    )
        ? terminadas.reduce(
            (suma, item) => suma + item.conteo_fisico - item.stock_sistema,
            0
        )
        : null;

    let diagnostico = "Pendiente de completar";
    let clase = "pending";
    if (!comparables.length) {
        diagnostico = "Sin renglones comparables";
        clase = "neutral";
    } else if (completo && Math.abs(diferencia) < 1e-9) {
        if (
            diferenciaProceso < 0
            && diferenciaTerminada > 0
            && Math.abs(diferenciaProceso + diferenciaTerminada) < 1e-9
        ) {
            diagnostico = "Posible producción sin declarar";
            clase = "shift";
        } else if (
            diferenciaProceso > 0
            && diferenciaTerminada < 0
            && Math.abs(diferenciaProceso + diferenciaTerminada) < 1e-9
        ) {
            diagnostico = "Posible ajuste entre etapas";
            clase = "shift";
        } else {
            diagnostico = "Total general correcto";
            clase = "ok";
        }
    } else if (completo && metricasDesvio?.dentro_tolerancia) {
        diagnostico = "Dentro de tolerancia";
        clase = "ok";
    } else if (completo) {
        diagnostico = "Diferencia real de stock";
        clase = "difference";
    }
    return {
        sistema,
        fisico,
        diferencia,
        desvio_porcentaje: metricasDesvio?.desvio_porcentaje ?? null,
        dentro_tolerancia: metricasDesvio?.dentro_tolerancia ?? null,
        diagnostico,
        clase,
    };
}

function analisisGrupoHtml(grupo, cerrado) {
    return grupo.items.map((linea) => `
        <div class="piece-analysis-item">
            <div>
                <strong>${etapaTexto(linea.etapa)}</strong>
                <small>${escapeHtml(
                    linea.titulo_operacion || linea.operacion || ""
                )}</small>
            </div>
            <label class="piece-analysis-cause">
                Causa
                <select
                    class="cause-select"
                    data-item-id="${linea.id}"
                    ${cerrado ? "disabled" : ""}
                >${opcionesCausasDiferencia(
                    linea.causa_diferencia_codigo
                )}</select>
            </label>
            <label class="piece-analysis-observation">
                Observación
                <textarea
                    class="item-observation"
                    data-item-id="${linea.id}"
                    maxlength="1000"
                    rows="2"
                    ${cerrado ? "disabled" : ""}
                >${escapeHtml(linea.observaciones || "")}</textarea>
            </label>
            ${ajusteSistemaHtml(linea, cerrado)}
        </div>
    `).join("");
}

function ajusteSistemaHtml(linea, cerrado) {
    const requiereAjuste = linea.dentro_tolerancia === false;
    const deshabilitado = cerrado || !requiereAjuste;
    let detalle = "Corrección todavía no registrada";
    if (linea.ajustado_sistema_en) {
        detalle = `Marcado ${formatearFechaHora(linea.ajustado_sistema_en)}`;
    } else if (linea.dentro_tolerancia === true) {
        detalle = "Dentro de tolerancia: no requiere ajuste";
    } else if (linea.dentro_tolerancia == null) {
        detalle = "Se habilita si el conteo queda fuera de tolerancia";
    }
    return `
        <label
            class="system-adjust-control
                ${linea.ajustado_sistema ? "checked" : ""}
                ${deshabilitado ? "not-required" : ""}"
            data-adjust-control="${linea.id}"
        >
            <input
                class="system-adjust-checkbox"
                data-item-id="${linea.id}"
                type="checkbox"
                ${linea.ajustado_sistema ? "checked" : ""}
                ${deshabilitado ? "disabled" : ""}
            >
            <span>
                <strong>${requiereAjuste
                    ? "Ajustado en sistema"
                    : "No requiere ajuste"}</strong>
                <small>${detalle}</small>
            </span>
        </label>
    `;
}

function tipoEstructuraHtml(tipo) {
    const normalizado = String(tipo || "INDEPENDIENTE").toUpperCase();
    const etiquetas = {
        PADRE: "Padre",
        SUBCONJUNTO: "Subconjunto",
        HIJO: "Hijo",
        INDEPENDIENTE: "Independiente",
    };
    return `
        <span class="structure-role role-${normalizado.toLowerCase()}">
            ${etiquetas[normalizado] || "Independiente"}
        </span>
    `;
}

function historialAnalisisPiezaHtml(inventario, grupo, metricas) {
    const diagnostico = diagnosticoDiferencia(inventario, { ...grupo, metricas });
    return `
        <div class="piece-history-panel">
            <div class="piece-history-heading">
                <span>HISTORIAL Y TENDENCIA</span>
                <strong>${escapeHtml(grupo.codigo)} · ${escapeHtml(grupo.descripcion || "Sin descripción")}</strong>
                <div class="difference-diagnosis ${diagnostico.clase}">
                    <strong>${escapeHtml(diagnostico.etiqueta)}</strong>
                    <span>${escapeHtml(diagnostico.detalle)}</span>
                </div>
            </div>
            <div class="piece-history-current">
                <span><small>Sistema actual</small><strong>${formatearNumero(metricas.sistema)}</strong></span>
                <span><small>Físico actual</small><strong>${metricas.fisico === null ? "—" : formatearNumero(metricas.fisico)}</strong></span>
                <span class="${metricas.diferencia ? "has-difference" : ""}"><small>Diferencia</small><strong>${metricas.diferencia === null ? "—" : numeroConSigno(metricas.diferencia)}</strong></span>
            </div>
            <div class="difference-focus-history piece-history-previous">
                <label>Últimos conteos <small>Diferencia · desvío</small></label>
                <div>${historialPiezaHtml(inventario, grupo.codigo)}</div>
            </div>
        </div>
    `;
}

function observacionRegistroConteo(observacion) {
    const valor = String(observacion || "").trim();
    const coincidencia = valor.match(/^\[(DISPONIBLE|LINEA|SCRAP)\]\s*/);
    const ubicaciones = {
        DISPONIBLE: "Disponible",
        LINEA: "En línea",
        SCRAP: "Scrap",
    };
    const detalle = valor.replace(/^\[(DISPONIBLE|LINEA|SCRAP)\]\s*/, "").trim();
    if (coincidencia && detalle) return `${ubicaciones[coincidencia[1]]} · ${detalle}`;
    if (coincidencia) return ubicaciones[coincidencia[1]];
    return detalle || "Sin ubicación informada";
}

async function abrirDetalleRegistrosConteo(itemId, conservarMaterial = false) {
    const inventario = state.inventarioSeleccionado;
    const item = inventario?.items.find((linea) => linea.id === Number(itemId));
    if (!inventario || !item) return;
    if (!conservarMaterial) state.countRecordsMaterialIds = [];
    state.countRecordsItemId = Number(itemId);
    $("#btn-back-material-lots").classList.toggle(
        "hidden",
        !state.countRecordsMaterialIds.length,
    );
    $("#count-records-title").textContent = item.etapa === "MATERIAL"
        ? `MP ${item.codigo_material || item.codigo} · Lote ${item.lote || "sin lote"}`
        : `${item.codigo} · ${etapaTexto(item.etapa)}`;
    $("#count-records-subtitle").textContent = item.etapa === "MATERIAL"
        ? (descripcionMaterialLote(item) || item.descripcion || "Sin descripción")
        : (item.descripcion || "Sin descripción");
    $("#count-records-summary").innerHTML = "";
    $("#count-records-list").innerHTML = '<div class="count-records-empty">Cargando registros…</div>';
    $("#form-count-records-add").classList.toggle(
        "hidden",
        inventario.estado === "Cerrado",
    );
    $("#btn-confirm-count-zero").classList.add("hidden");
    abrirModal("#modal-detalle-registros");
    try {
        const detalle = await api(`/api/inventarios/${inventario.id}/conteo-movil/cajas/${item.id}`);
        const base = Math.abs(Number(detalle.conteo_base || 0)) < 1e-9
            ? 0 : Number(detalle.conteo_base);
        $("#count-records-summary").innerHTML = `
            <span><small>Físico acumulado</small><strong>${detalle.conteo_fisico == null ? "—" : formatearNumero(detalle.conteo_fisico)}</strong></span>
            <span><small>Base / edición PC</small><strong>${formatearNumero(base)}</strong></span>
            <span><small>Cargas móviles</small><strong>${formatearNumero(detalle.total_registros)}</strong></span>
            <span><small>Registros</small><strong>${detalle.cantidad_registros}</strong></span>
        `;
        const filas = [];
        if (base !== 0 || !detalle.cajas.length) {
            filas.push(`<div class="count-record-row base">
                <span class="count-record-index">Base</span>
                <div><strong>Carga directa o edición desde PC</strong><small>No pertenece a un registro móvil individual.</small></div>
                <strong>${formatearNumero(base)}</strong>
            </div>`);
        }
        detalle.cajas.forEach((caja, indice) => {
            filas.push(`<div class="count-record-row">
                <span class="count-record-index">${indice + 1}</span>
                <div><strong>${escapeHtml(observacionRegistroConteo(caja.observacion))}</strong><small>${escapeHtml(caja.dispositivo || "Dispositivo sin identificar")} · ${formatearFechaHora(caja.capturado_en)}</small></div>
                <strong>${formatearNumero(caja.cantidad)}</strong>
                ${inventario.estado === "Cerrado" ? "" : `
                    <button
                        type="button"
                        class="count-record-delete"
                        data-delete-count-record="${caja.id}"
                        data-record-quantity="${caja.cantidad}"
                        title="Eliminar registro"
                        aria-label="Eliminar registro de ${formatearNumero(caja.cantidad)} unidades"
                    >⌫</button>
                `}
            </div>`);
        });
        $("#count-records-list").innerHTML = filas.length
            ? filas.join("")
            : '<div class="count-records-empty">Todavía no hay un conteo acumulado para este renglón.</div>';
        const puedeConfirmarCero = inventario.estado !== "Cerrado"
            && item.etapa === "MATERIAL"
            && detalle.cajas.length === 0
            && (detalle.conteo_fisico === null || Number(detalle.conteo_fisico) === 0);
        const botonCero = $("#btn-confirm-count-zero");
        botonCero.classList.toggle("hidden", !puedeConfirmarCero);
        botonCero.disabled = detalle.conteo_fisico !== null;
        botonCero.textContent = detalle.conteo_fisico === null
            ? "Confirmar físico 0"
            : "✓ Físico 0 confirmado";
    } catch (error) {
        $("#count-records-list").innerHTML = `<div class="count-records-empty error">${escapeHtml(error.message)}</div>`;
    }
}

function abrirDetalleLotesMaterial(itemIds) {
    const inventario = state.inventarioSeleccionado;
    const ids = new Set(itemIds.map(Number));
    const lineas = inventario?.items.filter((item) => (
        ids.has(Number(item.id)) && item.etapa === "MATERIAL"
    )) || [];
    if (!inventario || !lineas.length) return;
    state.countRecordsMaterialIds = lineas.map((linea) => Number(linea.id));
    state.countRecordsItemId = null;
    $("#btn-back-material-lots").classList.add("hidden");
    const codigoMaterial = String(
        lineas[0].codigo_material || lineas[0].codigo || "",
    );
    const sistema = stockSistemaLineas(lineas);
    const gruposLote = gruposMaterialPorLote(lineas);
    const fisicoUnico = fisicoMaterialUnico(lineas);
    const fisico = fisicoUnico.completo ? fisicoUnico.total : null;
    const diferencia = fisico === null ? null : fisico - sistema;
    $("#count-records-title").textContent = `MP ${codigoMaterial}`;
    $("#count-records-subtitle").textContent = "Elegí un lote para ver o agregar sus registros.";
    $("#form-count-records-add").classList.add("hidden");
    $("#count-records-summary").innerHTML = `
        <span><small>Stock sistema</small><strong>${formatearNumero(sistema)}</strong></span>
        <span><small>Físico acumulado</small><strong>${fisico === null ? "—" : formatearNumero(fisico)}</strong></span>
        <span><small>Diferencia</small><strong class="${diferencia ? "warning" : ""}">${diferencia === null ? "—" : numeroConSigno(diferencia)}</strong></span>
        <span><small>Lotes</small><strong>${cantidadLotesMaterial(lineas)}</strong></span>
    `;
    $("#count-records-list").innerHTML = `
        <div class="material-lot-grid">
            ${gruposLote.map((grupoLote) => {
                const linea = [...grupoLote].sort((a, b) => (
                    Number(b.stock_sistema || 0) - Number(a.stock_sistema || 0)
                    || Number(b.cantidad_cajas || 0) - Number(a.cantidad_cajas || 0)
                ))[0];
                const conteos = grupoLote
                    .map((item) => item.conteo_fisico)
                    .filter((valor) => valor !== null)
                    .map(Number);
                const fisicoLote = conteos.length ? Math.max(...conteos) : null;
                const sistemaLote = Math.max(
                    ...grupoLote.map((item) => Number(item.stock_sistema || 0)),
                );
                const diferenciaLote = fisicoLote === null
                    ? null
                    : fisicoLote - sistemaLote;
                return `<article class="material-lot-card">
                    <div class="material-lot-card-head">
                        <span><small>Lote</small><strong>${escapeHtml(linea.lote || "Sin lote")}</strong></span>
                        ${inventario.estado === "Cerrado" || !linea.lote || grupoLote.length > 1 ? "" : `
                            <button type="button" data-modal-delete-material-lot="${linea.id}" title="Quitar lote">×</button>
                        `}
                    </div>
                    <div class="material-lot-card-values">
                        <span><small>Sistema</small><strong>${formatearNumero(sistemaLote)}</strong></span>
                        <span><small>Físico</small><strong>${fisicoLote === null ? "—" : formatearNumero(fisicoLote)}</strong></span>
                        <span class="${diferenciaLote ? "warning" : ""}"><small>Diferencia</small><strong>${diferenciaLote === null ? "—" : numeroConSigno(diferenciaLote)}</strong></span>
                    </div>
                    <div class="material-lot-origin-actions">
                        ${grupoLote.map((origen) => `
                            <button type="button" class="material-lot-open" data-open-lot-records="${origen.id}">
                                Registros${grupoLote.length > 1 ? ` · ${escapeHtml(origen.codigo)}` : ""}${Number(origen.cantidad_cajas || 0) ? ` · ${origen.cantidad_cajas}` : ""}
                            </button>
                        `).join("")}
                    </div>
                </article>`;
            }).join("")}
        </div>
        ${inventario.estado === "Cerrado" ? "" : `
            <button
                type="button"
                class="stage-add-lot modal-add-lot"
                data-modal-add-material-lot="${escapeHtml(codigoMaterial)}"
                data-add-material-lot="${escapeHtml(codigoMaterial)}"
                data-lot-piece-code="${escapeHtml(lineas[0].codigo)}"
            >＋ Agregar lote</button>
        `}
    `;
    abrirModal("#modal-detalle-registros");
}

function uidRegistroPC(indice) {
    const aleatorio = window.crypto?.randomUUID
        ? window.crypto.randomUUID()
        : Math.random().toString(36).slice(2);
    return `pc-${Date.now()}-${indice}-${aleatorio}`.slice(0, 64);
}

async function agregarRegistrosDesdePC(event) {
    event.preventDefault();
    const inventario = state.inventarioSeleccionado;
    const itemId = Number(state.countRecordsItemId);
    const cantidad = Number($("#count-record-quantity").value);
    const cantidadRegistros = Number($("#count-record-count").value);
    const observacion = $("#count-record-observation").value.trim();
    const desdeMaterial = state.countRecordsMaterialIds.length > 0;
    if (!inventario || !itemId) return;
    if (!Number.isInteger(cantidad) || cantidad <= 0) {
        toast("La cantidad por registro debe ser un entero mayor que cero", true);
        return;
    }
    if (!Number.isInteger(cantidadRegistros) || cantidadRegistros < 1 || cantidadRegistros > 100) {
        toast("Podés agregar entre 1 y 100 registros por vez", true);
        return;
    }
    const boton = event.submitter;
    if (boton) boton.disabled = true;
    try {
        await guardarAntesDeEditarLotes();
        const respuesta = await api(
            `/api/inventarios/${inventario.id}/conteo-movil/cajas`,
            {
                method: "POST",
                body: JSON.stringify({
                    cajas: Array.from({ length: cantidadRegistros }, (_, indice) => ({
                        cliente_uid: uidRegistroPC(indice),
                        item_id: itemId,
                        cantidad,
                        observacion,
                        dispositivo: "PC",
                        capturado_en: new Date().toISOString(),
                    })),
                }),
            },
        );
        reemplazarInventario(respuesta.inventario);
        renderTodo();
        renderDetalle();
        $("#count-record-quantity").value = "";
        $("#count-record-count").value = "1";
        $("#count-record-observation").value = "";
        await abrirDetalleRegistrosConteo(itemId, desdeMaterial);
        toast(`${cantidadRegistros} registro${cantidadRegistros === 1 ? "" : "s"} agregado${cantidadRegistros === 1 ? "" : "s"}`);
    } catch (error) {
        toast(error.message, true);
    } finally {
        if (boton) boton.disabled = false;
    }
}

async function confirmarConteoCeroDesdePC() {
    const inventario = state.inventarioSeleccionado;
    const itemId = Number(state.countRecordsItemId);
    const item = inventario?.items.find((linea) => linea.id === itemId);
    if (!inventario || !item || item.etapa !== "MATERIAL") return;
    const boton = $("#btn-confirm-count-zero");
    boton.disabled = true;
    try {
        const payload = datosConteoActuales();
        const conteo = payload.items.find((linea) => linea.item_id === itemId);
        if (!conteo) throw new Error("No se encontró el renglón de materia prima");
        conteo.conteo_fisico = 0;
        const actualizado = await guardarConteo({ automatico: true, payload });
        if (!actualizado) return;
        renderTodo();
        renderDetalle();
        await abrirDetalleRegistrosConteo(itemId, state.countRecordsMaterialIds.length > 0);
        toast("Físico 0 confirmado · conteo completo");
    } catch (error) {
        boton.disabled = false;
        toast(error.message, true);
    }
}

async function eliminarRegistroConteoDesdePC(button) {
    const inventario = state.inventarioSeleccionado;
    const itemId = Number(state.countRecordsItemId);
    const cajaId = Number(button.dataset.deleteCountRecord);
    const cantidad = Number(button.dataset.recordQuantity || 0);
    const desdeMaterial = state.countRecordsMaterialIds.length > 0;
    if (!inventario || !itemId || !cajaId) return;
    if (!window.confirm(`¿Eliminar el registro de ${formatearNumero(cantidad)} unidades?`)) return;
    button.disabled = true;
    try {
        await guardarAntesDeEditarLotes();
        const resultado = await api(
            `/api/inventarios/${inventario.id}/conteo-movil/cajas/${cajaId}`,
            { method: "DELETE" },
        );
        if (!resultado.eliminada) throw new Error("El registro ya no existe");
        reemplazarInventario(resultado.inventario);
        renderTodo();
        renderDetalle();
        await abrirDetalleRegistrosConteo(itemId, desdeMaterial);
        toast(`Registro eliminado · físico ${formatearNumero(resultado.conteo_fisico)}`);
    } catch (error) {
        button.disabled = false;
        toast(error.message, true);
    }
}

async function guardarAntesDeEditarLotes() {
    window.clearTimeout(autosave.conteo.timer);
    autosave.conteo.timer = null;
    autosave.conteo.dirty = false;
    await guardarConteo({
        automatico: true,
        payload: datosConteoActuales(),
    });
}

async function agregarLoteMaterialDesdeConteo(button) {
    const codigoMaterial = button.dataset.addMaterialLot;
    const codigoPieza = button.dataset.lotPieceCode;
    const lote = window.prompt(
        `Número de lote para ${codigoMaterial} (${codigoPieza})`,
        "",
    )?.trim();
    if (!lote) return;
    if (!/^\d{5}$/.test(lote)) {
        toast("El lote debe tener exactamente 5 dígitos", true);
        return;
    }
    try {
        await guardarAntesDeEditarLotes();
        const actualizado = await api(
            `/api/inventarios/${state.inventarioSeleccionado.id}/materiales/${encodeURIComponent(codigoMaterial)}/lotes`,
            {
                method: "POST",
                body: JSON.stringify({
                    lote,
                    codigo_pieza: codigoPieza,
                }),
            },
        );
        reemplazarInventario(actualizado);
        renderTodo();
        renderDetalle();
        toast(`Lote ${lote} agregado a ${codigoPieza}`);
    } catch (error) {
        toast(error.message, true);
    }
}

async function eliminarLoteMaterialDesdeConteo(button) {
    const itemId = Number(button.dataset.deleteMaterialLot);
    const item = state.inventarioSeleccionado?.items.find(
        (linea) => linea.id === itemId,
    );
    if (!item?.lote) return;
    if (!window.confirm(`¿Quitar el lote ${item.lote} de ${item.codigo}?`)) {
        return;
    }
    try {
        await guardarAntesDeEditarLotes();
        const actualizado = await api(
            `/api/inventarios/${state.inventarioSeleccionado.id}/lotes/${itemId}`,
            { method: "DELETE" },
        );
        reemplazarInventario(actualizado);
        renderTodo();
        renderDetalle();
        toast(`Lote ${item.lote} eliminado`);
    } catch (error) {
        toast(error.message, true);
    }
}

function identidadGrupoPiezaHtml(grupo) {
    const tipo = grupo.items.find(
        (linea) => linea.etapa !== "MATERIAL",
    )?.tipo_estructura || "INDEPENDIENTE";
    return `<td class="piece-summary-identity structure-identity role-${tipo.toLowerCase()}">
        <strong>${escapeHtml(grupo.codigo)}</strong>
        <small>${escapeHtml(grupo.codigo_cliente || "")}</small>
        ${tipoEstructuraHtml(tipo)}
        <span>${escapeHtml(grupo.descripcion || "")}</span>
    </td>`;
}

function resultadoGrupoPiezaHtml(grupo, metricas, cerrado, rowspan = 1) {
    const tieneAnalisis = grupo.items.some((item) => (
        item.causa_diferencia_codigo
        || item.ajustado_sistema
        || (item.observaciones || "").trim()
    ));
    const cantidadAjustada = grupo.items.filter(
        (item) => item.ajustado_sistema
    ).length;
    const idSeguro = grupo.items[0]?.id;
    const atributoRowspan = rowspan > 1 ? ` rowspan="${rowspan}"` : "";
    const envolverResultadoCompartido = (contenido, clase = "") => (
        rowspan > 1
            ? `<div class="shared-result-content ${clase}">${contenido}</div>`
            : contenido
    );
    const totalHtml = `
        <small>Sistema</small>
        <strong>${formatearNumero(metricas.sistema)}</strong>
        <small>Físico</small>
        <strong data-group-physical>${metricas.fisico === null ? "—" : formatearNumero(metricas.fisico)}</strong>
        <span class="${metricas.diferencia ? "warning" : ""}" data-group-difference>
            ${metricas.diferencia === null ? "—" : numeroConSigno(metricas.diferencia)}
        </span>
    `;
    const desvioHtml = metricas.desvio_porcentaje === null
        ? '<strong class="pending-deviation">—</strong><small>Pendiente</small>'
        : `
            <strong class="${metricas.dentro_tolerancia
                ? "within-tolerance"
                : "outside-tolerance"}">
                ${numeroPorcentajeConSigno(metricas.desvio_porcentaje)}
            </strong>
            <small>${metricas.dentro_tolerancia
                ? "Dentro de tolerancia"
                : "Fuera de tolerancia"}</small>
        `;
    const diagnosticoHtml = `
        <span class="piece-diagnosis ${metricas.clase}" data-group-diagnosis>
            ${metricas.diagnostico}
        </span>
    `;
    const accionesHtml = `
        <div class="piece-row-action-group">
            <button
                type="button"
                class="piece-analysis-toggle ${tieneAnalisis ? "completed" : ""}"
                data-piece-analysis="${idSeguro}"
            >${cantidadAjustada
                ? `✓ ${cantidadAjustada}/${grupo.items.length} ajust.`
                : (tieneAnalisis ? "● Revisar" : "＋ Analizar")}</button>
            ${cerrado || grupo.es_material_compartido ? "" : `
                <button
                    type="button"
                    class="count-delete-button icon-only"
                    data-delete-piece="${grupo.items.map((item) => item.id).join(",")}"
                    data-delete-label="${escapeHtml(grupo.codigo)}"
                    aria-label="Quitar la pieza ${escapeHtml(grupo.codigo)}"
                    title="Quitar la pieza completa del inventario"
                >
                    <svg aria-hidden="true" viewBox="0 0 24 24">
                        <path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5"/>
                    </svg>
                </button>
            `}
        </div>
    `;
    return `
        <td${atributoRowspan} class="productive-total ${rowspan > 1 ? "shared-result-cell" : ""}" data-group-total="${escapeHtml(grupo.codigo)}">
            ${envolverResultadoCompartido(totalHtml, "shared-result-total")}
        </td>
        <td${atributoRowspan} class="summary-deviation ${rowspan > 1 ? "shared-result-cell" : ""}" data-group-deviation>
            ${envolverResultadoCompartido(desvioHtml, "shared-result-deviation")}
        </td>
        <td${atributoRowspan} class="${rowspan > 1 ? "shared-result-cell" : ""}">
            ${envolverResultadoCompartido(diagnosticoHtml, "shared-result-diagnosis")}
        </td>
        <td${atributoRowspan} class="count-row-actions ${rowspan > 1 ? "shared-result-cell" : ""}">
            ${envolverResultadoCompartido(accionesHtml, "shared-result-actions")}
        </td>
    `;
}

function analisisGrupoPiezaFilaHtml(grupo, cerrado) {
    const idSeguro = grupo.items[0]?.id;
    return `<tr id="piece-analysis-${idSeguro}" class="piece-analysis-row hidden">
        <td colspan="8">
            <div data-piece-history-slot="${idSeguro}"></div>
            <div class="piece-analysis-grid">${analisisGrupoHtml(grupo, cerrado)}</div>
        </td>
    </tr>`;
}

function renderGrupoMaterialCompartido(grupo, cerrado) {
    const piezas = grupo.subgrupos || [];
    const material = grupo.items.filter((item) => item.etapa === "MATERIAL");
    const metricas = metricasGrupoPieza(grupo);
    return piezas.map((pieza, indice) => {
        const proceso = pieza.items.filter((item) => (
            item.etapa === "PROCESO_GLOBAL" || item.etapa === "OPERACION"
        ));
        const terminado = pieza.items.filter((item) => item.etapa === "TERMINADO");
        const primera = indice === 0;
        return `
            <tr class="piece-summary-row shared-material-row ${primera ? "shared-group-first" : "shared-group-continuation"}" data-piece-code="${escapeHtml(grupo.codigo)}" data-piece-member="${escapeHtml(pieza.codigo)}">
                ${identidadGrupoPiezaHtml(pieza)}
                ${primera ? `<td rowspan="${piezas.length}" class="shared-material-cell">${celdaEstadioConsolidada(material, cerrado, grupo.codigo)}</td>` : ""}
                <td>${celdaEstadioConsolidada(proceso, cerrado, grupo.codigo)}</td>
                <td>${celdaEstadioConsolidada(terminado, cerrado, grupo.codigo)}</td>
                ${primera ? resultadoGrupoPiezaHtml(grupo, metricas, cerrado, piezas.length) : ""}
            </tr>
            ${indice === piezas.length - 1 ? analisisGrupoPiezaFilaHtml(grupo, cerrado) : ""}
        `;
    }).join("");
}

function renderConteoPorPieza(inventario, cerrado) {
    return agruparItemsPorPieza(inventario.items, true).map((grupo) => {
        if (grupo.es_material_compartido) {
            return renderGrupoMaterialCompartido(grupo, cerrado);
        }
        const material = grupo.items.filter((item) => item.etapa === "MATERIAL");
        const proceso = grupo.items.filter((item) => (
            item.etapa === "PROCESO_GLOBAL" || item.etapa === "OPERACION"
        ));
        const terminado = grupo.items.filter((item) => item.etapa === "TERMINADO");
        const metricas = metricasGrupoPieza(grupo);
        return `
            <tr class="piece-summary-row" data-piece-code="${escapeHtml(grupo.codigo)}">
                ${identidadGrupoPiezaHtml(grupo)}
                <td>${celdaEstadioConsolidada(material, cerrado, grupo.codigo)}</td>
                <td>${celdaEstadioConsolidada(proceso, cerrado, grupo.codigo)}</td>
                <td>${celdaEstadioConsolidada(terminado, cerrado, grupo.codigo)}</td>
                ${resultadoGrupoPiezaHtml(grupo, metricas, cerrado)}
            </tr>
            ${analisisGrupoPiezaFilaHtml(grupo, cerrado)}
        `;
    }).join("");
}

function renderConteoMedios(inventario, cerrado) {
    return inventario.items.map((linea) => {
        const totalCompleto = [
            linea.conteo_vacios,
            linea.conteo_llenos,
            linea.conteo_rotos,
        ].every((valor) => valor !== null);
        const total = totalCompleto
            ? linea.conteo_vacios + linea.conteo_llenos + linea.conteo_rotos
            : null;
        const utilizables = linea.conteo_vacios;
        const metricas = total === null
            ? {
                diferencia: null,
                relacion_porcentaje: null,
                dentro_tolerancia: null,
            }
            : calcularMetricasConteo(total, linea.stock_sistema);
        const tieneAnalisis = Boolean(
            linea.causa_diferencia_codigo
            || linea.ajustado_sistema
            || (linea.observaciones || "").trim()
        );
        return `
            <tr class="media-count-row">
                <td class="structure-identity role-${String(
                    linea.tipo_estructura || "INDEPENDIENTE"
                ).toLowerCase()}">
                    <strong>${escapeHtml(linea.codigo)}</strong>
                    ${tipoEstructuraHtml(linea.tipo_estructura)}
                </td>
                <td>${escapeHtml(linea.codigo_cliente || "—")}</td>
                <td>${escapeHtml(linea.descripcion)}</td>
                <td class="system-column">${formatearNumero(linea.stock_sistema)}</td>
                ${["vacios", "llenos", "rotos"].map((tipo) => `
                    <td>
                        <input
                            class="media-count-input"
                            data-item-id="${linea.id}"
                            data-media-kind="${tipo}"
                            type="number"
                            min="0"
                            step="any"
                            value="${linea[`conteo_${tipo}`] ?? ""}"
                            ${cerrado ? "disabled" : ""}
                        >
                    </td>
                `).join("")}
                <td data-media-usable="${linea.id}">
                    ${utilizables === null ? "—" : formatearNumero(utilizables)}
                </td>
                <td data-media-total="${linea.id}">
                    <strong>${total === null ? "—" : formatearNumero(total)}</strong>
                    <input
                        class="conteo-input media-total-input"
                        data-item-id="${linea.id}"
                        data-stock="${linea.stock_sistema}"
                        data-stock-pendiente="${linea.stock_pendiente}"
                        type="hidden"
                        value="${total ?? ""}"
                    >
                </td>
                <td
                    class="system-column difference ${metricas.diferencia ? "warning" : ""}"
                    data-diferencia-id="${linea.id}"
                >${metricas.diferencia === null ? "—" : numeroConSigno(metricas.diferencia)}</td>
                <td class="system-column percentage-cell" data-porcentaje-id="${linea.id}">
                    ${porcentajeConteoHtml(metricas)}
                </td>
                <td class="count-row-actions">
                    <div class="media-row-actions">
                        <button
                            type="button"
                            class="item-analysis-toggle ${tieneAnalisis ? "completed" : ""}"
                            data-item-id="${linea.id}"
                            aria-expanded="false"
                            aria-controls="item-analysis-${linea.id}"
                        >${linea.ajustado_sistema
                            ? "✓ Ajustado"
                            : (tieneAnalisis ? "● Revisar" : "＋ Causa / observ.")}</button>
                        ${cerrado ? "" : `
                            <button
                                type="button"
                                class="count-delete-button compact"
                                data-delete-item="${linea.id}"
                                data-delete-label="${escapeHtml(linea.codigo)}"
                            >Quitar</button>
                        `}
                    </div>
                </td>
            </tr>
            <tr id="item-analysis-${linea.id}" class="item-analysis-row hidden">
                <td colspan="12">
                    <div class="item-analysis-fields">
                        <label>
                            Posible causa de la diferencia
                            <select
                                class="cause-select"
                                data-item-id="${linea.id}"
                                ${cerrado ? "disabled" : ""}
                            >${opcionesCausasDiferencia(
                                linea.causa_diferencia_codigo
                            )}</select>
                        </label>
                        <label>
                            Observación del medio
                            <textarea
                                class="item-observation"
                                data-item-id="${linea.id}"
                                maxlength="1000"
                                rows="2"
                                ${cerrado ? "disabled" : ""}
                            >${escapeHtml(linea.observaciones || "")}</textarea>
                        </label>
                        ${ajusteSistemaHtml(linea, cerrado)}
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function actualizarConteoMediosVisual(event) {
    const itemId = event.target.dataset.itemId;
    const inputs = $$(`.media-count-input[data-item-id="${itemId}"]`);
    const completos = inputs.every((input) => input.value !== "");
    const valores = Object.fromEntries(inputs.map((input) => [
        input.dataset.mediaKind,
        input.value === "" ? null : Number(input.value),
    ]));
    const total = completos
        ? valores.vacios + valores.llenos + valores.rotos
        : null;
    const utilizables = valores.vacios;
    const totalInput = $(
        `.media-total-input[data-item-id="${itemId}"]`
    );
    totalInput.value = total === null ? "" : String(total);
    $(`[data-media-total="${itemId}"] strong`).textContent =
        total === null ? "—" : formatearNumero(total);
    $(`[data-media-usable="${itemId}"]`).textContent =
        utilizables === null ? "—" : formatearNumero(utilizables);
    actualizarDiferenciaVisual({ target: totalInput });

    const totales = $$(".media-total-input");
    const contados = totales.filter((input) => input.value !== "").length;
    $("#detalle-progreso").textContent = `${contados} / ${totales.length}`;
    $("#btn-cerrar").disabled = (
        state.inventarioSeleccionado.estado === "Cerrado"
        || contados !== totales.length
    );
}

function nombreCausaDiferencia(codigo) {
    if (!codigo) return "";
    return state.causasDiferencia.find((causa) => causa.codigo === codigo)?.nombre || codigo;
}

function gruposComparablesInventario(inventario) {
    return agruparItemsPorPieza(
        inventario.items,
        inventario.categoria === "PIEZAS",
    ).map((grupo) => ({
        ...grupo,
        metricas: metricasGrupoPieza(grupo),
        causas: [...new Set(grupo.items
            .map((item) => item.causa_diferencia_codigo)
            .filter(Boolean))],
        comentarios: [...new Set(grupo.items
            .map((item) => (item.observaciones || "").trim())
            .filter(Boolean))],
    }));
}

function inventariosHistoricosComparables(actual) {
    const fechaActual = String(actual.fecha || actual.cerrado_en || "");
    return state.inventarios.filter((inventario) => (
        inventario.id !== actual.id
        && inventario.cliente === actual.cliente
        && inventario.categoria === actual.categoria
        && inventario.modalidad_conteo === actual.modalidad_conteo
        && String(inventario.fecha || inventario.cerrado_en || "") <= fechaActual
    )).sort((a, b) => (
        String(b.fecha || b.cerrado_en || "").localeCompare(String(a.fecha || a.cerrado_en || ""))
        || Number(b.id) - Number(a.id)
    ));
}

function historialPieza(actual, codigo) {
    const registros = [];
    for (const inventario of inventariosHistoricosComparables(actual)) {
        const grupo = gruposComparablesInventario(inventario).find(
            (candidate) => candidate.codigo === codigo
        );
        if (!grupo || grupo.metricas.fisico === null) continue;
        registros.push({ inventario, metricas: grupo.metricas });
        if (registros.length === 3) break;
    }
    return registros;
}

function historialPiezaHtml(actual, codigo) {
    const registros = historialPieza(actual, codigo);
    if (!registros.length) {
        return '<span class="difference-history-empty">Sin conteos anteriores comparables</span>';
    }
    return registros.map(({ inventario, metricas }) => `
        <div class="difference-history-point">
            <small>${formatearFecha(inventario.fecha)}</small>
            <strong>${numeroConSigno(metricas.diferencia)}</strong>
            <span>${numeroPorcentajeConSigno(metricas.desvio_porcentaje)}</span>
        </div>
    `).join("");
}

function diagnosticoDiferencia(actual, grupo) {
    const historial = historialPieza(actual, grupo.codigo);
    const actualPct = grupo.metricas.desvio_porcentaje;
    if (grupo.metricas.fisico === null || actualPct === null) {
        return { clase: "unknown", etiqueta: "Pendiente de contar", detalle: "El historial queda disponible como referencia antes de cargar el físico." };
    }
    if (grupo.metricas.dentro_tolerancia === true) {
        return { clase: "ok", etiqueta: "Dentro de tolerancia", detalle: "El conteo actual no presenta una diferencia relevante." };
    }
    if (!historial.length) {
        return { clase: "unknown", etiqueta: "Sin antecedentes", detalle: "Conviene recontar antes de confirmar la causa." };
    }
    const ultimoPct = historial[0].metricas.desvio_porcentaje;
    if (Math.sign(actualPct) !== Math.sign(ultimoPct)) {
        return { clase: "review", etiqueta: "Cambió de signo", detalle: "Puede haber un ajuste, movimiento o error de conteo." };
    }
    const tolerancia = Number(state.configuracionIndicadores.tolerancia_pct ?? 5);
    const repetidos = historial.filter(({ metricas }) => (
        metricas.dentro_tolerancia === false
        && Math.sign(metricas.desvio_porcentaje) === Math.sign(actualPct)
    ));
    if (repetidos.length >= 2) {
        const promedio = repetidos.reduce(
            (suma, registro) => suma + registro.metricas.desvio_porcentaje,
            0
        ) / repetidos.length;
        if (Math.abs(actualPct - promedio) <= Math.max(tolerancia, Math.abs(promedio) * .45)) {
            return { clase: "persistent", etiqueta: "Diferencia repetida", detalle: "El patrón se sostiene; probablemente no sea un error aislado." };
        }
    }
    if (
        historial[0].metricas.dentro_tolerancia === true
        || Math.abs(actualPct) > Math.max(tolerancia * 2, Math.abs(ultimoPct) * 2)
    ) {
        return { clase: "recount", etiqueta: "Prioridad de reconteo", detalle: "Es nueva o se aleja mucho del último resultado." };
    }
    return { clase: "review", etiqueta: "Revisar evolución", detalle: "Hay antecedentes, pero el patrón todavía no es concluyente." };
}

function alternarFocoDiferencias() {
    state.focoDiferenciasAbierto = !state.focoDiferenciasAbierto;
    const content = $("#difference-focus-content");
    const button = $("#btn-toggle-difference-focus");
    content.classList.toggle("hidden", !state.focoDiferenciasAbierto);
    button.setAttribute("aria-expanded", String(state.focoDiferenciasAbierto));
    button.innerHTML = state.focoDiferenciasAbierto
        ? 'Ocultar análisis <span>⌃</span>'
        : 'Analizar diferencias <span>⌄</span>';
}

function enfocarPiezaDesdeDiferencias(codigo) {
    if (state.vistaConteo !== "PIEZA") {
        state.vistaConteo = "PIEZA";
        try { window.localStorage.setItem("vistaConteo", "PIEZA"); } catch (_error) {}
        renderDetalle();
    }
    window.requestAnimationFrame(() => {
        const fila = $$(".piece-summary-row").find(
            (candidate) => candidate.dataset.pieceCode === codigo
        );
        if (!fila) return;
        fila.scrollIntoView({ behavior: "smooth", block: "center" });
        fila.classList.add("difference-focus-highlight");
        window.setTimeout(() => fila.classList.remove("difference-focus-highlight"), 1800);
    });
}

function renderDifferenceFocus(inventario) {
    const panel = $("#difference-focus-panel");
    if (!panel) return;
    const grupos = gruposComparablesInventario(inventario);
    const conDiferencia = grupos.filter((grupo) => (
        grupo.metricas.fisico !== null && grupo.metricas.dentro_tolerancia === false
    )).sort((a, b) => (
        Math.abs(b.metricas.diferencia) - Math.abs(a.metricas.diferencia)
        || Math.abs(b.metricas.desvio_porcentaje) - Math.abs(a.metricas.desvio_porcentaje)
    ));
    panel.classList.toggle("hidden", conDiferencia.length === 0);
    if (!conDiferencia.length) return;

    const principales = conDiferencia.slice(0, 8);
    $("#difference-focus-count").textContent = `${conDiferencia.length} fuera de tolerancia`;
    $("#difference-focus-list").innerHTML = principales.map((grupo, indice) => {
        const metricas = grupo.metricas;
        const causas = grupo.causas.map(nombreCausaDiferencia).join(" · ");
        const comentario = grupo.comentarios.join(" · ");
        const diagnostico = diagnosticoDiferencia(inventario, grupo);
        return `<article class="difference-focus-item">
            <div class="difference-focus-rank">${indice + 1}</div>
            <div class="difference-focus-identity">
                <button type="button" data-focus-difference-code="${escapeHtml(grupo.codigo)}">${escapeHtml(grupo.codigo)}</button>
                <span>${escapeHtml(grupo.descripcion || "Sin descripción")}</span>
                <p><strong>${escapeHtml(causas || "Causa pendiente")}</strong>${comentario ? ` · ${escapeHtml(comentario)}` : ""}</p>
                <div class="difference-diagnosis ${diagnostico.clase}" title="${escapeHtml(diagnostico.detalle)}">
                    <strong>${escapeHtml(diagnostico.etiqueta)}</strong>
                    <span>${escapeHtml(diagnostico.detalle)}</span>
                </div>
            </div>
            <div class="difference-focus-numbers">
                <span><small>Sistema</small><strong>${formatearNumero(metricas.sistema)}</strong></span>
                <span><small>Físico</small><strong>${formatearNumero(metricas.fisico)}</strong></span>
                <span class="difference-focus-loss"><small>Diferencia</small><strong>${numeroConSigno(metricas.diferencia)}</strong></span>
                <span class="difference-focus-loss"><small>Desvío</small><strong>${numeroPorcentajeConSigno(metricas.desvio_porcentaje)}</strong></span>
            </div>
            <div class="difference-focus-history">
                <label>Últimos conteos <small>Diferencia · desvío</small></label>
                <div>${historialPiezaHtml(inventario, grupo.codigo)}</div>
            </div>
        </article>`;
    }).join("");
    $$("[data-focus-difference-code]").forEach((button) => button.addEventListener(
        "click", () => enfocarPiezaDesdeDiferencias(button.dataset.focusDifferenceCode)
    ));

    const frecuencias = new Map();
    conDiferencia.forEach((grupo) => grupo.causas.forEach((codigo) => (
        frecuencias.set(codigo, (frecuencias.get(codigo) || 0) + 1)
    )));
    const causas = [...frecuencias.entries()].sort((a, b) => b[1] - a[1]);
    const maximo = causas[0]?.[1] || 1;
    $("#difference-cause-list").innerHTML = causas.length ? causas.slice(0, 6).map(([codigo, cantidad]) => `
        <div class="difference-cause-row">
            <div><strong>${escapeHtml(nombreCausaDiferencia(codigo))}</strong><span>${cantidad}</span></div>
            <i><b style="width:${Math.max(8, cantidad / maximo * 100)}%"></b></i>
        </div>
    `).join("") : '<p class="difference-cause-empty">Todavía no hay causas asignadas. El panel no considera “Sin causa” como una causa.</p>';
    $("#difference-focus-content").classList.toggle("hidden", !state.focoDiferenciasAbierto);
    const toggle = $("#btn-toggle-difference-focus");
    toggle.setAttribute("aria-expanded", String(state.focoDiferenciasAbierto));
    toggle.innerHTML = state.focoDiferenciasAbierto
        ? 'Ocultar análisis <span>⌃</span>'
        : 'Analizar diferencias <span>⌄</span>';
}

function renderDetalle() {
    const item = state.inventarioSeleccionado;
    if (!item) return;
    const contados = item.items.filter((x) => x.conteo_fisico !== null).length;
    const diferencias = item.items.filter((x) => x.diferencia !== null && x.diferencia !== 0).length;
    const cerrado = item.estado === "Cerrado";

    $("#detalle-codigo").textContent = item.codigo;
    $("#detalle-estado").outerHTML = `<span id="detalle-estado">${statusHtml(item.estado)}</span>`;
    const fechasDetalle = [`Realizado ${formatearFecha(item.fecha)}`];
    if (item.fecha_programada) {
        fechasDetalle.unshift(
            `Programado ${formatearFecha(item.fecha_programada)}`
        );
    }
    if (item.cerrado_en) {
        fechasDetalle.push(`Cerrado ${formatearFecha(item.cerrado_en.split("T")[0])}`);
    }
    fechasDetalle.push(
        `Cierre ${formatearMesCierre(item.mes_cierre || item.fecha)}`
    );
    $("#detalle-subtitulo").textContent =
        `${item.cliente} · ${ambitoInventarioLabel(item.ambito)} · `
        + `${fechasDetalle.join(" · ")} · Responsable: ${item.responsable}`
        + (item.colaboradores
            ? ` · Colaboradores: ${item.colaboradores}`
            : "");
    $("#print-subtitulo").textContent = `${item.codigo} · ${item.cliente} · ${formatearFecha(item.fecha)}`;
    $("#detalle-progreso").textContent = `${contados} / ${item.items.length}`;
    $("#detalle-diferencias").textContent = diferencias;
    $("#detalle-diferencias").classList.toggle("warning", diferencias > 0);
    $("#detalle-stock").textContent = formatearNumero(item.items.reduce((suma, x) => suma + x.stock_sistema, 0));
    $("#detalle-stock-actualizado").textContent = item.stock_actualizado_en
        ? `${origenStockLabel(item.stock_origen)} · ${formatearFechaHora(item.stock_actualizado_en)}`
        : "Sin actualización registrada";
    actualizarResumenConfiabilidad({
        correctos: item.items_ok,
        evaluados: item.items_evaluados,
        total: item.items_evaluables,
        porcentaje: item.confiabilidad,
    });
    renderDifferenceFocus(item);
    $("#btn-guardar-conteo").disabled = cerrado;
    $("#btn-agregar-articulo").disabled = cerrado;
    $("#btn-actualizar-stock").disabled = cerrado;
    $("#btn-conteo-movil").disabled = cerrado;
    $("#btn-cerrar").disabled = cerrado || contados !== item.items.length;
    $("#btn-cerrar").classList.toggle("hidden", cerrado);
    $("#btn-reabrir").classList.toggle("hidden", !cerrado);
    $("#btn-iniciar-reconteo").classList.toggle("hidden", !cerrado);
    renderReconteos(item);
    $("#detalle-ambito").value = item.ambito || "INTERNO";
    $("#detalle-mes-cierre").value = (
        item.mes_cierre?.slice(0, 7) || item.fecha.slice(0, 7)
    );
    $("#detalle-comentario").value = item.observaciones || "";
    $("#inventory-data-summary").textContent =
        `${ambitoInventarioLabel(item.ambito)} · `
        + `Cierre ${formatearMesCierre(item.mes_cierre || item.fecha)} · `
        + (item.observaciones?.trim() || "Sin comentario");
    renderEstadoDatosInventario();
    $("#inventory-meta-grid").classList.toggle(
        "with-remittances",
        item.controla_remitos
    );
    $("#remitos-control").classList.toggle("hidden", !item.controla_remitos);
    $("#remito-ingreso").value = item.ultimo_remito_ingreso || "";
    $("#remito-egreso").value = item.ultimo_remito_egreso || "";
    $("#remito-ingreso").disabled = cerrado;
    $("#remito-egreso").disabled = cerrado;
    $("#remittance-summary").textContent = resumenControlRemitos();
    renderEstadoControlRemitos();

    $("#tabla-conteo").innerHTML = item.items.map((linea, indice) => {
        const tieneAnalisis = Boolean(
            linea.causa_diferencia_codigo
            || linea.ajustado_sistema
            || (linea.observaciones || "").trim()
        );
        return `
        <tr class="count-main-row">
            <td>${indice + 1}</td>
            <td class="${linea.etapa === "MATERIAL"
                ? ""
                : `structure-identity role-${String(
                    linea.tipo_estructura || "INDEPENDIENTE"
                ).toLowerCase()}`}">
                <strong>${escapeHtml(linea.codigo)}</strong>
                <small class="secondary-code">${escapeHtml(linea.codigo_cliente || "")}</small>
                ${linea.etapa === "MATERIAL"
                    ? ""
                    : tipoEstructuraHtml(linea.tipo_estructura)}
                ${item.categoria === "CICLICO" ? `
                    <small class="secondary-code">
                        Nivel ${linea.nivel} ·
                        ${linea.codigo_padre
                            ? `Padre ${escapeHtml(linea.codigo_padre)} · `
                            : ""}
                        Uso ${formatearNumero(linea.uso)}
                    </small>
                ` : ""}
            </td>
            <td>${escapeHtml(linea.descripcion)}</td>
            <td><span class="location">${escapeHtml(linea.codigo_material || "—")}</span></td>
            <td>${etapaLabel(linea.etapa)}</td>
            <td>
                ${linea.operacion ? `<strong>${escapeHtml(linea.operacion)}</strong>` : ""}
                <small class="secondary-code">${escapeHtml(linea.titulo_operacion || "")}</small>
            </td>
            <td>${escapeHtml(linea.proveedor || "—")}</td>
            <td class="system-column">
                ${linea.stock_pendiente ? `<span class="pending-stock">Pendiente de integrar</span>` : formatearNumero(linea.stock_sistema)}
            </td>
            <td>
                <div class="count-input-detail compact">
                    <input
                        class="conteo-input ${linea.diferencia ? "has-difference" : ""}"
                        data-item-id="${linea.id}"
                        data-stock="${linea.stock_sistema}"
                        data-stock-pendiente="${linea.stock_pendiente}"
                        type="number"
                        min="0"
                        step="any"
                        value="${linea.conteo_fisico ?? ""}"
                        ${cerrado ? "disabled" : ""}
                    >
                    <button type="button" data-count-records="${linea.id}">Detalle</button>
                </div>
            </td>
            <td class="system-column difference ${linea.diferencia ? "warning" : ""}" data-diferencia-id="${linea.id}">
                ${linea.diferencia === null ? "—" : numeroConSigno(linea.diferencia)}
            </td>
            <td class="system-column percentage-cell" data-porcentaje-id="${linea.id}">
                ${porcentajeConteoHtml(linea)}
            </td>
            <td class="count-row-actions">
                <button
                    type="button"
                    class="item-analysis-toggle ${tieneAnalisis ? "completed" : ""}"
                    data-item-id="${linea.id}"
                    aria-expanded="false"
                    aria-controls="item-analysis-${linea.id}"
                >
                    ${linea.ajustado_sistema
                        ? "✓ Ajustado"
                        : (tieneAnalisis ? "● Revisar" : "＋ Analizar")}
                </button>
                ${cerrado ? "" : `
                    <button
                        type="button"
                        class="count-delete-button compact"
                        data-delete-item="${linea.id}"
                        data-delete-label="${escapeHtml(
                            `${linea.codigo} · ${etapaTexto(linea.etapa)}`
                        )}"
                        title="Quitar este renglón del inventario"
                    >Quitar fila</button>
                `}
            </td>
        </tr>
        <tr id="item-analysis-${linea.id}" class="item-analysis-row hidden">
            <td colspan="12">
                <div class="item-analysis-fields">
                    <label>
                        Posible causa de la diferencia
                        <select
                            class="cause-select"
                            data-item-id="${linea.id}"
                            ${cerrado ? "disabled" : ""}
                        >
                            ${opcionesCausasDiferencia(
                                linea.causa_diferencia_codigo
                            )}
                        </select>
                    </label>
                    <label>
                        Observación del renglón
                        <textarea
                            class="item-observation"
                            data-item-id="${linea.id}"
                            maxlength="1000"
                            rows="2"
                            placeholder="Detalle del recuento, ubicación encontrada o acción pendiente"
                            ${cerrado ? "disabled" : ""}
                        >${escapeHtml(linea.observaciones || "")}</textarea>
                    </label>
                    ${ajusteSistemaHtml(linea, cerrado)}
                </div>
            </td>
        </tr>
    `;
    }).join("");

    const esMedios = item.modalidad_conteo === "MEDIOS";
    const permiteVistaPorPieza = item.categoria === "PIEZAS" && !esMedios;
    const vistaPorPieza =
        permiteVistaPorPieza && state.vistaConteo === "PIEZA";
    $("#count-view-tabs").classList.toggle("hidden", !permiteVistaPorPieza);
    $$("#count-view-tabs button").forEach((button) => {
        button.classList.toggle(
            "active",
            button.dataset.countView === state.vistaConteo
        );
    });
    $("#count-detail-wrap").classList.toggle(
        "hidden",
        vistaPorPieza || esMedios
    );
    $("#count-piece-wrap").classList.toggle(
        "hidden",
        !vistaPorPieza || esMedios
    );
    $("#count-media-wrap").classList.toggle("hidden", !esMedios);
    if (esMedios) {
        $("#tabla-conteo-medios").innerHTML =
            renderConteoMedios(item, cerrado);
        $("#tabla-conteo").innerHTML = "";
        $("#tabla-conteo-piezas").innerHTML = "";
    } else if (vistaPorPieza) {
        $("#tabla-conteo-piezas").innerHTML =
            renderConteoPorPieza(item, cerrado);
        $("#tabla-conteo").innerHTML = "";
    } else {
        $("#tabla-conteo-piezas").innerHTML = "";
        $("#tabla-conteo-medios").innerHTML = "";
    }

    renderTablaImpresion(item);
    $$(".conteo-input").forEach((input) => input.addEventListener("input", (event) => {
        actualizarDiferenciaVisual(event);
        programarAutoguardado("conteo");
    }));
    $$('[data-count-records]').forEach((button) => {
        button.addEventListener("click", () => abrirDetalleRegistrosConteo(
            Number(button.dataset.countRecords)
        ));
    });
    $$('[data-count-material]').forEach((button) => {
        button.addEventListener("click", () => abrirDetalleLotesMaterial(
            button.dataset.countMaterial.split(",").map(Number),
        ));
    });
    $$('[data-add-material-lot]').forEach((button) => {
        button.addEventListener("click", () => agregarLoteMaterialDesdeConteo(button));
    });
    $$('[data-delete-material-lot]').forEach((button) => {
        button.addEventListener("click", () => eliminarLoteMaterialDesdeConteo(button));
    });
    $$(".media-count-input").forEach((input) => {
        input.addEventListener("input", (event) => {
            actualizarConteoMediosVisual(event);
            programarAutoguardado("conteo");
        });
    });
    $$(".item-analysis-toggle").forEach((boton) => {
        boton.addEventListener("click", () => {
            const fila = $(`#item-analysis-${boton.dataset.itemId}`);
            const abierta = !fila.classList.toggle("hidden");
            boton.setAttribute("aria-expanded", String(abierta));
            if (abierta && !cerrado) {
                fila.querySelector(".cause-select")?.focus();
            }
        });
    });
    $$(".piece-analysis-toggle").forEach((button) => {
        button.addEventListener("click", () => {
            const row = $(`#piece-analysis-${button.dataset.pieceAnalysis}`);
            const abierta = !row.classList.toggle("hidden");
            button.setAttribute("aria-expanded", String(abierta));
            const slot = row.querySelector("[data-piece-history-slot]");
            if (abierta && slot && slot.dataset.loaded !== "true") {
                const group = agruparItemsPorPieza(
                    item.items,
                    item.categoria === "PIEZAS",
                ).find((candidate) => (
                    candidate.items.some((linea) => linea.id === Number(button.dataset.pieceAnalysis))
                ));
                if (group) {
                    slot.innerHTML = historialAnalisisPiezaHtml(
                        item,
                        group,
                        metricasGrupoPieza(group)
                    );
                    slot.dataset.loaded = "true";
                }
            }
        });
    });
    $$(".system-adjust-checkbox").forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            checkbox.closest(".system-adjust-control")?.classList.toggle(
                "checked",
                checkbox.checked
            );
            programarAutoguardado("conteo", 100);
        });
    });
    $$(".cause-select").forEach((input) => {
        input.addEventListener("change", () => programarAutoguardado("conteo", 100));
    });
    $$(".item-observation").forEach((input) => {
        input.addEventListener("input", () => programarAutoguardado("conteo"));
    });
    $$("[data-delete-item]").forEach((button) => {
        button.addEventListener("click", () => eliminarFilasInventario(
            [Number(button.dataset.deleteItem)],
            button.dataset.deleteLabel
        ));
    });
    $$("[data-delete-piece]").forEach((button) => {
        button.addEventListener("click", () => eliminarFilasInventario(
            button.dataset.deletePiece.split(",").map(Number),
            `la pieza ${button.dataset.deleteLabel}`
        ));
    });
}

function abrirModalReconteo() {
    const inventario = state.inventarioSeleccionado;
    if (!inventario || inventario.estado !== "Cerrado") return;
    $("#reconteo-responsable").value = inventario.responsable || "";
    $("#reconteo-observacion").value = "";
    $("#reconteo-seleccion").value = inventario.items.some((x) => x.dentro_tolerancia === false)
        ? "FUERA_TOLERANCIA" : "COMPLETO";
    $("#reconteo-stock").value = "ORIGINAL";
    renderSeleccionReconteo();
    $("#modal-reconteo").classList.remove("hidden");
}

function renderSeleccionReconteo() {
    const inventario = state.inventarioSeleccionado;
    if (!inventario) return;
    const modo = $("#reconteo-seleccion").value;
    const piezas = new Map();
    inventario.items.forEach((item) => {
        if (!piezas.has(item.codigo)) piezas.set(item.codigo, []);
        piezas.get(item.codigo).push(item);
    });
    $("#reconteo-items-seleccion").innerHTML = [...piezas.entries()].map(([codigo, items]) => {
        const marcado = modo === "COMPLETO"
            || (modo === "FUERA_TOLERANCIA" && items.some((x) => x.dentro_tolerancia === false));
        return `<label><input type="checkbox" data-recount-original-ids="${items.map((x) => x.id).join(",")}" ${marcado ? "checked" : ""} ${modo === "MANUAL" ? "" : "disabled"}>
            <span><strong>${escapeHtml(codigo)}</strong><small>${escapeHtml(items[0].descripcion || "")} · ${items.length} renglón(es)</small></span></label>`;
    }).join("");
}

async function crearReconteo(event) {
    event.preventDefault();
    const inventario = state.inventarioSeleccionado;
    const ids = $$('[data-recount-original-ids]').filter((x) => x.checked)
        .flatMap((x) => x.dataset.recountOriginalIds.split(",").map(Number));
    if (!ids.length) return toast("Seleccioná al menos una pieza", true);
    const seleccion = $("#reconteo-seleccion").value;
    try {
        const nuevo = await api(`/api/inventarios/${inventario.id}/reconteos`, {
            method: "POST",
            body: JSON.stringify({
                tipo: seleccion === "COMPLETO" ? "COMPLETO" : "PARCIAL",
                stock_referencia: $("#reconteo-stock").value,
                item_ids: ids,
                responsable: $("#reconteo-responsable").value.trim(),
                observaciones: $("#reconteo-observacion").value.trim(),
            }),
        });
        cerrarModales();
        await cargarInicio();
        abrirDetalle(nuevo.id);
        toast(`Reconteo creado como ${nuevo.codigo}`);
    } catch (error) { toast(error.message, true); }
}

function renderReconteos(inventario) {
    const panel = $("#reconteos-panel");
    const origen = inventario.relacion_reconteo;
    const hijos = inventario.reconteos_vinculados || [];
    panel.classList.toggle("hidden", !origen && !hijos.length);
    if (!origen && !hijos.length) return;
    const tarjetas = [];
    if (origen) {
        const original = state.inventarios.find((x) => x.id === origen.inventario_origen_id);
        tarjetas.push(`<button type="button" class="recount-link" data-open-inventory="${origen.inventario_origen_id}"><strong>Reconteo ${origen.numero_reconteo} de ${escapeHtml(original?.codigo || "inventario original")}</strong><small>${origen.tipo} · Stock ${origen.stock_referencia.toLowerCase()}</small></button>`);
    }
    hijos.forEach((relacion) => {
        const hijo = state.inventarios.find((x) => x.id === relacion.inventario_reconteo_id);
        if (!hijo) return;
        tarjetas.push(`<button type="button" class="recount-link" data-open-inventory="${hijo.id}"><strong>Reconteo ${relacion.numero_reconteo} · ${escapeHtml(hijo.codigo)}</strong><small>${relacion.tipo} · Stock ${relacion.stock_referencia.toLowerCase()} · ${escapeHtml(hijo.estado)}</small></button>`);
    });
    $("#reconteos-contenido").innerHTML = tarjetas.join("");
    $$('[data-open-inventory]').forEach((boton) => boton.addEventListener("click", () => abrirDetalle(Number(boton.dataset.openInventory))));
}

async function eliminarFilasInventario(itemIds, etiqueta) {
    const inventario = state.inventarioSeleccionado;
    if (!inventario || !itemIds.length) return;
    if (!confirm(
        `¿Quitar ${etiqueta} de ${inventario.codigo}?\n\n`
        + "Esta acción elimina también el conteo y el análisis de esos renglones."
    )) return;
    try {
        const actualizado = await api(
            `/api/inventarios/${inventario.id}/eliminar-filas`,
            {
                method: "POST",
                body: JSON.stringify({ item_ids: itemIds }),
            }
        );
        const indice = state.inventarios.findIndex((item) => item.id === actualizado.id);
        if (indice >= 0) state.inventarios[indice] = actualizado;
        if (state.inventarioSeleccionado?.id === actualizado.id) {
            state.inventarioSeleccionado = actualizado;
        }
        renderTodo();
        renderDetalle();
        toast("Renglón eliminado del inventario");
    } catch (error) {
        toast(error.message, true);
    }
}

function opcionesCausasDiferencia(seleccionada) {
    const codigoSeleccionado = seleccionada || "";
    const causas = [...state.causasDiferencia];
    if (
        codigoSeleccionado
        && !causas.some((causa) => causa.codigo === codigoSeleccionado)
    ) {
        causas.push({
            codigo: codigoSeleccionado,
            nombre: codigoSeleccionado,
            descripcion: "Causa histórica no activa",
        });
    }
    return [
        '<option value="">Sin causa</option>',
        ...causas.map((causa) => `
            <option
                value="${escapeHtml(causa.codigo)}"
                title="${escapeHtml(causa.descripcion || "")}"
                ${causa.codigo === codigoSeleccionado ? "selected" : ""}
            >
                ${escapeHtml(causa.nombre)}
            </option>
        `),
    ].join("");
}

function renderTablaImpresion(inventario) {
    const piezas = new Map();

    inventario.items
        .filter((linea) => Boolean((linea.codigo_material || "").trim()))
        .forEach((linea) => {
            if (!piezas.has(linea.codigo)) {
                piezas.set(linea.codigo, {
                    codigo: linea.codigo,
                    codigo_cliente: linea.codigo_cliente || "",
                    descripcion: linea.descripcion || "",
                    codigo_material: linea.codigo_material || "",
                    operaciones: [],
                });
            }

            if (
                ["OPERACION", "PROCESO_GLOBAL"].includes(linea.etapa)
                && linea.titulo_operacion
            ) {
                piezas.get(linea.codigo).operaciones.push(linea.titulo_operacion);
            }
        });

    $("#tabla-conteo-impresion").innerHTML = [...piezas.values()].map((pieza) => {
        const operaciones = [...new Set(pieza.operaciones)];
        const detalleProceso = operaciones.length
            ? operaciones.join(" · ")
            : "Proceso";

        return `
            <tr>
                <td class="print-code">${escapeHtml(pieza.codigo)}</td>
                <td></td>
                <td class="print-client">${escapeHtml(pieza.codigo_cliente || "—")}</td>
                <td class="print-description">${escapeHtml(pieza.descripcion)}</td>
                <td class="print-material">${escapeHtml(pieza.codigo_material)}</td>
                <td class="write-cell"></td>
                <td class="write-cell"></td>
                <td class="write-cell process-cell"><small>${escapeHtml(detalleProceso)}</small></td>
                <td class="write-cell"></td>
                <td class="write-cell"></td>
            </tr>
        `;
    }).join("");
}

function actualizarDiferenciaVisual(event) {
    const input = event.target;
    const celda = document.querySelector(`[data-diferencia-id="${input.dataset.itemId}"]`);
    const celdaPorcentaje = document.querySelector(`[data-porcentaje-id="${input.dataset.itemId}"]`);
    if (input.value === "" || input.dataset.stockPendiente === "true") {
        if (celda) {
            celda.textContent = "—";
            celda.classList.remove("warning");
        }
        if (celdaPorcentaje) celdaPorcentaje.innerHTML = "—";
        actualizarControlAjuste(input.dataset.itemId, null);
        input.classList.remove("has-difference");
        if (input.dataset.groupCode) {
            actualizarResumenGrupoVisual(input.dataset.groupCode);
        }
        actualizarConfiabilidadVisual();
        return;
    }
    const metricas = calcularMetricasConteo(
        Number(input.value),
        Number(input.dataset.stock)
    );
    const diferencia = metricas.diferencia;
    if (celda) {
        celda.textContent = numeroConSigno(diferencia);
        celda.classList.toggle("warning", diferencia !== 0);
    }
    input.classList.toggle("has-difference", diferencia !== 0);
    if (celdaPorcentaje) {
        celdaPorcentaje.innerHTML = porcentajeConteoHtml(metricas);
    }
    actualizarControlAjuste(
        input.dataset.itemId,
        metricas.dentro_tolerancia
    );
    if (input.dataset.groupCode) {
        actualizarResumenGrupoVisual(input.dataset.groupCode);
    }
    actualizarConfiabilidadVisual();
}

function actualizarResumenGrupoVisual(codigo) {
    const inputs = $$(".conteo-input").filter(
        (input) => input.dataset.groupCode === codigo
    );
    const comparables = inputs;
    const proceso = comparables.filter(
        (input) => input.dataset.stage !== "MATERIAL"
            && input.dataset.stage !== "TERMINADO"
    );
    const terminadas = comparables.filter(
        (input) => input.dataset.stage === "TERMINADO"
    );
    const entradasMaterial = comparables.filter(
        (input) => input.dataset.stage === "MATERIAL"
    );
    const entradasProductivas = comparables.filter(
        (input) => input.dataset.stage !== "MATERIAL"
    );
    const fisicosMaterial = new Map();
    entradasMaterial.forEach((input) => {
        const clave = `${input.dataset.materialCode || ""}::${input.dataset.lot || ""}`;
        if (!fisicosMaterial.has(clave)) fisicosMaterial.set(clave, []);
        if (input.value !== "") fisicosMaterial.get(clave).push(Number(input.value));
    });
    const materialCompleto = [...fisicosMaterial.values()].every(
        (valores) => valores.length > 0,
    );
    const completo = comparables.length > 0
        && materialCompleto
        && entradasProductivas.every((input) => input.value !== "");
    const materiales = new Map();
    const sistemaProductivo = comparables.reduce((suma, input) => {
        if (input.dataset.stage !== "MATERIAL") {
            return suma + Number(input.dataset.stock);
        }
        const clave = `${input.dataset.materialCode || ""}::${input.dataset.lot || ""}`;
        materiales.set(
            clave,
            Math.max(materiales.get(clave) || 0, Number(input.dataset.stock || 0)),
        );
        return suma;
    }, 0);
    const sistema = sistemaProductivo + [...materiales.values()].reduce(
        (suma, valor) => suma + valor,
        0,
    );
    const fisico = completo
        ? entradasProductivas.reduce(
            (suma, input) => suma + Number(input.value),
            0,
        ) + [...fisicosMaterial.values()].reduce(
            (suma, valores) => suma + Math.max(...valores),
            0,
        )
        : null;
    const diferencia = fisico === null ? null : fisico - sistema;
    const diferenciaProceso = proceso.length
        && proceso.every((input) => input.value !== "")
        ? proceso.reduce(
            (suma, input) => (
                suma + Number(input.value) - Number(input.dataset.stock)
            ),
            0
        )
        : null;
    const diferenciaTerminada = terminadas.length
        && terminadas.every((input) => input.value !== "")
        ? terminadas.reduce(
            (suma, input) => (
                suma + Number(input.value) - Number(input.dataset.stock)
            ),
            0
        )
        : null;
    const fila = inputs[0]?.closest(".piece-summary-row");
    if (!fila) return;
    fila.querySelectorAll(".stage-details").forEach((details) => {
        const stageInputs = [...details.querySelectorAll(".conteo-input")];
        const counted = stageInputs.filter((input) => input.value !== "");
        details.querySelector("summary strong").textContent =
            counted.length === stageInputs.length
                ? `Físico ${formatearNumero(
                    counted.reduce(
                        (suma, input) => suma + Number(input.value),
                        0
                    )
                )}`
                : `${counted.length}/${stageInputs.length} contados`;
    });
    const total = fila.querySelector("[data-group-total]");
    total.querySelector("[data-group-physical]").textContent =
        fisico === null ? "—" : formatearNumero(fisico);
    const diferenciaElement = total.querySelector("[data-group-difference]");
    diferenciaElement.textContent =
        diferencia === null ? "—" : numeroConSigno(diferencia);
    diferenciaElement.classList.toggle(
        "warning",
        diferencia !== null && Math.abs(diferencia) > 1e-9
    );
    const desvioElement = fila.querySelector("[data-group-deviation]");
    if (desvioElement) {
        if (fisico === null) {
            desvioElement.innerHTML =
                '<strong class="pending-deviation">—</strong><small>Pendiente</small>';
        } else {
            const metricasDesvio = calcularMetricasConteo(fisico, sistema);
            desvioElement.innerHTML = `
                <strong class="${metricasDesvio.dentro_tolerancia
                    ? "within-tolerance"
                    : "outside-tolerance"}">
                    ${numeroPorcentajeConSigno(metricasDesvio.desvio_porcentaje)}
                </strong>
                <small>${metricasDesvio.dentro_tolerancia
                    ? "Dentro de tolerancia"
                    : "Fuera de tolerancia"}</small>
            `;
        }
    }

    let texto = "Pendiente de completar";
    let clase = "pending";
    if (!comparables.length) {
        texto = "Sin renglones comparables";
        clase = "neutral";
    } else if (completo && Math.abs(diferencia) < 1e-9) {
        if (
            diferenciaProceso < 0
            && diferenciaTerminada > 0
            && Math.abs(diferenciaProceso + diferenciaTerminada) < 1e-9
        ) {
            texto = "Posible producción sin declarar";
            clase = "shift";
        } else if (
            diferenciaProceso > 0
            && diferenciaTerminada < 0
            && Math.abs(diferenciaProceso + diferenciaTerminada) < 1e-9
        ) {
            texto = "Posible ajuste entre etapas";
            clase = "shift";
        } else {
            texto = "Total general correcto";
            clase = "ok";
        }
    } else if (
        completo
        && calcularMetricasConteo(fisico, sistema).dentro_tolerancia
    ) {
        texto = "Dentro de tolerancia";
        clase = "ok";
    } else if (completo) {
        texto = "Diferencia real de stock";
        clase = "difference";
    }
    const diagnostico = fila.querySelector("[data-group-diagnosis]");
    diagnostico.textContent = texto;
    diagnostico.className = `piece-diagnosis ${clase}`;
}

function calcularMetricasConteo(fisico, teorico) {
    const diferencia = fisico - teorico;
    const tolerancia = Number(
        state.configuracionIndicadores.tolerancia_pct ?? 5
    );
    if (teorico === 0) {
        return {
            diferencia,
            relacion_porcentaje: fisico === 0 ? 100 : 200,
            desvio_porcentaje: fisico === 0 ? 0 : 100,
            dentro_tolerancia: fisico === 0,
        };
    }
    const relacion = fisico * 100 / teorico;
    const desvio = diferencia * 100 / teorico;
    return {
        diferencia,
        relacion_porcentaje: relacion,
        desvio_porcentaje: desvio,
        dentro_tolerancia: Math.abs(desvio) <= tolerancia + 1e-9,
    };
}

function porcentajeConteoHtml(metricas) {
    if (metricas.dentro_tolerancia === null || metricas.dentro_tolerancia === undefined) {
        return "—";
    }
    const clase = metricas.dentro_tolerancia ? "within-tolerance" : "outside-tolerance";
    return `
        <strong class="${clase}">${formatearPorcentaje(metricas.relacion_porcentaje)}</strong>
        <small>Desvío ${numeroPorcentajeConSigno(metricas.desvio_porcentaje)}</small>
    `;
}

function actualizarControlAjuste(itemId, dentroTolerancia) {
    const control = document.querySelector(
        `[data-adjust-control="${itemId}"]`
    );
    if (!control) return;
    const checkbox = control.querySelector(".system-adjust-checkbox");
    const titulo = control.querySelector("strong");
    const detalle = control.querySelector("small");
    const requiereAjuste = dentroTolerancia === false;
    checkbox.disabled = !requiereAjuste;
    if (!requiereAjuste) {
        checkbox.checked = false;
        control.classList.remove("checked");
    }
    control.classList.toggle("not-required", !requiereAjuste);
    titulo.textContent = requiereAjuste
        ? "Ajustado en sistema"
        : "No requiere ajuste";
    detalle.textContent = requiereAjuste
        ? "Corrección todavía no registrada"
        : (
            dentroTolerancia === true
                ? "Dentro de tolerancia: no requiere ajuste"
                : "Se habilita si el conteo queda fuera de tolerancia"
        );
}

function actualizarEtiquetasIndicadores() {
    const tolerancia = formatearNumero(
        state.configuracionIndicadores.tolerancia_pct
    );
    const etiqueta = document.querySelector(
        "#detalle-confiabilidad-etiqueta"
    );
    if (etiqueta) etiqueta.textContent = `Confiabilidad (±${tolerancia}%)`;
    const etiquetaConciliacion = document.querySelector(
        "#conciliacion-confiabilidad-etiqueta"
    );
    if (etiquetaConciliacion) {
        etiquetaConciliacion.textContent = `Dentro de ±${tolerancia}%`;
    }
}

function actualizarConfiabilidadVisual() {
    const inputs = $$(".conteo-input").filter(
        (input) => input.dataset.stockPendiente !== "true"
    );
    const evaluados = inputs.filter((input) => input.value !== "");
    const correctos = evaluados.filter((input) => (
        calcularMetricasConteo(
            Number(input.value),
            Number(input.dataset.stock)
        ).dentro_tolerancia
    )).length;
    const total = inputs.length;
    actualizarResumenConfiabilidad({
        correctos,
        evaluados: evaluados.length,
        total,
        porcentaje: total ? correctos * 100 / total : null,
    });

    const diferencias = evaluados.filter((input) => (
        Number(input.value) - Number(input.dataset.stock) !== 0
    )).length;
    $("#detalle-diferencias").textContent = diferencias;
    $("#detalle-diferencias").classList.toggle("warning", diferencias > 0);
}

function actualizarResumenConfiabilidad({ correctos, evaluados, total, porcentaje }) {
    const valor = $("#detalle-confiabilidad");
    valor.textContent = porcentaje === null ? "—" : formatearPorcentaje(porcentaje);
    valor.className = porcentaje === null ? "" : claseConfiabilidad(porcentaje);
    $("#detalle-confiabilidad-detalle").textContent =
        `${correctos} / ${total} renglones OK`
        + (evaluados < total ? ` · ${evaluados} contados` : "");
}

async function guardarConteo({
    automatico = false, inventarioId = null, payload = null,
} = {}) {
    if (!automatico) {
        window.clearTimeout(autosave.conteo.timer);
        autosave.conteo.timer = null;
        autosave.conteo.dirty = false;
        autosave.conteo.failed = false;
        estadoAutoguardado("conteo", "saving");
    }
    const inventario = state.inventarioSeleccionado;
    const id = inventarioId || inventario?.id;
    if (!id) return;
    try {
        const actualizado = await api(`/api/inventarios/${id}/conteo`, {
            method: "PUT",
            body: JSON.stringify(payload || datosConteoActuales()),
        });
        reemplazarInventario(actualizado);
        if (automatico) {
            // El detalle ya se actualiza mientras se escribe. Redibujar sólo
            // los resúmenes externos evita dejar una confiabilidad anterior
            // visible detrás del detalle sin interrumpir el foco del campo.
            renderMetricas();
            renderInventarios();
        } else {
            renderTodo();
            renderDetalle();
            estadoAutoguardado("conteo", "saved");
            toast("Conteo guardado");
        }
        return actualizado;
    } catch (error) {
        if (!automatico) {
            autosave.conteo.failed = true;
            estadoAutoguardado("conteo", "error");
            toast(error.message, true);
            return null;
        }
        throw error;
    }
}

async function guardarDatosInventario({ automatico = false } = {}) {
    const inventario = state.inventarioSeleccionado;
    if (!inventario) return;
    const boton = $("#btn-guardar-datos");
    if (!automatico) boton.disabled = true;
    try {
        const actualizado = await api(
            `/api/inventarios/${inventario.id}/datos`,
            {
                method: "PUT",
                body: JSON.stringify({
                    ambito: $("#detalle-ambito").value,
                    mes_cierre: `${$("#detalle-mes-cierre").value}-01`,
                    observaciones: $("#detalle-comentario").value.trim(),
                }),
            }
        );
        reemplazarInventario(actualizado);
        if (!automatico) {
            renderTodo();
            renderDetalle();
            toast("Datos del inventario guardados");
        }
        return actualizado;
    } catch (error) {
        if (!automatico) {
            toast(error.message, true);
            return null;
        }
        throw error;
    } finally {
        if (!automatico) boton.disabled = false;
    }
}

function valorConteoMedio(itemId, tipo) {
    const input = document.querySelector(
        `.media-count-input[data-item-id="${itemId}"][data-media-kind="${tipo}"]`
    );
    return !input || input.value === "" ? null : Number(input.value);
}

function conteosEscritos() {
    return $$(".conteo-input").map((input) => ({
        item_id: Number(input.dataset.itemId),
        conteo_fisico: input.value === "" ? null : Number(input.value),
        conteo_vacios: valorConteoMedio(input.dataset.itemId, "vacios"),
        conteo_llenos: valorConteoMedio(input.dataset.itemId, "llenos"),
        conteo_rotos: valorConteoMedio(input.dataset.itemId, "rotos"),
        causa_diferencia_codigo:
            document.querySelector(
                `.cause-select[data-item-id="${input.dataset.itemId}"]`
            )?.value || null,
        ajustado_sistema: Boolean(
            document.querySelector(
                `.system-adjust-checkbox[data-item-id="${input.dataset.itemId}"]`
            )?.checked
        ),
        observaciones:
            document.querySelector(
                `.item-observation[data-item-id="${input.dataset.itemId}"]`
            )?.value.trim() || "",
    }));
}

function datosConteoActuales() {
    return {
        items: conteosEscritos(),
        revision_conteo: state.inventarioSeleccionado.conteo_modificado_en,
        ultimo_remito_ingreso: $("#remito-ingreso").value.trim(),
        ultimo_remito_egreso: $("#remito-egreso").value.trim(),
        ambito: $("#detalle-ambito").value,
        observaciones: $("#detalle-comentario").value.trim(),
    };
}

function abrirModalAgregarArticulo() {
    const inventario = state.inventarioSeleccionado;
    if (!inventario || inventario.estado === "Cerrado") return;
    const selector = $("#agregar-tipo-articulo");
    if (inventario.categoria === "MATERIA_PRIMA") {
        selector.value = "MATERIA_PRIMA";
        selector.disabled = true;
    } else if (inventario.categoria === "PIEZAS") {
        selector.value = "PIEZA";
        selector.disabled = true;
    } else {
        selector.value = "PIEZA";
        selector.disabled = false;
    }
    $("#agregar-codigo-articulo").value = "";
    $("#agregar-articulo-options").innerHTML = "";
    $("#agregar-tipo-conteo").value = "GLOBAL";
    $("#agregar-contar-material").checked = true;
    actualizarOpcionesAgregarArticulo();
    abrirModal("#modal-agregar-articulo");
    setTimeout(() => $("#agregar-codigo-articulo").focus(), 0);
}

function actualizarOpcionesAgregarArticulo() {
    const inventario = state.inventarioSeleccionado;
    const esMateriaPrima =
        $("#agregar-tipo-articulo").value === "MATERIA_PRIMA";
    const esMedios = inventario?.modalidad_conteo === "MEDIOS";
    $("#agregar-tipo-conteo-wrap").classList.toggle(
        "hidden",
        esMateriaPrima || esMedios
    );
    $("#agregar-contar-material-wrap").classList.toggle(
        "hidden",
        esMateriaPrima || esMedios
    );
    $("#agregar-codigo-articulo").value = "";
    $("#agregar-articulo-options").innerHTML = "";
}

function programarSugerenciasAgregarArticulo() {
    window.clearTimeout(addArticleAutocompleteState.timer);
    const termino = $("#agregar-codigo-articulo").value.trim();
    if (termino.length < 2) {
        $("#agregar-articulo-options").innerHTML = "";
        return;
    }
    addArticleAutocompleteState.timer = window.setTimeout(
        () => cargarSugerenciasAgregarArticulo(termino),
        250
    );
}

async function cargarSugerenciasAgregarArticulo(termino) {
    addArticleAutocompleteState.controller?.abort();
    addArticleAutocompleteState.controller = new AbortController();
    const tipo = $("#agregar-tipo-articulo").value;
    const recurso = tipo === "MATERIA_PRIMA" ? "materiales" : "piezas";
    try {
        const response = await fetch(
            `/api/busqueda/${recurso}?q=${encodeURIComponent(termino)}&limite=12`,
            { signal: addArticleAutocompleteState.controller.signal }
        );
        if (!response.ok) return;
        const data = await response.json();
        if (
            $("#agregar-codigo-articulo").value.trim().toUpperCase()
            !== termino.toUpperCase()
        ) return;
        $("#agregar-articulo-options").innerHTML = (data.resultados || [])
            .map((item) => `
                <option
                    value="${escapeHtml(item.codigo)}"
                    label="${escapeHtml(item.descripcion || "")}"
                ></option>
            `).join("");
    } catch (error) {
        if (error.name !== "AbortError") {
            $("#agregar-articulo-options").innerHTML = "";
        }
    }
}

function hayDatosDeConteoParaPreservar() {
    const datos = datosConteoActuales();
    return (
        datos.items.some((item) => (
            item.conteo_fisico !== null
            || item.conteo_vacios !== null
            || item.conteo_llenos !== null
            || item.conteo_rotos !== null
            || item.causa_diferencia_codigo
            || item.ajustado_sistema
            || item.observaciones
        ))
        || datos.ultimo_remito_ingreso
        || datos.ultimo_remito_egreso
        || datos.observaciones !== (state.inventarioSeleccionado?.observaciones || "")
        || datos.ambito !== (state.inventarioSeleccionado?.ambito || "INTERNO")
    );
}

async function agregarArticuloAInventario(event) {
    event.preventDefault();
    let inventario = state.inventarioSeleccionado;
    if (!inventario || inventario.estado === "Cerrado") return;
    const codigo = $("#agregar-codigo-articulo").value.trim();
    if (!codigo) {
        toast("Ingresá el código que querés agregar", true);
        $("#agregar-codigo-articulo").focus();
        return;
    }
    try {
        if (hayDatosDeConteoParaPreservar()) {
            inventario = await api(
                `/api/inventarios/${inventario.id}/conteo`,
                {
                    method: "PUT",
                    body: JSON.stringify(datosConteoActuales()),
                }
            );
            reemplazarInventario(inventario);
        }
        const actualizado = await api(
            `/api/inventarios/${inventario.id}/articulos`,
            {
                method: "POST",
                body: JSON.stringify({
                    codigo,
                    tipo_articulo: $("#agregar-tipo-articulo").value,
                    contar_material: $("#agregar-contar-material").checked,
                    tipo_conteo: $("#agregar-tipo-conteo").value,
                }),
            }
        );
        reemplazarInventario(actualizado);
        cerrarModales();
        renderTodo();
        renderDetalle();
        toast(`${codigo.toUpperCase()} agregado al inventario`);
    } catch (error) {
        toast(error.message, true);
    }
}

function abrirModalActualizarStock() {
    const inventario = state.inventarioSeleccionado;
    if (!inventario || inventario.estado === "Cerrado") return;
    const necesitaPt = inventario.items.some((item) => item.etapa === "TERMINADO");
    const necesitaPrd = inventario.items.some(
        (item) => ["OPERACION", "PROCESO_GLOBAL"].includes(item.etapa)
    );
    const necesitaMp = inventario.items.some((item) => item.etapa === "MATERIAL");
    [
        ["#archivo-stock-pt", "#label-archivo-pt", necesitaPt],
        ["#archivo-stock-prd", "#label-archivo-prd", necesitaPrd],
        ["#archivo-stock-mp", "#label-archivo-mp", necesitaMp],
        ["#archivo-stock-asignado", "#label-archivo-asignado", false],
    ].forEach(([inputSelector, labelSelector, requerido]) => {
        const input = $(inputSelector);
        input.required = requerido;
        input.value = "";
        $(labelSelector).classList.toggle("required-file", requerido);
    });
    abrirModal("#modal-actualizar-stock");
}

async function actualizarStockMysql() {
    const inventario = state.inventarioSeleccionado;
    if (!inventario || inventario.estado === "Cerrado") return;
    const confirmado = confirm(
        "¿Volver a consultar el stock de todas las piezas y materiales?\n\n"
        + "Los conteos físicos escritos se conservarán y se recalcularán "
        + "las diferencias contra la nueva foto del sistema."
    );
    if (!confirmado) return;

    try {
        const actualizado = await api(
            `/api/inventarios/${inventario.id}/actualizar-stock`,
            {
                method: "POST",
                body: JSON.stringify(datosConteoActuales()),
            }
        );
        reemplazarInventario(actualizado);
        cerrarModales();
        renderTodo();
        renderDetalle();
        toast("Stock actualizado desde la base productiva");
    } catch (error) {
        toast(error.message, true);
    }
}

async function actualizarStockExcel(event) {
    event.preventDefault();
    const inventario = state.inventarioSeleccionado;
    if (!inventario || inventario.estado === "Cerrado") return;
    const formulario = new FormData();
    formulario.append(
        "conteos_json",
        JSON.stringify(datosConteoActuales())
    );
    [
        ["#archivo-stock-pt", "archivo_pt"],
        ["#archivo-stock-prd", "archivo_prd"],
        ["#archivo-stock-mp", "archivo_mp"],
        ["#archivo-stock-asignado", "archivo_asignado"],
    ].forEach(([selector, nombre]) => {
        const archivo = $(selector).files[0];
        if (archivo) formulario.append(nombre, archivo, archivo.name);
    });

    try {
        const resultado = await api(
            `/api/inventarios/${inventario.id}/actualizar-stock-excel`,
            { method: "POST", body: formulario }
        );
        reemplazarInventario(resultado.inventario);
        cerrarModales();
        renderTodo();
        renderDetalle();
        const resumen = resultado.resumen;
        const sinRegistro = new Set([
            ...(resumen.sin_registro_pt || []),
            ...(resumen.sin_registro_prd || []),
            ...(resumen.sin_registro_mp || []),
            ...(resumen.sin_registro_asignado || []),
        ]).size;
        toast(
            sinRegistro
                ? `Stock Excel actualizado · ${sinRegistro} códigos sin registro tomados como 0`
                : "Stock actualizado desde los reportes Excel"
        );
    } catch (error) {
        toast(error.message, true);
    }
}

async function cerrarInventario() {
    const inventario = state.inventarioSeleccionado;
    if (!confirm(`¿Cerrar ${inventario.codigo}? Después no se podrá modificar el conteo.`)) return;
    try {
        const guardado = await api(
            `/api/inventarios/${inventario.id}/conteo`,
            {
                method: "PUT",
                body: JSON.stringify(datosConteoActuales()),
            }
        );
        reemplazarInventario(guardado);
        const actualizado = await api(`/api/inventarios/${inventario.id}/cerrar`, { method: "POST" });
        reemplazarInventario(actualizado);
        renderTodo();
        renderDetalle();
        toast("Inventario cerrado");
    } catch (error) {
        toast(error.message, true);
    }
}

function reabrirInventario() {
    const inventario = state.inventarioSeleccionado;
    if (!inventario || inventario.estado !== "Cerrado") return;
    $("#reabrir-autorizado").value = "";
    $("#reabrir-motivo").value = "";
    $("#reabrir-clave").value = "";
    abrirModal("#modal-reabrir");
    setTimeout(() => $("#reabrir-autorizado").focus(), 0);
}

async function confirmarReaperturaInventario(event) {
    event.preventDefault();
    const inventario = state.inventarioSeleccionado;
    if (!inventario || inventario.estado !== "Cerrado") return;
    const boton = event.submitter;
    if (boton) boton.disabled = true;
    try {
        const actualizado = await api(`/api/inventarios/${inventario.id}/reabrir`, {
            method: "POST",
            body: JSON.stringify({
                autorizado_por: $("#reabrir-autorizado").value.trim(),
                motivo: $("#reabrir-motivo").value.trim(),
                clave: $("#reabrir-clave").value,
            }),
        });
        reemplazarInventario(actualizado);
        cerrarModales();
        renderTodo();
        renderDetalle();
        toast(`${inventario.codigo} quedó habilitado para corrección`);
    } catch (error) {
        toast(error.message, true);
        $("#reabrir-clave").select();
    } finally {
        if (boton) boton.disabled = false;
    }
}

async function eliminarInventario() {
    const inventario = state.inventarioSeleccionado;
    if (!inventario) return;

    const confirmado = confirm(
        `¿Eliminar definitivamente ${inventario.codigo}?\n\n`
        + "Se borrarán también todos sus conteos. Esta acción no se puede deshacer."
    );
    if (!confirmado) return;

    try {
        await api(`/api/inventarios/${inventario.id}`, { method: "DELETE" });
        state.inventarios = state.inventarios.filter((item) => item.id !== inventario.id);
        if (inventario.programacion_id) {
            const programacion = state.programaciones.find(
                (item) => item.id === inventario.programacion_id
            );
            if (programacion) {
                programacion.ejecuciones = Math.max(
                    0,
                    programacion.ejecuciones - 1
                );
            }
        }
        state.inventarioSeleccionado = null;
        renderTodo();
        mostrarVista("inventarios");
        toast(`${inventario.codigo} fue eliminado`);
    } catch (error) {
        toast(error.message, true);
    }
}

function exportarExcel() {
    if (state.inventarioSeleccionado) {
        window.location.href = `/api/inventarios/${state.inventarioSeleccionado.id}/excel`;
    }
}

async function crearInventario(event) {
    event.preventDefault();
    const modo = $("#inventario-modo").value;
    const payload = {
        modo,
        fecha: $("#inventario-fecha").value,
        responsable: responsableTexto($("#inventario-responsable")),
        colaboradores: colaboradoresTexto($("#inventario-colaboradores")),
        ambito: $("#inventario-ambito").value,
        observaciones: $("#inventario-observaciones").value.trim(),
        mes_cierre: `${$("#inventario-mes-cierre").value}-01`,
        modalidad_conteo: $("#inventario-modalidad-conteo").value,
        tipo_inventario_codigo: $("#inventario-tipo-inventario").value,
    };
    if (modo === "CICLICO") {
        payload.codigo_raiz = $("#inventario-codigo-raiz").value.trim();
        payload.tipo_conteo = $("#inventario-tipo-conteo").value;
        payload.controla_remitos = $("#inventario-controla-remitos").checked;
        if (!payload.codigo_raiz) {
            toast("Ingresá la pieza raíz del inventario cíclico", true);
            $("#inventario-codigo-raiz").focus();
            return;
        }
    } else if (modo === "MANUAL") {
        payload.articulos_manual = manualInventoryArticles.map((articulo) => ({
            codigo: articulo.codigo,
            tipo_articulo: articulo.tipo_articulo,
            contar_material: articulo.contar_material,
        }));
        payload.tipo_conteo = $("#inventario-tipo-conteo-manual").value;
        payload.controla_remitos =
            $("#inventario-controla-remitos-manual").checked;
        if (!payload.articulos_manual.length) {
            toast("Agregá al menos un código al listado", true);
            $("#inventario-codigo-manual").focus();
            return;
        }
    } else {
        payload.plantilla_id = Number($("#inventario-plantilla").value);
        if (!payload.plantilla_id) {
            toast("Seleccioná una plantilla", true);
            return;
        }
    }
    try {
        const inventario = await api("/api/inventarios", { method: "POST", body: JSON.stringify(payload) });
        state.inventarios.unshift(inventario);
        cerrarModales();
        renderTodo();
        toast("Inventario creado");
        abrirDetalle(inventario.id);
    } catch (error) {
        toast(error.message, true);
    }
}

function abrirModalProgramacion(programacionId = null, plantillaId = null) {
    const programacion = state.programaciones.find(
        (item) => item.id === programacionId
    );
    const primeraActiva = state.plantillas.find(
        (plantilla) => plantilla.activa
    );
    if (!programacion && !primeraActiva) {
        return toast(
            "No hay plantillas activas disponibles para programar",
            true
        );
    }
    $("#programacion-id").value = programacion?.id || "";
    $("#programacion-modal-title").textContent = programacion
        ? "Editar programación"
        : "Programar inventario";
    $("#guardar-programacion").textContent = programacion
        ? "Guardar cambios"
        : "Guardar programación";
    $("#programacion-plantilla").value =
        programacion?.plantilla_id || plantillaId || primeraActiva.id;
    $("#programacion-fecha").value =
        programacion?.fecha_proxima || fechaHoyLocal();
    $("#programacion-mes-cierre").value = (
        programacion?.mes_cierre_proximo?.slice(0, 7)
        || $("#programacion-fecha").value.slice(0, 7)
    );
    $("#programacion-mes-cierre").dataset.automatico = programacion
        ? "false"
        : "true";
    $("#programacion-frecuencia").value =
        programacion?.frecuencia || "UNA_VEZ";
    seleccionarValores(
        $("#programacion-responsable"),
        idsPersonasPorNombres(
            programacion?.responsable || "Agustín Romero"
        )
    );
    seleccionarValores(
        $("#programacion-colaboradores"),
        idsPersonasPorNombres(programacion?.colaboradores || "")
    );
    $("#programacion-observaciones").value =
        programacion?.observaciones || "";
    abrirModal("#modal-programacion");
}

async function guardarProgramacion(event) {
    event.preventDefault();
    const id = Number($("#programacion-id").value) || null;
    const payload = {
        plantilla_id: Number($("#programacion-plantilla").value),
        fecha_proxima: $("#programacion-fecha").value,
        mes_cierre_proximo: `${$("#programacion-mes-cierre").value}-01`,
        frecuencia: $("#programacion-frecuencia").value,
        responsable: responsableTexto($("#programacion-responsable")),
        colaboradores: colaboradoresTexto($("#programacion-colaboradores")),
        observaciones: $("#programacion-observaciones").value.trim(),
    };
    try {
        const guardada = await api(
            id ? `/api/programaciones/${id}` : "/api/programaciones",
            {
                method: id ? "PUT" : "POST",
                body: JSON.stringify(payload),
            }
        );
        reemplazarProgramacion(guardada);
        cerrarModales();
        renderProgramaciones();
        renderCalendario();
        toast(id ? "Programación actualizada" : "Inventario programado");
    } catch (error) {
        toast(error.message, true);
    }
}

async function generarInventarioProgramado(programacionId) {
    const programacion = state.programaciones.find(
        (item) => item.id === programacionId
    );
    if (!programacion) return;
    const confirmado = confirm(
        `¿Generar ahora el inventario de "${programacion.plantilla_nombre}"?\n\n`
        + `Fecha programada: ${formatearFecha(programacion.fecha_proxima)}\n`
        + `Mes de cierre: ${formatearMesCierre(programacion.mes_cierre_proximo)}\n`
        + `Fecha real: ${formatearFecha(fechaHoyLocal())}\n\n`
        + "En este momento se tomará el stock de referencia del sistema."
    );
    if (!confirmado) return;

    try {
        const resultado = await api(
            `/api/programaciones/${programacionId}/generar`,
            { method: "POST" }
        );
        state.inventarios.unshift(resultado.inventario);
        reemplazarProgramacion(resultado.programacion);
        renderTodo();
        toast("Inventario generado desde la programación");
        abrirDetalle(resultado.inventario.id);
    } catch (error) {
        toast(error.message, true);
    }
}

async function alternarProgramacion(programacionId) {
    try {
        const actualizada = await api(
            `/api/programaciones/${programacionId}/alternar`,
            { method: "POST" }
        );
        reemplazarProgramacion(actualizada);
        renderProgramaciones();
        renderCalendario();
        toast(actualizada.activa ? "Programación reanudada" : "Programación pausada");
    } catch (error) {
        toast(error.message, true);
    }
}

async function eliminarProgramacion(programacionId) {
    const programacion = state.programaciones.find(
        (item) => item.id === programacionId
    );
    if (!programacion) return;
    if (!confirm(
        `¿Eliminar la programación de "${programacion.plantilla_nombre}"?\n\n`
        + "Los inventarios ya realizados se conservarán."
    )) return;

    try {
        await api(`/api/programaciones/${programacionId}`, {
            method: "DELETE",
        });
        state.programaciones = state.programaciones.filter(
            (item) => item.id !== programacionId
        );
        renderProgramaciones();
        renderCalendario();
        toast("Programación eliminada");
    } catch (error) {
        toast(error.message, true);
    }
}

async function eliminarPlantilla(plantillaId) {
    const plantilla = state.plantillas.find((item) => item.id === plantillaId);
    if (!plantilla) return;

    const confirmado = confirm(
        `¿Eliminar la plantilla "${plantilla.nombre}"?\n\n`
        + "Los inventarios ya creados se conservarán."
    );
    if (!confirmado) return;

    try {
        await api(`/api/plantillas/${plantilla.id}`, { method: "DELETE" });
        state.plantillas = state.plantillas.filter((item) => item.id !== plantilla.id);
        state.programaciones = state.programaciones.filter(
            (item) => item.plantilla_id !== plantilla.id
        );
        renderTodo();
        toast("Plantilla eliminada");
    } catch (error) {
        toast(error.message, true);
    }
}

function reemplazarProgramacion(actualizada) {
    const indice = state.programaciones.findIndex(
        (item) => item.id === actualizada.id
    );
    if (indice === -1) {
        state.programaciones.push(actualizada);
    } else {
        state.programaciones[indice] = actualizada;
    }
    state.programaciones.sort((a, b) => {
        if (a.activa !== b.activa) return a.activa ? -1 : 1;
        return a.fecha_proxima.localeCompare(b.fecha_proxima);
    });
}

function reemplazarInventario(actualizado) {
    const indice = state.inventarios.findIndex((x) => x.id === actualizado.id);
    state.inventarios[indice] = actualizado;
    state.inventarioSeleccionado = actualizado;
}

function obtenerUltimoInventarioProgramacion(programacionId) {
    return state.inventarios
        .filter((inventario) => inventario.programacion_id === programacionId)
        .sort((a, b) => b.id - a.id)[0] || null;
}

function mostrarVista(nombre) {
    $$(".view").forEach((vista) => vista.classList.add("hidden"));
    $(`#view-${nombre}`).classList.remove("hidden");
    $$(".nav-button").forEach((boton) => boton.classList.toggle("active", boton.dataset.view === nombre));
    const titulos = {
        inventarios: "Inventarios",
        programados: "Programados",
        plantillas: "Plantillas",
        conciliaciones: "Conciliaciones",
        detalle: state.inventarioSeleccionado?.codigo || "Detalle",
    };
    $("#breadcrumb-current").textContent = titulos[nombre];
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function abrirModalInventario(plantillaId = null) {
    const tienePlantillas = state.plantillas.some(
        (plantilla) => plantilla.activa
    );
    $("#inventario-modo").value =
        plantillaId || tienePlantillas ? "PLANTILLA" : "CICLICO";
    if (plantillaId && state.plantillas.find(
        (plantilla) => plantilla.id === plantillaId && plantilla.activa
    )) {
        $("#inventario-plantilla").value = String(plantillaId);
    } else if (tienePlantillas) {
        $("#inventario-plantilla").value = String(
            state.plantillas.find((plantilla) => plantilla.activa).id
        );
    }
    $("#inventario-codigo-raiz").value = "";
    hideCyclicSuggestions();
    $("#inventario-tipo-conteo").value = "GLOBAL";
    $("#inventario-controla-remitos").checked = false;
    $("#inventario-codigo-manual").value = "";
    hideManualSuggestions();
    $("#inventario-tipo-articulo-manual").value = "PIEZA";
    $("#inventario-tipo-conteo-manual").value = "GLOBAL";
    $("#inventario-contar-material-manual").checked = true;
    $("#inventario-controla-remitos-manual").checked = false;
    manualInventoryArticles = [];
    seleccionarValores($("#inventario-colaboradores"), []);
    $("#inventario-ambito").value = "INTERNO";
    $("#inventario-fecha").value = fechaHoyLocal();
    $("#inventario-mes-cierre").dataset.automatico = "true";
    actualizarMesSugerido(
        $("#inventario-fecha"),
        $("#inventario-mes-cierre"),
        true
    );
    $("#inventario-observaciones").value = "";
    $("#inventario-modalidad-conteo").value = "ESTANDAR";
    $("#resumen-raiz-ciclica").classList.add("hidden");
    renderManualInventoryArticles();
    actualizarOpcionesManual();
    cambiarModoInventario();
    abrirModal("#modal-inventario");
    renderResumenPlantilla();
}

function cambiarModoInventario() {
    const modo = $("#inventario-modo").value;
    const esCiclico = modo === "CICLICO";
    const esManual = modo === "MANUAL";
    $("#inventario-desde-plantilla").classList.toggle(
        "hidden",
        esCiclico || esManual
    );
    $("#inventario-ciclico").classList.toggle("hidden", !esCiclico);
    $("#inventario-manual").classList.toggle("hidden", !esManual);
    $("#inventario-plantilla").required = !esCiclico && !esManual;
    $("#inventario-codigo-raiz").required = esCiclico;
    $("#inventario-codigo-manual").required = false;
    if (!esCiclico) hideCyclicSuggestions();
    actualizarDisponibilidadModalidadMedios();
    if (esCiclico) {
        setTimeout(() => $("#inventario-codigo-raiz").focus(), 0);
    } else if (esManual) {
        setTimeout(() => $("#inventario-codigo-manual").focus(), 0);
    }
}

function actualizarOpcionesManual() {
    const esMateriaPrima =
        $("#inventario-tipo-articulo-manual").value === "MATERIA_PRIMA";
    $("#manual-contar-material-wrap").classList.toggle(
        "hidden",
        esMateriaPrima
    );
    $("#inventario-tipo-conteo-manual").closest("label").classList.toggle(
        "hidden",
        esMateriaPrima
    );
    $("#inventario-codigo-manual").value = "";
    hideManualSuggestions();
    renderManualInventoryArticles();
    actualizarDisponibilidadModalidadMedios();
}

function actualizarDisponibilidadModalidadMedios() {
    const selector = $("#inventario-tipo-inventario");
    const modalidad = $("#inventario-modalidad-conteo");
    if (!selector || !modalidad) return;
    const modo = $("#inventario-modo").value;
    const plantilla = state.plantillas.find(
        (item) => item.id === Number($("#inventario-plantilla").value)
    );
    const esMateriaPrima = (
        modo === "MANUAL"
        && $("#inventario-tipo-articulo-manual").value === "MATERIA_PRIMA"
    ) || (
        modo === "PLANTILLA"
        && plantilla?.categoria === "MATERIA_PRIMA"
    );
    const motor = modo === "CICLICO"
        ? "CICLICO"
        : (esMateriaPrima ? "MATERIA_PRIMA" : "PIEZAS");
    const codigoPlantilla = modo === "PLANTILLA"
        ? plantilla?.tipo_inventario_codigo
        : null;
    [...selector.options].forEach((option) => {
        const tipo = state.tiposInventario.find(
            (item) => item.codigo === option.value
        );
        option.hidden = tipo?.motor !== motor;
        option.disabled = option.hidden;
    });
    const disponibles = state.tiposInventario.filter(
        (tipo) => tipo.motor === motor
    );
    if (
        codigoPlantilla
        && disponibles.some((tipo) => tipo.codigo === codigoPlantilla)
    ) {
        selector.value = codigoPlantilla;
    } else if (!disponibles.some((tipo) => tipo.codigo === selector.value)) {
        selector.value = disponibles[0]?.codigo || "";
    }
    selector.disabled = modo === "PLANTILLA";
    sincronizarTipoInventario();
}

function sincronizarTipoInventario() {
    const tipo = state.tiposInventario.find(
        (item) => item.codigo === $("#inventario-tipo-inventario").value
    );
    if (!tipo) return;
    $("#inventario-modalidad-conteo").value = tipo.modalidad;
    $("#inventario-tipo-ayuda").textContent = tipo.descripcion
        || `Usa el motor ${tipo.motor.toLowerCase()}.`;
}

function programarSugerenciasManual() {
    window.clearTimeout(manualAutocompleteState.timer);
    const termino = $("#inventario-codigo-manual").value.trim();
    if (termino.length < 2) {
        hideManualSuggestions();
        return;
    }
    manualAutocompleteState.timer = window.setTimeout(
        () => cargarSugerenciasManual(termino),
        250
    );
}

async function cargarSugerenciasManual(termino) {
    manualAutocompleteState.controller?.abort();
    manualAutocompleteState.controller = new AbortController();
    const tipo = $("#inventario-tipo-articulo-manual").value;
    const recurso = tipo === "MATERIA_PRIMA" ? "materiales" : "piezas";
    try {
        const response = await fetch(
            `/api/busqueda/${recurso}?q=${encodeURIComponent(termino)}&limite=12`,
            { signal: manualAutocompleteState.controller.signal }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || "No se pudieron buscar códigos");
        }
        if (
            $("#inventario-codigo-manual").value.trim().toUpperCase()
            !== termino.toUpperCase()
        ) return;
        manualAutocompleteState.results = data.resultados || [];
        manualAutocompleteState.activeIndex =
            manualAutocompleteState.results.length ? 0 : -1;
        manualAutocompleteState.error = "";
        renderManualSuggestions();
    } catch (error) {
        if (error.name !== "AbortError") {
            manualAutocompleteState.results = [];
            manualAutocompleteState.activeIndex = -1;
            manualAutocompleteState.error = error.message;
            renderManualSuggestions();
        }
    }
}

function renderManualSuggestions() {
    const menu = $("#manual-code-suggestions");
    const input = $("#inventario-codigo-manual");
    if (manualAutocompleteState.error) {
        menu.innerHTML = `
            <div class="autocomplete-empty autocomplete-error">
                ${escapeHtml(manualAutocompleteState.error)}
            </div>
        `;
    } else if (!manualAutocompleteState.results.length) {
        menu.innerHTML = `
            <div class="autocomplete-empty">Sin coincidencias en el maestro</div>
        `;
    } else {
        menu.innerHTML = manualAutocompleteState.results.map((item, index) => {
            const detalle = [
                item.unidad ? `Unidad ${item.unidad}` : "",
                item.diametro ? `Diám. ${item.diametro}` : "",
                item.largo ? `Largo ${item.largo}` : "",
                item.espesor ? `Esp. ${item.espesor}` : "",
            ].filter(Boolean).join(" · ");
            return `
                <button
                    type="button"
                    class="autocomplete-option ${index === manualAutocompleteState.activeIndex ? "active" : ""}"
                    data-manual-suggestion-index="${index}"
                    role="option"
                    aria-selected="${index === manualAutocompleteState.activeIndex}"
                >
                    <strong>${escapeHtml(item.codigo)}</strong>
                    <span>${escapeHtml(item.descripcion || "Sin descripción")}</span>
                    <small>${escapeHtml(detalle)}</small>
                </button>
            `;
        }).join("");
        menu.querySelectorAll(".autocomplete-option").forEach((option) => {
            option.addEventListener("mousedown", (event) => {
                event.preventDefault();
                selectManualSuggestion(
                    Number(option.dataset.manualSuggestionIndex)
                );
            });
        });
    }
    menu.classList.remove("hidden");
    input.setAttribute("aria-expanded", "true");
}

function handleManualSuggestionKeydown(event) {
    const menuVisible =
        !$("#manual-code-suggestions").classList.contains("hidden");
    if (menuVisible && manualAutocompleteState.results.length) {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const direction = event.key === "ArrowDown" ? 1 : -1;
            const length = manualAutocompleteState.results.length;
            manualAutocompleteState.activeIndex =
                (manualAutocompleteState.activeIndex + direction + length)
                % length;
            renderManualSuggestions();
            $("#manual-code-suggestions .autocomplete-option.active")
                ?.scrollIntoView({ block: "nearest" });
            return;
        }
        if (event.key === "Enter") {
            event.preventDefault();
            selectManualSuggestion(manualAutocompleteState.activeIndex);
            return;
        }
    }
    if (event.key === "Escape") {
        hideManualSuggestions();
        return;
    }
    if (event.key === "Enter") {
        event.preventDefault();
        validarCodigoManual();
    }
}

function selectManualSuggestion(index) {
    const item = manualAutocompleteState.results[index];
    if (!item) return;
    $("#inventario-codigo-manual").value = item.codigo;
    hideManualSuggestions();
    $("#inventario-codigo-manual").focus();
}

function hideManualSuggestions() {
    window.clearTimeout(manualAutocompleteState.timer);
    manualAutocompleteState.controller?.abort();
    manualAutocompleteState.results = [];
    manualAutocompleteState.activeIndex = -1;
    manualAutocompleteState.error = "";
    $("#manual-code-suggestions")?.classList.add("hidden");
    $("#inventario-codigo-manual")?.setAttribute("aria-expanded", "false");
}

async function validarCodigoManual() {
    const input = $("#inventario-codigo-manual");
    const codigo = input.value.trim().toUpperCase();
    if (!codigo) {
        toast("Ingresá un código", true);
        input.focus();
        return;
    }
    const boton = $("#validar-codigo-manual");
    const esMateriaPrima =
        $("#inventario-tipo-articulo-manual").value === "MATERIA_PRIMA";
    boton.disabled = true;
    boton.textContent = "Validando…";
    try {
        const articulo = await api(
            `/api/${esMateriaPrima ? "materiales" : "piezas"}/${encodeURIComponent(codigo)}`
        );
        if (manualInventoryArticles.some(
            (item) => item.codigo === articulo.codigo
        )) {
            throw new Error(`El código ${articulo.codigo} ya está en la lista`);
        }
        manualInventoryArticles.push({
            ...articulo,
            tipo_articulo: esMateriaPrima ? "MATERIA_PRIMA" : "PIEZA",
            contar_material: (
                !esMateriaPrima
                && $("#inventario-contar-material-manual").checked
            ),
        });
        input.value = "";
        hideManualSuggestions();
        renderManualInventoryArticles();
        toast(`${articulo.codigo} agregado al listado`);
        input.focus();
    } catch (error) {
        toast(error.message, true);
    } finally {
        boton.disabled = false;
        boton.textContent = "Agregar a la lista";
    }
}

function renderManualInventoryArticles() {
    const count = manualInventoryArticles.length;
    const typeSelect = $("#inventario-tipo-articulo-manual");
    typeSelect.disabled = count > 0;
    $("#manual-list-count").textContent =
        `${count} ${count === 1 ? "artículo" : "artículos"}`;
    $("#manual-list-empty").classList.toggle("hidden", count > 0);
    const list = $("#manual-list-items");
    list.classList.toggle("hidden", count === 0);
    list.innerHTML = manualInventoryArticles.map((articulo, index) => {
        const detalle = articulo.tipo_articulo === "MATERIA_PRIMA"
            ? `MP · ${articulo.unidad || "Sin unidad"}`
            : (
                `${articulo.codigo_cliente || "Sin código cliente"}`
                + (
                    articulo.contar_material
                        ? ` · MP ${articulo.codigo_material || "no asignada"}`
                        : " · Sin conteo de MP"
                )
            );
        return `
            <div>
                <b>${index + 1}</b>
                <p>
                    <strong>${escapeHtml(articulo.codigo)}</strong>
                    <small>${escapeHtml(articulo.descripcion || "Sin descripción")}</small>
                    <small>${escapeHtml(detalle)}</small>
                </p>
                <button
                    type="button"
                    class="manual-list-item-remove"
                    data-remove-manual-index="${index}"
                    title="${escapeHtml(detalle)}"
                >Quitar</button>
            </div>
        `;
    }).join("");
    $$("[data-remove-manual-index]").forEach((button) => {
        button.addEventListener("click", () => {
            manualInventoryArticles.splice(
                Number(button.dataset.removeManualIndex),
                1
            );
            renderManualInventoryArticles();
            actualizarDisponibilidadModalidadMedios();
        });
    });
}

async function validarRaizCiclica() {
    const input = $("#inventario-codigo-raiz");
    const codigo = input.value.trim().toUpperCase();
    if (!codigo) {
        toast("Ingresá una pieza raíz", true);
        input.focus();
        return;
    }
    const boton = $("#validar-raiz-ciclica");
    hideCyclicSuggestions();
    boton.disabled = true;
    boton.textContent = "Validando…";
    try {
        const pieza = await api(`/api/piezas/${encodeURIComponent(codigo)}`);
        const estructura = await api(
            `/api/estructuras/${encodeURIComponent(codigo)}`
        );
        input.value = pieza.codigo;
        const muestra = estructura.nodos.slice(0, 8);
        $("#resumen-raiz-ciclica").innerHTML = `
            <div class="selection-summary-overview">
                <span>↳</span>
                <div>
                    <strong>${escapeHtml(pieza.codigo)} · ${escapeHtml(pieza.descripcion)}</strong>
                    <p>
                        ${estructura.cantidad_codigos} códigos detectados
                        ${pieza.codigo_cliente
                            ? ` · Cliente ${escapeHtml(pieza.codigo_cliente)}`
                            : ""}
                    </p>
                </div>
            </div>
            <div class="selection-preview-list">
                ${muestra.map((nodo) => `
                    <div>
                        <b>${escapeHtml(nodo.nivel)}</b>
                        <p>
                            <strong>${escapeHtml(nodo.codigo)}</strong>
                            <small>
                                ${nodo.codigo_padre
                                    ? `Depende de ${escapeHtml(nodo.codigo_padre)}`
                                    : "Pieza raíz"}
                            </small>
                        </p>
                        <span>Uso ${formatearNumero(nodo.uso_acumulado)}</span>
                    </div>
                `).join("")}
                ${estructura.nodos.length > muestra.length ? `
                    <div>
                        <b>+</b>
                        <p><strong>Y ${estructura.nodos.length - muestra.length} códigos más</strong></p>
                        <span>Estructura completa</span>
                    </div>
                ` : ""}
            </div>
        `;
        $("#resumen-raiz-ciclica").classList.remove("hidden");
        toast("Estructura cíclica validada");
    } catch (error) {
        $("#resumen-raiz-ciclica").classList.add("hidden");
        toast(error.message, true);
        input.select();
    } finally {
        boton.disabled = false;
        boton.textContent = "Validar estructura";
    }
}
function abrirModal(selector) { $(selector).classList.remove("hidden"); }
function cerrarModales() {
    hideCyclicSuggestions();
    $$(".backdrop").forEach((x) => x.classList.add("hidden"));
}
function mostrarLoading(valor) { $("#loading").classList.toggle("hidden", !valor); }

function toast(mensaje, error = false) {
    const elemento = $("#toast");
    elemento.textContent = mensaje;
    elemento.classList.toggle("error", error);
    elemento.classList.remove("hidden");
    clearTimeout(toast.temporizador);
    toast.temporizador = setTimeout(() => elemento.classList.add("hidden"), 3500);
}

function statusHtml(estado) {
    const clase = estado === "Cerrado" || estado === "Activa" ? "closed" : estado === "En conteo" ? "counting" : "preparing";
    return `<span class="status ${clase}">${escapeHtml(estado)}</span>`;
}
function confiabilidadHtml(inventario) {
    if (!inventario.items_evaluables) {
        return '<span class="confidence-empty">—</span>';
    }
    const porcentaje = inventario.confiabilidad ?? 0;
    const provisional = inventario.items_evaluados < inventario.items_evaluables;
    return `
        <div class="confidence ${claseConfiabilidad(porcentaje)}">
            <span>${formatearPorcentaje(porcentaje)}</span>
            <i><b style="width:${Math.max(0, Math.min(100, porcentaje))}%"></b></i>
            <small>
                ${inventario.items_ok} / ${inventario.items_evaluables} OK
                ${provisional ? "· parcial" : ""}
            </small>
        </div>
    `;
}
function claseConfiabilidad(porcentaje) {
    const objetivo = Number(
        state.configuracionIndicadores.objetivo_confiabilidad_pct ?? 90
    );
    const alerta = Number(
        state.configuracionIndicadores.alerta_cliente_pct ?? 85
    );
    if (porcentaje >= objetivo) return "confidence-high";
    if (porcentaje >= alerta) return "confidence-medium";
    return "confidence-low";
}
function estadoProgramacionHtml(estado) {
    const clase = {
        "Vencida": "schedule-overdue",
        "Para hoy": "schedule-today",
        "Próxima": "schedule-upcoming",
        "Pausada": "schedule-paused",
        "Completada": "schedule-completed",
    }[estado] || "schedule-paused";
    return `<span class="schedule-status ${clase}">${escapeHtml(estado)}</span>`;
}
function frecuenciaLabel(frecuencia) {
    return {
        UNA_VEZ: "Una sola vez",
        SEMANAL: "Semanal",
        MENSUAL: "Mensual",
    }[frecuencia] || frecuencia;
}
function parsearFechaISO(valor) {
    const [anio, mes, dia] = String(valor).split("-").map(Number);
    return new Date(anio, mes - 1, dia);
}
function fechaISO(fecha) {
    const anio = fecha.getFullYear();
    const mes = String(fecha.getMonth() + 1).padStart(2, "0");
    const dia = String(fecha.getDate()).padStart(2, "0");
    return `${anio}-${mes}-${dia}`;
}
function sumarDias(fecha, cantidad) {
    const resultado = new Date(
        fecha.getFullYear(),
        fecha.getMonth(),
        fecha.getDate()
    );
    resultado.setDate(resultado.getDate() + cantidad);
    return resultado;
}
function sumarMesConDia(fecha, diaObjetivo) {
    const primerDiaSiguiente = new Date(
        fecha.getFullYear(),
        fecha.getMonth() + 1,
        1
    );
    const ultimoDia = new Date(
        primerDiaSiguiente.getFullYear(),
        primerDiaSiguiente.getMonth() + 1,
        0
    ).getDate();
    return new Date(
        primerDiaSiguiente.getFullYear(),
        primerDiaSiguiente.getMonth(),
        Math.min(diaObjetivo, ultimoDia)
    );
}
function inicioSemana(fecha) {
    return sumarDias(fecha, -((fecha.getDay() + 6) % 7));
}
function rangoDias(inicio, cantidad) {
    return Array.from({ length: cantidad }, (_, indice) => (
        sumarDias(inicio, indice)
    ));
}
function nombreDiaCorto(fecha) {
    return new Intl.DateTimeFormat("es-AR", {
        weekday: "short",
    }).format(fecha).replace(".", "");
}
function tituloSemana(inicio, fin) {
    const inicioTexto = new Intl.DateTimeFormat("es-AR", {
        day: "numeric",
        month: "short",
    }).format(inicio);
    const finTexto = new Intl.DateTimeFormat("es-AR", {
        day: "numeric",
        month: "short",
        year: "numeric",
    }).format(fin);
    return `${inicioTexto} — ${finTexto}`;
}
async function copiarTexto(texto) {
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(texto);
        return;
    }
    const area = document.createElement("textarea");
    area.value = texto;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copiado = typeof document.execCommand === "function"
        && document.execCommand("copy");
    area.remove();
    if (!copiado) throw new Error("No se pudo copiar");
}
async function copiarHtml(html, texto) {
    if (navigator.clipboard?.write && window.ClipboardItem) {
        await navigator.clipboard.write([
            new ClipboardItem({
                "text/html": new Blob([html], { type: "text/html" }),
                "text/plain": new Blob([texto], { type: "text/plain" }),
            }),
        ]);
        return;
    }

    const contenedor = document.createElement("div");
    contenedor.contentEditable = "true";
    contenedor.style.position = "fixed";
    contenedor.style.left = "-10000px";
    contenedor.innerHTML = html;
    document.body.appendChild(contenedor);
    const seleccion = window.getSelection();
    const rango = document.createRange();
    rango.selectNodeContents(contenedor);
    seleccion.removeAllRanges();
    seleccion.addRange(rango);
    const copiado = typeof document.execCommand === "function"
        && document.execCommand("copy");
    seleccion.removeAllRanges();
    contenedor.remove();
    if (!copiado) await copiarTexto(texto);
}
async function crearImagenCronograma() {
    const panel = $("#programaciones-calendario").cloneNode(true);
    panel.classList.remove("hidden");
    panel.classList.add("calendar-image-export");
    panel.querySelector(".calendar-toolbar")?.remove();
    panel.querySelector(".calendar-empty")?.remove();

    const ancho = 1600;
    const alto = state.periodoCalendario === "SEMANA" ? 720 : 1120;
    const estilos = obtenerCssDocumento();
    const ajustes = `
        * { box-sizing: border-box; }
        body { margin: 0; }
        .calendar-image-wrapper {
            background: #ffffff;
            font-family: Arial, sans-serif;
            height: ${alto}px;
            padding: 32px;
            width: ${ancho}px;
        }
        .calendar-image-export {
            border: 0;
            border-radius: 0;
            box-shadow: none;
            overflow: hidden;
            width: 100%;
        }
        .calendar-image-export .calendar-print-header {
            align-items: flex-end;
            border-bottom: 2px solid #244f7e;
            display: flex;
            justify-content: space-between;
            margin-bottom: 14px;
            padding-bottom: 10px;
        }
        .calendar-image-export .calendar-print-header p {
            color: #244f7e;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: .1em;
            margin: 0;
        }
        .calendar-image-export .calendar-print-header h2 {
            font-size: 25px;
            margin: 0;
            text-transform: capitalize;
        }
        .calendar-image-export .calendar-print-header span {
            color: #555;
            font-size: 12px;
        }
        .calendar-image-export .calendar-day { min-height: 148px; }
        .calendar-image-export .calendar-grid.week-view .calendar-day {
            min-height: 530px;
        }
        .calendar-image-export .calendar-event strong { font-size: 11px; }
        .calendar-image-export .calendar-event span { font-size: 10px; }
        .calendar-image-export .calendar-event small,
        .calendar-image-export .calendar-event em { font-size: 9px; }
    `;

    const contenedor = document.createElement("div");
    contenedor.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
    contenedor.className = "calendar-image-wrapper";
    const style = document.createElement("style");
    style.textContent = `${estilos}\n${ajustes}`;
    contenedor.appendChild(style);
    contenedor.appendChild(panel);
    const contenido = new XMLSerializer().serializeToString(contenedor);
    const svg = `
        <svg xmlns="http://www.w3.org/2000/svg" width="${ancho}" height="${alto}">
            <foreignObject width="100%" height="100%">${contenido}</foreignObject>
        </svg>
    `;
    const url = URL.createObjectURL(
        new Blob([svg], { type: "image/svg+xml;charset=utf-8" })
    );
    try {
        const imagen = await cargarImagen(url);
        const canvas = document.createElement("canvas");
        canvas.width = ancho;
        canvas.height = alto;
        const contexto = canvas.getContext("2d");
        contexto.fillStyle = "#ffffff";
        contexto.fillRect(0, 0, ancho, alto);
        contexto.drawImage(imagen, 0, 0);
        return await new Promise((resolve, reject) => {
            canvas.toBlob(
                (blob) => blob ? resolve(blob) : reject(new Error("PNG vacío")),
                "image/png"
            );
        });
    } finally {
        URL.revokeObjectURL(url);
    }
}
function obtenerCssDocumento() {
    return [...document.styleSheets].map((hoja) => {
        try {
            return [...hoja.cssRules].map((regla) => regla.cssText).join("\n");
        } catch {
            return "";
        }
    }).join("\n");
}
function cargarImagen(url) {
    return new Promise((resolve, reject) => {
        const imagen = new Image();
        imagen.onload = () => resolve(imagen);
        imagen.onerror = () => reject(new Error("No se pudo renderizar"));
        imagen.src = url;
    });
}
function descargarBlob(blob, nombre) {
    const url = URL.createObjectURL(blob);
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = nombre;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function categoriaPlantillaLabel(categoria) {
    return {
        PIEZAS: "Piezas y proceso",
        MATERIA_PRIMA: "Materia prima",
        CICLICO: "Cíclico",
    }[categoria] || "Piezas y proceso";
}

function tipoInventarioLabel(codigo, categoria = "PIEZAS") {
    return state.tiposInventario.find((tipo) => tipo.codigo === codigo)?.nombre
        || categoriaPlantillaLabel(categoria);
}

function ambitoInventarioLabel(ambito) {
    return ambito === "CLIENTE" ? "Con cliente" : "Interno";
}
function etapaTexto(etapa) {
    return {
        MATERIAL: "Material sin usar",
        PROCESO_GLOBAL: "Proceso global",
        OPERACION: "En proceso",
        TERMINADO: "Pieza terminada",
    }[etapa] || etapa;
}
function etapaLabel(etapa) {
    return `<span class="stage stage-${String(etapa).toLowerCase()}">${escapeHtml(etapaTexto(etapa))}</span>`;
}
function formatearFecha(fecha) { return fecha.split("-").reverse().join("/"); }
function formatearFechaHora(fechaHora) {
    return new Intl.DateTimeFormat("es-AR", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(new Date(fechaHora));
}
function origenStockLabel(origen) {
    if (origen === "DEMO") return "Datos demo";
    if (origen === "EXCEL") return "Reportes Excel";
    if (origen === "MIXTO") return "Fuentes combinadas";
    return "Base productiva";
}
function fechaHoyLocal() {
    const hoy = new Date();
    const anio = hoy.getFullYear();
    const mes = String(hoy.getMonth() + 1).padStart(2, "0");
    const dia = String(hoy.getDate()).padStart(2, "0");
    return `${anio}-${mes}-${dia}`;
}
function actualizarMesSugerido(fechaInput, mesInput, forzar = false) {
    const sugerido = String(fechaInput.value || "").slice(0, 7);
    if (
        sugerido
        && (forzar || !mesInput.value || mesInput.dataset.automatico === "true")
    ) {
        mesInput.value = sugerido;
        mesInput.dataset.automatico = "true";
    }
}
function formatearMesCierre(valor) {
    const codigo = String(valor || "").slice(0, 7);
    if (!/^\d{4}-\d{2}$/.test(codigo)) return "Sin asignar";
    const [anio, mes] = codigo.split("-").map(Number);
    const texto = new Intl.DateTimeFormat("es-AR", {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
    }).format(new Date(Date.UTC(anio, mes - 1, 1)));
    return texto.charAt(0).toUpperCase() + texto.slice(1);
}
function formatearNumero(numero) { return new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(numero); }
function numeroConSigno(numero) { return numero > 0 ? `+${formatearNumero(numero)}` : formatearNumero(numero); }
function formatearPorcentaje(numero) {
    return `${new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(numero)}%`;
}
function numeroPorcentajeConSigno(numero) {
    return `${numero > 0 ? "+" : ""}${formatearPorcentaje(numero)}`;
}
function escapeHtml(texto) {
    return String(texto ?? "").replace(/[&<>"']/g, (caracter) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
    })[caracter]);
}
