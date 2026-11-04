(() => {
  const form = document.querySelector("[data-piece-config-form]");
  if (!form) return;
  const search = form.querySelector("[data-piece-config-search]");
  const code = form.querySelector("[data-piece-config-code]");
  const results = form.querySelector("[data-piece-config-results]");
  const submit = form.querySelector("[data-piece-config-submit]");
  let timer;
  let currentPieces = [];

  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[char]);

  function select(piece) {
    code.value = piece.codigo;
    search.value = `${piece.codigo} · ${piece.descripcion || "Sin descripción"}`;
    results.classList.add("hidden");
    submit.disabled = false;
  }

  search.addEventListener("input", () => {
    code.value = "";
    submit.disabled = true;
    clearTimeout(timer);
    const query = search.value.trim();
    if (query.length < 2) {
      results.classList.add("hidden");
      return;
    }
    timer = setTimeout(async () => {
      try {
        const response = await fetch(`/api/piezas?q=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error();
        const pieces = await response.json();
        currentPieces = pieces;
        results.innerHTML = pieces.length
          ? pieces.map((piece, index) => `<button type="button" data-piece-index="${index}"><b>${esc(piece.codigo)}</b><span>${esc(piece.descripcion || "Sin descripción")}</span></button>`).join("")
          : "<small>No se encontraron piezas.</small>";
        results.classList.remove("hidden");
        results.onclick = event => {
          const button = event.target.closest("[data-piece-index]");
          if (button) select(pieces[Number(button.dataset.pieceIndex)]);
        };
      } catch (error) {
        results.innerHTML = "<small>No se pudo realizar la búsqueda.</small>";
        results.classList.remove("hidden");
      }
    }, 250);
  });

  search.addEventListener("keydown", event => {
    if (event.key !== "Enter" || results.classList.contains("hidden")) return;
    if (!currentPieces.length) return;
    event.preventDefault();
    select(currentPieces[0]);
  });
})();
