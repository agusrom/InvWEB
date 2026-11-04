(() => {
  const form = document.querySelector("#declaracion-form");
  const hoy = form.dataset.hoy;
  const buscador = document.querySelector("#buscador-pieza");
  const resultados = document.querySelector("#resultados-piezas");
  const estructuraPanel = document.querySelector("#estructura-panel");
  const estructuraLista = document.querySelector("#estructura-lista");
  const estructuraSubtitulo = document.querySelector("#estructura-subtitulo");
  const itemsLista = document.querySelector("#items-lista");
  const itemsVacios = document.querySelector("#items-vacios");
  const itemsJson = document.querySelector("#items-json");
  const tipoMaterialGlobal = document.querySelector("#tipo-material");
  const operacionesLista = document.querySelector("#operaciones-origen");
  let temporizador;
  let temporizadorOperacion;
  let padreActual = null;
  let items = [];
  try { items = JSON.parse(itemsJson.value || "[]"); } catch (_) { items = []; }

  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[c]);
  const optionsHtml = (id, seleccionado) => {
    const temporal = document.createElement("select");
    temporal.append(document.querySelector(id).content.cloneNode(true));
    temporal.querySelectorAll("option").forEach(o => {
      o.selected = String(o.value) === String(seleccionado);
    });
    return temporal.innerHTML;
  };
  const modoActual = () => document.querySelector('input[name="modo"]:checked').value;
  const numero = valor => Number(valor || 0);

  function origenComun() {
    return {
      sector_origen: document.querySelector("#origen-comun-sector").value,
      celula_origen: document.querySelector("#origen-comun-celula").value.trim(),
      operacion_origen: document.querySelector("#origen-comun-operacion").value.trim(),
      tipo_imputacion: document.querySelector("#origen-comun-imputacion").value,
      legajo_origen: document.querySelector("#origen-comun-legajo").value.trim()
    };
  }

  document.querySelector("#aplicar-origen").addEventListener("click", () => {
    const origen = origenComun();
    items.forEach(item => Object.assign(item, origen));
    renderItems();
  });
  document.querySelector("#expandir-todos").addEventListener("click", () => {
    items.forEach(item => item.abierto = true);
    renderItems();
  });
  document.querySelector("#contraer-todos").addEventListener("click", () => {
    items.forEach(item => item.abierto = false);
    renderItems();
  });

  document.querySelectorAll('input[name="modo"]').forEach(radio => {
    radio.addEventListener("change", () => {
      document.querySelectorAll(".choice-card").forEach(c => c.classList.remove("selected"));
      radio.closest(".choice-card").classList.add("selected");
      items.forEach(aplicarModo);
      renderItems();
    });
  });

  function aplicarModo(item) {
    const cantidad = numero(item.cantidad_detectada);
    if (modoActual() === "SCRAP") {
      item.cantidad_scrap_directo = cantidad;
      item.cantidad_a_retrabajo = 0;
      item.retrabajo_estado = "PENDIENTE";
    } else if (modoActual() === "RETRABAJO") {
      item.cantidad_scrap_directo = 0;
      item.cantidad_a_retrabajo = cantidad;
    }
  }

  buscador.addEventListener("input", () => {
    clearTimeout(temporizador);
    const q = buscador.value.trim();
    if (q.length < 2) {
      resultados.innerHTML = "";
      return;
    }
    resultados.innerHTML = '<div class="loading">Buscando códigos…</div>';
    temporizador = setTimeout(async () => {
      try {
        const respuesta = await fetch(`/api/piezas?q=${encodeURIComponent(q)}`);
        const data = await respuesta.json();
        if (!respuesta.ok) throw new Error(data.error);
        resultados.innerHTML = data.length ? data.map(p => `
          <button type="button" class="search-result" data-codigo="${escapeHtml(p.codigo)}">
            <strong>${escapeHtml(p.codigo)}</strong>
            <span>${escapeHtml(p.descripcion)}${p.material ? `<small>Material: ${escapeHtml(p.material)}</small>` : ""}</span>
            <b>Ver estructura →</b>
          </button>`).join("") : '<div class="loading">No se encontraron piezas.</div>';
      } catch (error) {
        resultados.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message || "Error de consulta")}</div>`;
      }
    }, 250);
  });

  resultados.addEventListener("click", async event => {
    const boton = event.target.closest("[data-codigo]");
    if (!boton) return;
    padreActual = boton.dataset.codigo;
    estructuraPanel.classList.remove("hidden");
    estructuraLista.innerHTML = '<div class="loading">Cargando estructura…</div>';
    estructuraSubtitulo.textContent = `Estructura de ${padreActual}`;
    try {
      const respuesta = await fetch(`/api/estructura/${encodeURIComponent(padreActual)}`);
      const data = await respuesta.json();
      if (!respuesta.ok) throw new Error(data.error);
      const principal = data.pieza || {codigo: padreActual, descripcion: "Pieza principal", uso: 1};
      const filas = [{...principal, padre: padreActual, nivel: 0, uso: 1}, ...data.componentes];
      estructuraLista._filas = filas;
      estructuraLista.innerHTML = filas.map((p, index) => `
        <label class="tree-row" style="--nivel:${p.nivel || 0}">
          <input type="checkbox" class="tree-check" data-index="${index}">
          <span class="tree-line"></span>
          <span class="tree-code">${escapeHtml(p.codigo)}</span>
          <span class="tree-desc">${escapeHtml(p.descripcion)}</span>
          <span class="tree-qty">Uso: ${escapeHtml(p.uso ?? 1)}</span>
        </label>`).join("");
      estructuraPanel.scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) {
      estructuraLista.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message || "Error de consulta")}</div>`;
    }
  });

  document.querySelector("#seleccionar-todos").addEventListener("click", () => {
    document.querySelectorAll(".tree-check").forEach(c => c.checked = true);
  });
  document.querySelector("#limpiar-seleccion").addEventListener("click", () => {
    document.querySelectorAll(".tree-check").forEach(c => c.checked = false);
  });
  document.querySelector("#agregar-seleccion").addEventListener("click", () => {
    const filas = estructuraLista._filas || [];
    let primero = true;
    document.querySelectorAll(".tree-check:checked").forEach(check => {
      const pieza = filas[Number(check.dataset.index)];
      const clave = `${padreActual}|${pieza.codigo}`;
      if (!items.some(i => i.clave === clave)) {
        items.push(nuevoItem({
          clave, codigo_padre: padreActual, codigo: pieza.codigo,
          descripcion: pieza.descripcion || "", codigo_cliente: pieza.codigo_cliente || "",
          material: pieza.material || "", uso: pieza.uso || 1,
          tipo_material: Number(pieza.nivel || 0) > 0 ? "COMPONENTE" : tipoMaterialGlobal.value,
          abierto: primero
        }));
        primero = false;
      }
    });
    renderItems();
    itemsLista.scrollIntoView({behavior: "smooth", block: "center"});
  });

  document.querySelector("#agregar-manual").addEventListener("click", () => {
    const consecutivo = items.filter(i => i.manual).length + 1;
    items.forEach(item => item.abierto = false);
    items.push(nuevoItem({
      clave: `manual-${Date.now()}`, codigo: `SIN-COD-${consecutivo}`,
      descripcion: "Material sin código productivo", codigo_padre: "",
      tipo_material: tipoMaterialGlobal.value, manual: true, abierto: true
    }));
    renderItems();
    itemsLista.scrollIntoView({behavior: "smooth", block: "center"});
  });

  function nuevoItem(datos) {
    const item = {
      trazabilidad: "", unidad: "PZS", cantidad_detectada: 1,
      cantidad_scrap_directo: 0, cantidad_a_retrabajo: 0, motivo_id: "",
      observacion: "", codigo_cliente: "", material: "", uso: 1,
      retrabajo_estado: "PENDIENTE", fecha_retrabajo: hoy,
      operacion_retrabajo: "", celula_retrabajo: "", legajo_retrabajo: "",
      minutos_retrabajo: "", personas_retrabajo: 1, cantidad_ok: 0,
      cantidad_scrap_retrabajo: 0, motivo_scrap_retrabajo_id: "",
      observacion_retrabajo: "", abierto: true, ...origenComun(), ...datos
    };
    aplicarModo(item);
    return item;
  }

  function resumenDestino(item) {
    if (modoActual() === "SCRAP") return `<b class="summary-scrap">${escapeHtml(item.cantidad_detectada)} ${escapeHtml(item.unidad)} scrap</b>`;
    if (modoActual() === "RETRABAJO") return `<b class="summary-rework">${escapeHtml(item.cantidad_detectada)} ${escapeHtml(item.unidad)} retrabajo</b>`;
    return `<b class="summary-mixed">${escapeHtml(item.cantidad_scrap_directo)} scrap · ${escapeHtml(item.cantidad_a_retrabajo)} retrabajo</b>`;
  }

  function destinoFields(item) {
    if (modoActual() === "SCRAP") {
      return `
        <label>Cantidad a scrap<input data-field="cantidad_detectada" type="number" min="0.001" step="0.001" value="${escapeHtml(item.cantidad_detectada)}"></label>
        <input data-field="cantidad_scrap_directo" type="hidden" value="${escapeHtml(item.cantidad_scrap_directo)}">
        <input data-field="cantidad_a_retrabajo" type="hidden" value="0">`;
    }
    if (modoActual() === "RETRABAJO") {
      return `
        <label>Cantidad a retrabajo<input data-field="cantidad_detectada" type="number" min="0.001" step="0.001" value="${escapeHtml(item.cantidad_detectada)}"></label>
        <input data-field="cantidad_scrap_directo" type="hidden" value="0">
        <input data-field="cantidad_a_retrabajo" type="hidden" value="${escapeHtml(item.cantidad_a_retrabajo)}">`;
    }
    return `
      <label>Cantidad detectada<input data-field="cantidad_detectada" type="number" min="0.001" step="0.001" value="${escapeHtml(item.cantidad_detectada)}"></label>
      <label>Scrap directo<input data-field="cantidad_scrap_directo" type="number" min="0" step="0.001" value="${escapeHtml(item.cantidad_scrap_directo)}"></label>
      <label>A retrabajo<input data-field="cantidad_a_retrabajo" type="number" min="0" step="0.001" value="${escapeHtml(item.cantidad_a_retrabajo)}"></label>`;
  }

  function retrabajoFields(item) {
    if (numero(item.cantidad_a_retrabajo) <= 0) return "";
    const realizado = item.retrabajo_estado === "REALIZADO";
    return `
      <section class="rework-inline">
        <div class="subsection-heading">
          <div><b>Estado del retrabajo</b><small>Podés dejarlo pendiente o registrar el resultado ahora.</small></div>
          <div class="segmented">
            <label><input type="radio" data-field="retrabajo_estado" value="PENDIENTE" ${!realizado ? "checked" : ""}> Pendiente</label>
            <label><input type="radio" data-field="retrabajo_estado" value="REALIZADO" ${realizado ? "checked" : ""}> Ya realizado</label>
          </div>
        </div>
        ${realizado ? `
        <div class="form-grid rework-fields">
          <label>Fecha<input data-field="fecha_retrabajo" type="date" value="${escapeHtml(item.fecha_retrabajo || hoy)}"></label>
          <label>Operación realizada<input data-field="operacion_retrabajo" class="operacion-autocomplete" list="operaciones-origen" value="${escapeHtml(item.operacion_retrabajo)}" placeholder="Ej. Corrección soldadura"></label>
          <label>Célula que retrabajó<input data-field="celula_retrabajo" value="${escapeHtml(item.celula_retrabajo)}"></label>
          <label>Legajo<input data-field="legajo_retrabajo" data-legajo value="${escapeHtml(item.legajo_retrabajo)}"></label>
          <label>Tiempo (min)<input data-field="minutos_retrabajo" type="number" min="1" value="${escapeHtml(item.minutos_retrabajo)}"></label>
          <label>Personas<input data-field="personas_retrabajo" type="number" min="1" value="${escapeHtml(item.personas_retrabajo)}"></label>
          <label>Recuperadas<input data-field="cantidad_ok" type="number" min="0" step="0.001" value="${escapeHtml(item.cantidad_ok)}"></label>
          <label>Scrap final<input data-field="cantidad_scrap_retrabajo" type="number" min="0" step="0.001" value="${escapeHtml(item.cantidad_scrap_retrabajo)}"></label>
          ${numero(item.cantidad_scrap_retrabajo) > 0 ? `<label class="span-2">Motivo del scrap final<select data-field="motivo_scrap_retrabajo_id">${optionsHtml("#motivos-options", item.motivo_scrap_retrabajo_id)}</select></label>` : ""}
          <label class="${numero(item.cantidad_scrap_retrabajo) > 0 ? "span-2" : "span-4"}">Observación<input data-field="observacion_retrabajo" value="${escapeHtml(item.observacion_retrabajo)}"></label>
        </div>` : ""}
      </section>`;
  }

  function renderItems() {
    itemsVacios.classList.toggle("hidden", items.length > 0);
    itemsLista.innerHTML = items.map((item, index) => `
      <article class="compact-item ${item.abierto ? "open" : ""}" data-index="${index}">
        <header class="compact-item-head">
          <button type="button" class="toggle-item" aria-label="Abrir o cerrar">⌄</button>
          <div class="item-identity">
            <span>${item.codigo_padre ? `REF. ${escapeHtml(item.codigo_padre)}` : "INDEPENDIENTE"}</span>
            <strong>${escapeHtml(item.codigo)}</strong><small>${escapeHtml(item.descripcion)}</small>
          </div>
          <div class="item-summary">${resumenDestino(item)}<small>${item.trazabilidad ? `HCP ${escapeHtml(item.trazabilidad)}` : "Sin HCP"}</small></div>
          <div class="item-origin-summary"><small>Origen</small><b>${escapeHtml(item.celula_origen || "Sin completar")}</b></div>
          <button type="button" class="remove-item" aria-label="Quitar">×</button>
        </header>
        <div class="compact-item-body ${item.abierto ? "" : "hidden"}">
          <div class="form-grid item-fields compact-fields">
            <label>Tipo<select data-field="tipo_material">${optionsHtml("#tipos-options", item.tipo_material)}</select></label>
            ${item.manual ? `<label>Código<input data-field="codigo" value="${escapeHtml(item.codigo)}"></label>` : ""}
            <label>HCP<input data-field="trazabilidad" value="${escapeHtml(item.trazabilidad)}" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" placeholder="6 números"></label>
            <label>Unidad<select data-field="unidad"><option>PZS</option><option>KG</option><option>M</option><option>M2</option></select></label>
            ${destinoFields(item)}
            <label class="${modoActual() === "MIXTO" ? "" : "span-2"}">Defecto / motivo<select data-field="motivo_id">${optionsHtml("#motivos-options", item.motivo_id)}</select></label>
          </div>
          <details class="origin-override">
            <summary>Modificar origen para esta pieza <span>${escapeHtml(item.sector_origen)} · ${escapeHtml(item.celula_origen || "sin célula")}</span></summary>
            <div class="form-grid item-fields origin-fields">
              <label>Sector<select data-field="sector_origen">${optionsHtml("#sectores-options", item.sector_origen)}</select></label>
              <label>Célula<input data-field="celula_origen" value="${escapeHtml(item.celula_origen)}"></label>
              <label>Operación<input data-field="operacion_origen" class="operacion-autocomplete" list="operaciones-origen" value="${escapeHtml(item.operacion_origen)}"></label>
              <label>Imputación<select data-field="tipo_imputacion">${optionsHtml("#imputacion-options", item.tipo_imputacion)}</select></label>
              <label>Legajo<input data-field="legajo_origen" data-legajo value="${escapeHtml(item.legajo_origen)}" placeholder="Opcional"></label>
              <label class="span-3">Observación<input data-field="observacion" value="${escapeHtml(item.observacion)}"></label>
            </div>
          </details>
          ${retrabajoFields(item)}
        </div>
      </article>`).join("");
    itemsLista.querySelectorAll('[data-field="unidad"]').forEach((select, index) => {
      select.value = items[index].unidad;
    });
    sync();
  }

  itemsLista.addEventListener("click", event => {
    const articulo = event.target.closest(".compact-item");
    if (!articulo) return;
    const index = Number(articulo.dataset.index);
    if (event.target.closest(".remove-item")) {
      items.splice(index, 1);
      renderItems();
    } else if (event.target.closest(".toggle-item") || event.target.closest(".item-identity")) {
      items[index].abierto = !items[index].abierto;
      renderItems();
    }
  });
  itemsLista.addEventListener("input", actualizarItem);
  itemsLista.addEventListener("change", actualizarItem);

  function actualizarItem(event) {
    const campo = event.target.dataset.field;
    if (!campo) return;
    const index = Number(event.target.closest(".compact-item").dataset.index);
    items[index][campo] = event.target.value;
    if (campo === "cantidad_detectada" && modoActual() !== "MIXTO") {
      aplicarModo(items[index]);
      if (event.type === "change") renderItems();
      else {
        sync();
        actualizarResumen(index);
      }
      return;
    }
    if (
      campo === "retrabajo_estado" ||
      (campo === "cantidad_scrap_retrabajo" && event.type === "change")
    ) {
      items[index].abierto = true;
      renderItems();
      return;
    }
    if (event.target.classList.contains("operacion-autocomplete")) buscarOperaciones(event.target.value);
    sync();
    actualizarResumen(index);
  }

  function actualizarResumen(index) {
    const articulo = itemsLista.querySelector(`[data-index="${index}"]`);
    if (!articulo) return;
    articulo.querySelector(".item-summary").innerHTML =
      `${resumenDestino(items[index])}<small>${items[index].trazabilidad ? `HCP ${escapeHtml(items[index].trazabilidad)}` : "Sin HCP"}</small>`;
    articulo.querySelector(".item-origin-summary b").textContent =
      items[index].celula_origen || "Sin completar";
  }

  document.querySelector(".operacion-comun").addEventListener("input", event => buscarOperaciones(event.target.value));
  function buscarOperaciones(q) {
    clearTimeout(temporizadorOperacion);
    if (q.trim().length < 1) return;
    temporizadorOperacion = setTimeout(async () => {
      try {
        const respuesta = await fetch(`/api/operaciones?q=${encodeURIComponent(q)}`);
        const data = await respuesta.json();
        if (!respuesta.ok) return;
        operacionesLista.innerHTML = data.map(op =>
          `<option value="${escapeHtml(op.codigo)} · ${escapeHtml(op.titulo)}"></option>`
        ).join("");
      } catch (_) {}
    }, 250);
  }

  function sync() {
    itemsJson.value = JSON.stringify(items.map(({clave, manual, abierto, ...item}) => item));
  }

  form.addEventListener("submit", event => {
    sync();
    if (!items.length) {
      event.preventDefault();
      alert("Agregá al menos una pieza o material.");
      return;
    }
    const datosBasicosInvalidos = items.find(i =>
      !i.codigo || !i.tipo_material || !/^\d{6}$/.test(String(i.trazabilidad || "")) ||
      !i.motivo_id || numero(i.cantidad_detectada) <= 0
    );
    if (datosBasicosInvalidos) {
      event.preventDefault();
      abrirConError(datosBasicosInvalidos, `Revisá código, HCP, cantidad y motivo de ${datosBasicosInvalidos.codigo || "la pieza"}.`);
      return;
    }
    const cantidadesInvalidas = items.find(i =>
      numero(i.cantidad_scrap_directo) + numero(i.cantidad_a_retrabajo) !== numero(i.cantidad_detectada)
    );
    if (cantidadesInvalidas) {
      event.preventDefault();
      alert(`En ${cantidadesInvalidas.codigo}, las cantidades no coinciden con lo detectado.`);
      return;
    }
    const retrabajoInvalido = items.find(i =>
      i.retrabajo_estado === "REALIZADO" &&
      numero(i.cantidad_ok) + numero(i.cantidad_scrap_retrabajo) > numero(i.cantidad_a_retrabajo)
    );
    if (retrabajoInvalido) {
      event.preventDefault();
      alert(`El resultado de retrabajo de ${retrabajoInvalido.codigo} supera la cantidad enviada.`);
      return;
    }
    const retrabajoIncompleto = items.find(i =>
      numero(i.cantidad_a_retrabajo) > 0 && i.retrabajo_estado === "REALIZADO" && (
        !i.fecha_retrabajo || !i.operacion_retrabajo || !i.celula_retrabajo ||
        !i.legajo_retrabajo || numero(i.minutos_retrabajo) <= 0 ||
        numero(i.personas_retrabajo) <= 0 ||
        numero(i.cantidad_ok) + numero(i.cantidad_scrap_retrabajo) <= 0 ||
        (numero(i.cantidad_scrap_retrabajo) > 0 && !i.motivo_scrap_retrabajo_id)
      )
    );
    if (retrabajoIncompleto) {
      event.preventDefault();
      abrirConError(retrabajoIncompleto, `Completá tiempo y resultado del retrabajo de ${retrabajoIncompleto.codigo}.`);
      return;
    }
    const origenIncompleto = items.find(i =>
      !i.sector_origen || !i.celula_origen || !i.operacion_origen || !i.tipo_imputacion
    );
    if (origenIncompleto) {
      event.preventDefault();
      abrirConError(origenIncompleto, `Completá el origen imputado de ${origenIncompleto.codigo}. Podés usar "Aplicar origen a todas".`);
    }
  });

  function abrirConError(item, mensaje) {
    items.forEach(actual => actual.abierto = actual === item);
    renderItems();
    alert(mensaje);
    const index = items.indexOf(item);
    itemsLista.querySelector(`[data-index="${index}"]`)?.scrollIntoView({behavior: "smooth", block: "center"});
  }

  renderItems();
})();
