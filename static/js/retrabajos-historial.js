(() => {
  const search = document.querySelector("[data-history-search]");
  if (!search) return;
  const rows = [...document.querySelectorAll("[data-history-row]")];
  const empty = document.querySelector("[data-history-empty]");
  const normalize = value => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();

  search.addEventListener("input", () => {
    const query = normalize(search.value);
    let visible = 0;
    rows.forEach(row => {
      const show = !query || normalize(row.dataset.search).includes(query);
      row.classList.toggle("hidden", !show);
      if (show) visible += 1;
    });
    empty?.classList.toggle("hidden", visible > 0);
  });
})();
