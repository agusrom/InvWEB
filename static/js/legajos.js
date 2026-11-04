(() => {
  const selector = "[data-legajo]";

  function preparar(input) {
    if (!input.matches?.(selector)) return;
    input.inputMode = "numeric";
    input.maxLength = 5;
    input.pattern = "\\d{1,5}";
    input.title = "Ingresá solamente números, hasta 5 dígitos";
  }

  document.querySelectorAll(selector).forEach(preparar);
  document.addEventListener("input", event => {
    if (!event.target.matches?.(selector)) return;
    event.target.value = event.target.value.replace(/\D/g, "").slice(0, 5);
  });

  new MutationObserver(mutations => {
    mutations.forEach(mutation => mutation.addedNodes.forEach(node => {
      if (!(node instanceof Element)) return;
      preparar(node);
      node.querySelectorAll?.(selector).forEach(preparar);
    }));
  }).observe(document.body, {childList: true, subtree: true});
})();
