const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

document.addEventListener("DOMContentLoaded", () => {
    inicializarMesCierre();
    $("#report-period").addEventListener("change", cargarReporte);
    $("#report-client").addEventListener("change", cargarReporte);
    $("#report-programming").addEventListener("change", cargarReporte);
    $("#report-inventory-type").addEventListener("change", cargarReporte);
    $("#trend-grouping").addEventListener("change", cargarReporte);
    inicializarHistorialPieza();
    cargarReporte();
});

let temporizadorBusquedaPieza = null;
let sugerenciasPieza = [];

function inicializarHistorialPieza() {
    const input = $("#piece-history-search");
    input.addEventListener("input", () => {
        clearTimeout(temporizadorBusquedaPieza);
        sugerenciasPieza = [];
        const termino = input.value.trim();
        if (termino.length < 2) {
            cerrarSugerenciasPieza();
            return;
        }
        temporizadorBusquedaPieza = setTimeout(
            () => buscarSugerenciasPieza(termino),
            300
        );
    });
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            const codigo = sugerenciasPieza[0]?.codigo || input.value.trim();
            if (codigo) cargarHistorialPieza(codigo);
        }
    });
    $("#piece-history-button").addEventListener("click", () => {
        const codigo = sugerenciasPieza[0]?.codigo || input.value.trim();
        if (codigo) cargarHistorialPieza(codigo);
    });
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".piece-search")) cerrarSugerenciasPieza();
    });
}

async function buscarSugerenciasPieza(termino) {
    try {
        const response = await fetch(
            `/api/reportes/piezas?q=${encodeURIComponent(termino)}`
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "No se pudo buscar");
        if ($("#piece-history-search").value.trim() !== termino) return;
        sugerenciasPieza = data.resultados || [];
        const menu = $("#piece-history-suggestions");
        menu.innerHTML = sugerenciasPieza.length
            ? sugerenciasPieza.map((item) => `
                <button type="button" data-piece-code="${escapeHtml(item.codigo)}">
                    <strong>${escapeHtml(item.codigo)}</strong>
                    <span>${escapeHtml(item.descripcion || "Sin descripción")}</span>
                    ${item.codigo_cliente ? `<small>Cliente: ${escapeHtml(item.codigo_cliente)}</small>` : ""}
                </button>
            `).join("")
            : '<div class="piece-suggestion-empty">No fue contada en inventarios cerrados.</div>';
        menu.classList.remove("hidden");
        menu.querySelectorAll("[data-piece-code]").forEach((button) => {
            button.addEventListener("click", () => cargarHistorialPieza(
                button.dataset.pieceCode
            ));
        });
    } catch (error) {
        mostrarToast(error.message, true);
    }
}

function cerrarSugerenciasPieza() {
    $("#piece-history-suggestions").classList.add("hidden");
    sugerenciasPieza = [];
}

async function cargarHistorialPieza(codigo) {
    cerrarSugerenciasPieza();
    $("#piece-history-search").value = codigo;
    mostrarCarga(true);
    try {
        const response = await fetch(
            `/api/reportes/historial-pieza?codigo=${encodeURIComponent(codigo)}`
        );
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "No se pudo cargar el historial");
        }
        renderHistorialPieza(data);
    } catch (error) {
        mostrarToast(error.message, true);
    } finally {
        mostrarCarga(false);
    }
}

function renderHistorialPieza(data) {
    const resultados = data.resultados || [];
    $("#piece-history-content").classList.toggle("hidden", !resultados.length);
    $("#piece-history-empty").classList.toggle("hidden", resultados.length > 0);
    if (!resultados.length) {
        $("#piece-history-empty").textContent =
            `No se encontraron conteos cerrados para ${data.codigo}.`;
        return;
    }
    $("#piece-history-code").textContent = data.codigo;
    $("#piece-history-description").textContent = [
        data.descripcion,
        data.codigo_cliente ? `Código cliente: ${data.codigo_cliente}` : "",
    ].filter(Boolean).join(" · ");
    $("#piece-history-count").textContent =
        `${data.cantidad_resultados} resultado${data.cantidad_resultados === 1 ? "" : "s"}`;
    $("#piece-history-body").innerHTML = resultados.map((item) => {
        const estado = item.stock_pendiente || item.conteo_fisico === null
            ? '<span class="piece-result pending">Pendiente</span>'
            : (item.dentro_tolerancia
                ? '<span class="piece-result ok">Dentro</span>'
                : '<span class="piece-result difference">Diferencia</span>');
        const detalle = [item.causa, item.observaciones].filter(Boolean).join(" · ") || "—";
        const etapa = [etiquetaEtapa(item.etapa), item.operacion].filter(Boolean).join(" · ");
        return `
            <tr>
                <td>${formatearFecha(item.fecha)}</td>
                <td><strong>${escapeHtml(item.inventario_codigo)}</strong></td>
                <td>${escapeHtml(item.cliente || "—")}</td>
                <td>${escapeHtml(etapa || "—")}</td>
                <td>${item.stock_pendiente ? "Pendiente" : formatoNumero(item.stock_sistema)}</td>
                <td>${item.conteo_fisico === null ? "—" : formatoNumero(item.conteo_fisico)}</td>
                <td class="${claseDiferencia(item.diferencia)}">${item.diferencia === null ? "—" : formatoNumeroConSigno(item.diferencia)}</td>
                <td>${item.desvio_porcentaje === null ? "—" : formatoPorcentaje(item.desvio_porcentaje)}</td>
                <td>${estado}${item.ajustado_sistema ? '<small class="piece-adjusted">Ajustado</small>' : ""}</td>
                <td title="${escapeHtml(detalle)}">${escapeHtml(detalle)}</td>
            </tr>
        `;
    }).join("");
}

function etiquetaEtapa(etapa) {
    return ({
        TERMINADO: "Terminada",
        OPERACION: "Operación",
        PROCESO_GLOBAL: "En proceso",
        MATERIA_PRIMA: "Materia prima",
    })[etapa] || etapa || "";
}

function formatoNumeroConSigno(valor) {
    const numero = Number(valor);
    return `${numero > 0 ? "+" : ""}${formatoNumero(numero)}`;
}

function claseDiferencia(valor) {
    if (valor === null || Number(valor) === 0) return "";
    return Number(valor) > 0 ? "piece-positive" : "piece-negative";
}

async function cargarReporte() {
    mostrarCarga(true);
    const mesCierre = $("#report-period").value;
    const cliente = $("#report-client").value;
    const programacion = $("#report-programming").value;
    const tipoInventario = $("#report-inventory-type").value;
    const agrupacion = $("#trend-grouping").value;
    try {
        const response = await fetch(
            `/api/reportes/resumen?dias=0`
            + `&mes_cierre=${encodeURIComponent(mesCierre)}`
            + `&cliente=${encodeURIComponent(cliente)}`
            + `&programacion=${encodeURIComponent(programacion)}`
            + `&tipo_inventario=${encodeURIComponent(tipoInventario)}`
            + `&agrupacion=${encodeURIComponent(agrupacion)}`
        );
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "No se pudo cargar el reporte");
        }
        renderFiltroMeses(data.filtros);
        renderFiltroClientes(data.filtros);
        renderReporte(data);
    } catch (error) {
        mostrarToast(error.message, true);
    } finally {
        mostrarCarga(false);
    }
}

function inicializarMesCierre() {
    const fecha = new Date();
    fecha.setDate(1);
    fecha.setMonth(fecha.getMonth() - 1);
    const codigo = `${fecha.getFullYear()}-${String(
        fecha.getMonth() + 1
    ).padStart(2, "0")}`;
    const selector = $("#report-period");
    selector.innerHTML = `<option value="${codigo}">${etiquetaMes(codigo)}</option>`;
    selector.value = codigo;
}

function renderFiltroMeses(filtros) {
    const selector = $("#report-period");
    const seleccionado = filtros.mes_cierre || selector.value;
    selector.innerHTML = filtros.meses_cierre.map((mes) => `
        <option value="${mes}" ${mes === seleccionado ? "selected" : ""}>
            ${escapeHtml(etiquetaMes(mes))}
        </option>
    `).join("");
}

function etiquetaMes(codigo) {
    const [anio, mes] = codigo.split("-").map(Number);
    const texto = new Intl.DateTimeFormat("es-AR", {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
    }).format(new Date(Date.UTC(anio, mes - 1, 1)));
    return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function renderFiltroClientes(filtros) {
    const selector = $("#report-client");
    const seleccionado = filtros.cliente || "";
    selector.innerHTML = [
        '<option value="">Todos los clientes</option>',
        ...filtros.clientes.map((cliente) => `
            <option
                value="${escapeHtml(cliente)}"
                ${cliente === seleccionado ? "selected" : ""}
            >${escapeHtml(cliente)}</option>
        `),
    ].join("");
}

function renderReporte(data) {
    const general = data.general;
    const configuracion = data.configuracion || {
        tolerancia_pct: 5,
        objetivo_confiabilidad_pct: 90,
        alerta_cliente_pct: 85,
    };
    $("#metric-reliability").textContent = formatoPorcentaje(
        general.confiabilidad
    );
    $("#metric-reliability").className = claseConfiabilidad(
        general.confiabilidad,
        configuracion
    );
    $("#metric-reliability-detail").textContent =
        `${general.correctos} de ${general.evaluados} renglones dentro del ±`
        + `${formatoNumero(configuracion.tolerancia_pct)}%`;
    $("#metric-inventories").textContent = general.inventarios;
    $("#metric-differences").textContent = general.diferencias;
    $("#metric-differences-detail").textContent =
        `${formatoPorcentaje(general.porcentaje_diferencias)} de los evaluados`;
    $("#metric-pending").textContent = general.ajustes_pendientes;
    $("#metric-pending-detail").textContent = general.ajustes_pendientes
        ? `${general.ajustados} diferencias ya fueron ajustadas`
        : "Sin acciones pendientes";
    $("#metric-cause-coverage").textContent = formatoPorcentaje(
        general.cobertura_causas
    );
    $("#metric-evaluated").textContent = general.evaluados;
    $("#metric-adjusted").textContent = general.ajustados;
    $("#metric-status").textContent = estadoGeneral(general, configuracion);
    $("#metric-status").className = claseConfiabilidad(
        general.confiabilidad,
        configuracion
    );
    $("#trend-tolerance-label").textContent =
        `Porcentaje de renglones dentro del ±`
        + `${formatoNumero(configuracion.tolerancia_pct)}%.`;
    $("#trend-target-label").textContent =
        `Objetivo ${formatoNumero(configuracion.objetivo_confiabilidad_pct)}%`;

    const periodo = data.filtros.mes_cierre
        ? `Cierre ${etiquetaMes(data.filtros.mes_cierre)}`
        : (data.filtros.desde
            ? `${formatearFecha(data.filtros.desde)} al ${formatearFecha(data.filtros.hasta)}`
            : `Historial completo hasta ${formatearFecha(data.filtros.hasta)}`);
    const reasignados = data.filtros.reasignados_mes
        ? ` · ${data.filtros.reasignados_mes} inventario${data.filtros.reasignados_mes === 1 ? "" : "s"}`
            + " realizado en otro mes y asignado a este cierre"
        : "";
    $("#report-scope").textContent =
        `${periodo} · ${data.filtros.cliente || "Todos los clientes"}`
        + ` · ${etiquetaProgramacion(data.filtros.programacion)}`
        + ` · ${etiquetaTipoInventario(data.filtros.tipo_inventario)}`
        + " · Sólo inventarios cerrados"
        + reasignados;

    renderTiposInventario(data.tipos_inventario, configuracion);
    renderTendencia(data.tendencia, configuracion);
    renderGraficoClientes(data.clientes_grafico, configuracion);
    renderClientes(data.clientes, configuracion);
    renderCausas(data.causas);
    renderAlertas(data.alertas);
}

function renderTiposInventario(tipos, configuracion) {
    const contenedor = $("#inventory-type-summary");
    contenedor.innerHTML = tipos.map((tipo) => {
        const porcentaje = tipo.confiabilidad === null
            ? 0
            : (tipo.confiabilidad === 0
                ? 0
                : Math.max(1.5, tipo.confiabilidad));
        const detalle = tipo.inventarios
            ? `${tipo.inventarios} inventario${tipo.inventarios === 1 ? "" : "s"}`
                + ` · ${tipo.evaluados} renglones · ${tipo.diferencias} diferencias`
            : "Sin inventarios para los filtros seleccionados";
        return `
            <button
                type="button"
                class="inventory-type-card ${tipo.codigo}"
                data-inventory-type="${escapeHtml(tipo.codigo)}"
            >
                <span>${escapeHtml(tipo.nombre)}</span>
                <strong class="${claseConfiabilidad(tipo.confiabilidad, configuracion)}">
                    ${formatoPorcentaje(tipo.confiabilidad)}
                </strong>
                <div class="inventory-type-track">
                    <i style="width:${porcentaje}%"></i>
                </div>
                <small>${escapeHtml(detalle)}</small>
            </button>
        `;
    }).join("");
    $$('[data-inventory-type]').forEach((button) => {
        button.addEventListener("click", () => {
            $("#report-inventory-type").value = button.dataset.inventoryType;
            cargarReporte();
        });
    });
}

function renderGraficoClientes(clientes, configuracion) {
    const contenedor = $("#client-chart");
    if (!clientes.length) {
        contenedor.innerHTML = `
            <div class="report-empty">
                No hay clientes con inventarios cerrados para estos filtros.
            </div>
        `;
        return;
    }
    const objetivo = Number(configuracion.objetivo_confiabilidad_pct);
    const barra = (serie, clase, nombre) => {
        if (!serie.inventarios || serie.confiabilidad === null) {
            return `
                <div class="client-bar-row ${clase}">
                    <span>${nombre}</span>
                    <div class="client-bar-track"><i style="width:0"></i></div>
                    <strong>—</strong>
                </div>
            `;
        }
        const detalle = `${serie.inventarios} inventario${serie.inventarios === 1 ? "" : "s"}`
            + ` · ${serie.evaluados} renglones evaluados`;
        return `
            <div class="client-bar-row ${clase}" title="${escapeHtml(detalle)}">
                <span>${nombre}</span>
                <div class="client-bar-track">
                    <i style="width:${serie.confiabilidad === 0
                        ? 0
                        : Math.max(1.5, serie.confiabilidad)}%"></i>
                    <b style="left:${objetivo}%" aria-hidden="true"></b>
                </div>
                <strong>${formatoPorcentaje(serie.confiabilidad)}</strong>
                <small>${serie.inventarios} inv.</small>
            </div>
        `;
    };
    contenedor.innerHTML = clientes.map((item) => `
        <article class="client-chart-item">
            <button
                type="button"
                class="client-chart-name"
                data-chart-client="${escapeHtml(item.cliente)}"
            >${escapeHtml(item.cliente)}</button>
            <div class="client-chart-bars">
                ${barra(item.programado, "scheduled", "Prog.")}
                ${barra(item.no_programado, "unscheduled", "No prog.")}
            </div>
        </article>
    `).join("");
    $$('[data-chart-client]').forEach((button) => {
        button.addEventListener("click", () => {
            $("#report-client").value = button.dataset.chartClient;
            cargarReporte();
        });
    });
}

function etiquetaProgramacion(valor) {
    if (valor === "programado") return "Programados";
    if (valor === "no_programado") return "No programados";
    return "Programados y no programados";
}

function etiquetaTipoInventario(valor) {
    if (valor === "piezas") return "Piezas";
    if (valor === "medios") return "Medios";
    if (valor === "materia_prima") return "Materia prima";
    return "Todos los tipos";
}

function renderTendencia(puntos, configuracion) {
    const contenedor = $("#trend-chart");
    const validos = puntos.filter((item) => item.confiabilidad !== null);
    if (!validos.length) {
        contenedor.innerHTML = `
            <div class="report-empty">
                Todavía no hay suficientes inventarios cerrados para mostrar una evolución.
            </div>
        `;
        return;
    }
    const width = Math.max(900, validos.length * 68 + 66);
    const height = 245;
    const margin = { left: 42, right: 24, top: 22, bottom: 42 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const x = (index) => (
        margin.left
        + (
            validos.length === 1
                ? innerWidth / 2
                : index * innerWidth / (validos.length - 1)
        )
    );
    const y = (valor) => margin.top + (100 - valor) * innerHeight / 100;
    const objetivo = Number(configuracion.objetivo_confiabilidad_pct);
    const coords = validos.map((item, index) => ({
        ...item,
        x: x(index),
        y: y(item.confiabilidad),
    }));
    const path = coords.map(
        (item, index) => `${index ? "L" : "M"} ${item.x} ${item.y}`
    ).join(" ");
    const area = (
        `${path} L ${coords.at(-1).x} ${margin.top + innerHeight}`
        + ` L ${coords[0].x} ${margin.top + innerHeight} Z`
    );
    const grillas = [0, 25, 50, 75, 100].map((valor) => `
        <line
            class="trend-grid"
            x1="${margin.left}"
            x2="${width - margin.right}"
            y1="${y(valor)}"
            y2="${y(valor)}"
        />
        <text class="trend-label" x="4" y="${y(valor) + 3}">${valor}%</text>
    `).join("");
    contenedor.innerHTML = `
        <svg
            viewBox="0 0 ${width} ${height}"
            style="width:${width}px"
            role="img"
            aria-label="Evolución de confiabilidad"
        >
            <defs>
                <linearGradient id="trend-gradient" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stop-color="#8fb1ff" stop-opacity=".45"/>
                    <stop offset="100%" stop-color="#8fb1ff" stop-opacity=".04"/>
                </linearGradient>
            </defs>
            ${grillas}
            <line
                class="trend-target"
                x1="${margin.left}"
                x2="${width - margin.right}"
                y1="${y(objetivo)}"
                y2="${y(objetivo)}"
            />
            <path class="trend-area" d="${area}"/>
            <path class="trend-line" d="${path}"/>
            ${coords.map((item) => `
                <g class="trend-point-group">
                    <title>${escapeHtml(
                        `${item.etiqueta}: ${formatoPorcentaje(item.confiabilidad)}`
                        + ` · ${item.inventarios} inventario${item.inventarios === 1 ? "" : "s"}`
                        + ` · ${item.evaluados} renglones evaluados`
                    )}</title>
                    <circle class="trend-point" cx="${item.x}" cy="${item.y}" r="4"/>
                </g>
                <text
                    class="trend-value"
                    text-anchor="middle"
                    x="${item.x}"
                    y="${Math.max(12, item.y - 10)}"
                >${formatoPorcentaje(item.confiabilidad)}</text>
                <text
                    class="trend-label"
                    text-anchor="middle"
                    x="${item.x}"
                    y="${height - 15}"
                >${escapeHtml(item.etiqueta)}</text>
            `).join("")}
        </svg>
    `;
    contenedor.scrollLeft = 0;
}

function renderClientes(clientes, configuracion) {
    const cuerpo = $("#report-client-body");
    const vacio = $("#report-client-empty");
    vacio.classList.toggle("hidden", clientes.length > 0);
    cuerpo.innerHTML = clientes.map((item) => `
        <tr>
            <td>
                <button
                    type="button"
                    class="client-filter-button"
                    data-report-client="${escapeHtml(item.cliente)}"
                >${escapeHtml(item.cliente)}</button>
            </td>
            <td>${item.inventarios}</td>
            <td>
                <span class="report-value-pill ${claseValor(item.confiabilidad, configuracion)}">
                    ${formatoPorcentaje(item.confiabilidad)}
                </span>
            </td>
            <td>${item.diferencias}</td>
            <td>${item.ajustes_pendientes}</td>
            <td>${tendenciaHtml(item.tendencia)}</td>
        </tr>
    `).join("");
    $$("[data-report-client]").forEach((button) => {
        button.addEventListener("click", () => {
            $("#report-client").value = button.dataset.reportClient;
            cargarReporte();
        });
    });
}

function renderCausas(causas) {
    $("#report-causes-empty").classList.toggle("hidden", causas.length > 0);
    $("#report-causes").innerHTML = causas.map((item) => `
        <article class="cause-item ${item.codigo === "SIN_CAUSA" ? "no-cause" : ""}">
            <header>
                <div>
                    <strong>${escapeHtml(item.nombre)}</strong>
                    <small>
                        ${item.cantidad} casos · ${item.pendientes} pendientes de ajuste
                    </small>
                </div>
                <span>${formatoPorcentaje(item.porcentaje)}</span>
            </header>
            <div class="cause-track">
                <span style="width:${Math.max(2, item.porcentaje || 0)}%"></span>
            </div>
        </article>
    `).join("");
}

function renderAlertas(alertas) {
    $("#report-alert-count").textContent =
        `${alertas.length} ${alertas.length === 1 ? "alerta" : "alertas"}`;
    $("#report-alerts-empty").classList.toggle("hidden", alertas.length > 0);
    $("#report-alerts").innerHTML = alertas.map((item) => `
        <article class="alert-item ${item.nivel === "ALTO" ? "high" : ""}">
            <span>${escapeHtml(item.tipo)}</span>
            <strong>${escapeHtml(item.titulo)}</strong>
            <small>${escapeHtml(item.detalle)}</small>
        </article>
    `).join("");
}

function estadoGeneral(general, configuracion) {
    if (general.confiabilidad === null) return "Sin datos";
    const objetivo = Number(configuracion.objetivo_confiabilidad_pct);
    const alerta = Number(configuracion.alerta_cliente_pct);
    if (general.confiabilidad >= objetivo && !general.ajustes_pendientes) {
        return "Controlado";
    }
    if (general.confiabilidad >= alerta) return "Requiere seguimiento";
    return "Atención requerida";
}

function formatoPorcentaje(valor) {
    if (valor === null || valor === undefined) return "—";
    return `${new Intl.NumberFormat("es-AR", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 1,
    }).format(valor)}%`;
}

function claseValor(valor, configuracion) {
    if (valor === null || valor === undefined) return "trend-flat";
    if (valor >= Number(configuracion.objetivo_confiabilidad_pct)) {
        return "value-good";
    }
    if (valor >= Number(configuracion.alerta_cliente_pct)) {
        return "value-watch";
    }
    return "value-bad";
}

function claseConfiabilidad(valor, configuracion = {
    objetivo_confiabilidad_pct: 90,
    alerta_cliente_pct: 85,
}) {
    if (valor === null || valor === undefined) return "";
    if (valor >= Number(configuracion.objetivo_confiabilidad_pct)) {
        return "confidence-high";
    }
    if (valor >= Number(configuracion.alerta_cliente_pct)) {
        return "confidence-medium";
    }
    return "confidence-low";
}

function formatoNumero(valor) {
    return new Intl.NumberFormat("es-AR", {
        maximumFractionDigits: 1,
    }).format(Number(valor));
}

function tendenciaHtml(valor) {
    if (valor === null || valor === undefined) {
        return '<span class="trend-pill trend-flat">Sin base</span>';
    }
    if (Math.abs(valor) < 0.05) {
        return '<span class="trend-pill trend-flat">→ 0 pp</span>';
    }
    const clase = valor > 0 ? "trend-up" : "trend-down";
    const flecha = valor > 0 ? "↑" : "↓";
    return `
        <span class="trend-pill ${clase}">
            ${flecha} ${formatoPorcentaje(Math.abs(valor)).replace("%", " pp")}
        </span>
    `;
}

function formatearFecha(valor) {
    if (!valor) return "—";
    const [anio, mes, dia] = valor.split("-");
    return `${dia}/${mes}/${anio}`;
}

function escapeHtml(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function mostrarCarga(valor) {
    $("#report-loading").classList.toggle("hidden", !valor);
}

function mostrarToast(mensaje, error = false) {
    const toast = $("#report-toast");
    toast.textContent = mensaje;
    toast.classList.toggle("error", error);
    toast.classList.remove("hidden");
    clearTimeout(mostrarToast.timer);
    mostrarToast.timer = setTimeout(
        () => toast.classList.add("hidden"),
        3500
    );
}
