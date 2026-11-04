(() => {
  const prefix = document.querySelector('[name="PREFIJO_DECLARACION"]');
  const digits = document.querySelector('[name="DIGITOS_DECLARACION"]');
  const preview = document.querySelector("[data-numbering-preview]");
  if (!prefix || !digits || !preview) return;

  function update() {
    const cleanPrefix = prefix.value.trim().toUpperCase() || "DNC";
    const width = Math.min(12, Math.max(3, Number(digits.value) || 6));
    preview.textContent = `${cleanPrefix}-${String(1).padStart(width, "0")}`;
  }
  prefix.addEventListener("input", update);
  digits.addEventListener("input", update);
  update();
})();
