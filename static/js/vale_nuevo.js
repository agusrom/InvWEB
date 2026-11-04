(() => {
  const buscador = document.querySelector("#buscador-pieza");
  const resultados = document.querySelector("#resultados-piezas");
  const estructuraPanel = document.querySelector("#estructura-panel");
  const estructuraLista = document.querySelector("#estructura-lista");
  const estructuraSubtitulo = document.querySelector("#estructura-subtitulo");
  const itemsLista = document.querySelector("#items-lista");
  const itemsVacios = document.querySelector("#items-vacios");
  const itemsJson = document.querySelector("#items-json");
  const form = document.querySelector("#vale-form");
  let temporizador;
  let padreActual = null;
  let items = [];

  try { items = JSON.parse(itemsJson.value || "[]"); } catch (_) { items = []; }

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[c]);

  buscador.addEventListener("input", () => {
    clearTimeout(temporizador);
    const q = buscador.value.trim();
    if (q.length < 2) {
      resultados.innerHTML = "";
      return;
    }
    resultados.innerHTML = '<div class="loading">Buscando…</div>';
    temporizador = setTimeout(async () => {
      try {
        const respuesta = await fetch(`/api/piezas?q=${encodeURIComponent(q)}`);
        const data = await respuesta.json();
        if (!respuesta.ok) throw new Error(data.error);
        resultados.innerHTML = data.length ? data.map(p => `
          <button type="button" class="search-result" data-codigo="${escapeHtml(p.codigo)}">
            <strong>${escapeHtml(p.codigo)}</strong>
            <span>${escapeHtml(p.descripcion)}</span>
            <b>Ver estructura →</b>
          </button>`).join("") : '<div class="loading">No se encontraron piezas.</div>';
      } catch (error) {
        resultados.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message || "Error de consulta")}</div>`;
      }
    }, 250);
  });

  resultados.addEventListener("click", async (event) => {
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
      const principal = data.pieza || {codigo: padreActual, descripcion: "Pieza principal"};
      const filas = [{...principal, padre: padreActual, nivel: 0, uso: 1}, ...data.componentes];
      estructuraLista.innerHTML = filas.map((p, index) => `
        <label class="tree-row" style="--nivel:${p.nivel || 0}">
          <input type="checkbox" class="tree-check" data-index="${index}">
          <span class="tree-line"></span>
          <span class="tree-code">${escapeHtml(p.codigo)}</span>
          <span class="tree-desc">${escapeHtml(p.descripcion)}</span>
          <span class="tree-qty">Uso: ${escapeHtml(p.uso ?? 1)}</span>
        </label>`).join("");
      estructuraLista._filas = filas;
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
    document.querySelectorAll(".tree-check:checked").forEach(check => {
      const pieza = filas[Number(check.dataset.index)];
      const clave = `${padreActual}|${pieza.codigo}`;
      if (!items.some(i => i.clave === clave)) {
        items.push({
          clave, codigo_padre: padreActual, codigo: pieza.codigo,
          descripcion: pieza.descripcion || "", trazabilidad: "",
          cantidad: 1, motivo_id: "", observacion: ""
        });
      }
    });
    renderItems();
    itemsLista.scrollIntoView({behavior: "smooth", block: "center"});
  });

  function renderItems() {
    itemsVacios.classList.toggle("hidden", items.length > 0);
    itemsLista.innerHTML = items.map((item, index) => `
      <article class="scrap-item" data-index="${index}">
        <div class="item-heading">
          <div><span>${escapeHtml(item.codigo_padre)}</span><h3>${escapeHtml(item.codigo)}</h3><p>${escapeHtml(item.descripcion)}</p></div>
          <button type="button" class="remove-item" aria-label="Quitar">×</button>
        </div>
        <div class="form-grid item-fields">
          <label>Trazabilidad<input data-field="trazabilidad" value="${escapeHtml(item.trazabilidad)}" required placeholder="Número o código"></label>
          <label>Cantidad<input data-field="cantidad" type="number" min="0.001" step="0.001" value="${escapeHtml(item.cantidad)}" required></label>
          <label class="span-2">Motivo<select data-field="motivo_id" required>${motivosConSeleccion(item.motivo_id)}</select></label>
          <label class="span-4">Observación del componente<input data-field="observacion" value="${escapeHtml(item.observacion)}" placeholder="Opcional"></label>
        </div>
      </article>`).join("");
    sync();
  }

  function motivosConSeleccion(seleccionado) {
    const template = document.querySelector("#motivos-options").content.cloneNode(true);
    const temporal = document.createElement("select");
    temporal.append(template);
    temporal.querySelectorAll("option").forEach(o => {
      if (String(o.value) === String(seleccionado)) o.selected = true;
    });
    return temporal.innerHTML;
  }

  itemsLista.addEventListener("input", actualizarItem);
  itemsLista.addEventListener("change", actualizarItem);
  itemsLista.addEventListener("click", event => {
    const quitar = event.target.closest(".remove-item");
    if (!quitar) return;
    const index = Number(quitar.closest(".scrap-item").dataset.index);
    items.splice(index, 1);
    renderItems();
  });

  function actualizarItem(event) {
    const campo = event.target.dataset.field;
    if (!campo) return;
    const index = Number(event.target.closest(".scrap-item").dataset.index);
    items[index][campo] = event.target.value;
    sync();
  }

  function sync() {
    itemsJson.value = JSON.stringify(items.map(({clave, ...item}) => item));
  }

  form.addEventListener("submit", event => {
    sync();
    if (!items.length) {
      event.preventDefault();
      alert("Agregá al menos una pieza o componente.");
    }
  });

  renderItems();
})();

