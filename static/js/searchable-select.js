(() => {
  const normalize = value => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();

  window.focusNextField = current => {
    if (!current) return;
    const step = current.closest(".wizard-step.active") || current.closest(".wizard-step");
    if (!step) return;
    const fields = [...step.querySelectorAll(
      'input:not([type="hidden"]):not([type="radio"]):not([readonly]), ' +
      'textarea:not([readonly]), select:not(.searchable-select-native), ' +
      'button[data-flow-next]'
    )].filter(field =>
      !field.disabled &&
      field.offsetParent !== null &&
      !field.closest(".searchable-select-menu, .autocomplete-results")
    );
    const index = fields.indexOf(current);
    const next = fields.slice(index + 1).find(field => !field.disabled);
    if (next) {
      next.focus();
      if (next.matches('input[type="search"], input[type="text"], input:not([type])')) {
        next.select?.();
      }
      return;
    }
    document.querySelector("#siguiente:not(.hidden):not(:disabled)")?.focus();
  };

  function enhance(select) {
    if (select.dataset.searchEnhanced === "true") return;
    select.dataset.searchEnhanced = "true";

    const wrapper = document.createElement("div");
    wrapper.className = "searchable-select";
    const input = document.createElement("input");
    input.type = "search";
    input.autocomplete = "off";
    input.className = "searchable-select-input";
    const menu = document.createElement("div");
    menu.className = "searchable-select-menu hidden";

    select.parentNode.insertBefore(wrapper, select);
    wrapper.append(input, menu, select);
    select.classList.add("searchable-select-native");
    select.tabIndex = -1;
    let activeIndex = -1;
    let visibleOptions = [];

    const sync = () => {
      input.disabled = select.disabled;
      const selected = [...select.options].find(
        option => option.value && option.value === select.value
      );
      input.value = selected ? selected.textContent.trim() : "";
      input.placeholder = select.options[0]?.textContent.trim() || "Buscar…";
      if (select.disabled) menu.classList.add("hidden");
    };

    const choose = option => {
      select.value = option.value;
      input.value = option.textContent.trim();
      menu.classList.add("hidden");
      select.dispatchEvent(new Event("change", {bubbles: true}));
      if (!select.hasAttribute("data-no-auto-next")) {
        setTimeout(() => window.focusNextField?.(input), 0);
      }
    };

    const render = query => {
      const needle = normalize(query);
      visibleOptions = [...select.options].filter(option =>
        option.value && (
          normalize(option.textContent).includes(needle) ||
          normalize(option.dataset.search).includes(needle) ||
          normalize(option.value).includes(needle)
        )
      );
      activeIndex = visibleOptions.length ? 0 : -1;
      menu.innerHTML = visibleOptions.length
        ? visibleOptions.map((option, index) => `
            <button type="button" data-search-option="${index}" class="${index === activeIndex ? "active" : ""}">
              ${option.textContent.trim().replace(/[&<>"']/g, char => ({
                "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
              })[char])}
            </button>`).join("")
        : '<small>Sin coincidencias</small>';
      menu.classList.remove("hidden");
    };

    const paintActive = () => {
      menu.querySelectorAll("[data-search-option]").forEach((button, index) =>
        button.classList.toggle("active", index === activeIndex));
      menu.querySelector(".active")?.scrollIntoView({block: "nearest"});
    };

    input.addEventListener("focus", () => {
      if (input.disabled) return;
      input.select();
      render("");
    });
    input.addEventListener("input", () => render(input.value));
    input.addEventListener("keydown", event => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (menu.classList.contains("hidden")) render(input.value);
        const direction = event.key === "ArrowDown" ? 1 : -1;
        activeIndex = Math.max(
          0,
          Math.min(visibleOptions.length - 1, activeIndex + direction)
        );
        paintActive();
      } else if (event.key === "Enter") {
        if (!menu.classList.contains("hidden") && visibleOptions[activeIndex]) {
          event.preventDefault();
          choose(visibleOptions[activeIndex]);
        }
      } else if (event.key === "Escape") {
        menu.classList.add("hidden");
        sync();
      }
    });
    input.addEventListener("blur", () => {
      setTimeout(() => {
        menu.classList.add("hidden");
        sync();
      }, 120);
    });
    menu.addEventListener("mousedown", event => {
      const button = event.target.closest("[data-search-option]");
      if (!button) return;
      event.preventDefault();
      choose(visibleOptions[Number(button.dataset.searchOption)]);
    });
    select.addEventListener("change", sync);

    new MutationObserver(sync).observe(select, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["disabled"],
    });
    sync();
  }

  window.enhanceSearchable = root => {
    root.querySelectorAll("select[data-searchable]").forEach(enhance);
  };
  window.enhanceSearchable(document);
})();
