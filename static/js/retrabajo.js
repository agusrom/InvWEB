(() => {
  const form = document.querySelector("#rework-form");
  if (!form) return;

  const pending = Number(form.dataset.pending);
  const recovered = form.elements.cantidad_ok;
  const scrap = form.elements.cantidad_scrap;
  const totalStatus = form.querySelector("[data-rework-total]");
  const submit = form.querySelector("[data-rework-submit]");

  function validInteger(input) {
    const value = Number(input.value);
    return input.value !== "" && Number.isInteger(value) && value >= 0;
  }

  function update() {
    const recoveredValue = Number(recovered.value);
    const scrapValue = Number(scrap.value);
    const integers = validInteger(recovered) && validInteger(scrap);
    const total = recoveredValue + scrapValue;

    totalStatus.classList.remove("ok");
    if (!integers) {
      totalStatus.textContent = "Ingresá cantidades enteras, sin decimales.";
    } else if (total === pending) {
      totalStatus.textContent = `Correcto: ${total} de ${pending} piezas informadas.`;
      totalStatus.classList.add("ok");
    } else if (total < pending) {
      totalStatus.textContent = `Faltan asignar ${pending - total} de ${pending} piezas.`;
    } else {
      totalStatus.textContent = `La suma excede en ${total - pending} la cantidad pendiente.`;
    }

    const requiredFieldsValid = [...form.querySelectorAll("[required]")].every(field =>
      field.disabled || (String(field.value || "").trim() && field.validity.valid)
    );
    const quantitiesValid = integers && total === pending;
    submit.disabled = !(requiredFieldsValid && quantitiesValid);
  }

  recovered.addEventListener("input", update);
  scrap.addEventListener("input", update);
  form.querySelectorAll("input, select, textarea").forEach(field => {
    field.addEventListener("input", update);
    field.addEventListener("change", update);
  });
  form.addEventListener("submit", event => {
    update();
    if (submit.disabled || !form.reportValidity()) {
      event.preventDefault();
    }
  });

  update();
})();
