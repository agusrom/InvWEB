(() => {
  const input = document.querySelector(".operacion-autocomplete");
  const lista = document.querySelector("#operaciones-lista");
  let temporizador;
  if (!input || !lista) return;
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[c]);
  let valoresValidos = new Set();

  const marcarValidez = () => {
    const valor = input.value.trim();
    input.setCustomValidity(
      valor && valoresValidos.has(valor)
        ? ""
        : "Seleccioná una operación válida de la lista"
    );
    input.dispatchEvent(new Event("operationvalidation"));
  };

  input.setCustomValidity("Seleccioná una operación válida de la lista");
  input.addEventListener("input", () => {
    clearTimeout(temporizador);
    marcarValidez();
    if (!input.value.trim()) {
      lista.innerHTML = "";
      return;
    }
    temporizador = setTimeout(async () => {
      try {
        const consulta = input.value.includes("·")
          ? input.value.split("·", 1)[0].trim()
          : input.value.trim();
        const respuesta = await fetch(`/api/operaciones?q=${encodeURIComponent(consulta)}`);
        const data = await respuesta.json();
        if (!respuesta.ok) return;
        valoresValidos = new Set(data.map(op =>
          `${String(op.codigo).trim()} · ${String(op.titulo || "").trim()}`
        ));
        lista.innerHTML = data.map(op =>
          `<option value="${escapeHtml(op.codigo)} · ${escapeHtml(op.titulo)}"></option>`
        ).join("");
        marcarValidez();
      } catch (_) {}
    }, 250);
  });
  input.addEventListener("change", marcarValidez);
  input.addEventListener("blur", marcarValidez);
  if (input.value.trim()) {
    input.dispatchEvent(new Event("input", {bubbles: true}));
  }
})();
