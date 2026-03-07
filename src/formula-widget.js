(function () {
  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function initFormulaWidget(options) {
    const pdfUrl = (options && options.pdfUrl) || "/data/resources/aa_hl_formula_booklet_2024.pdf";
    const pdfBaseUrl = String(pdfUrl).split("#")[0];
    if (document.getElementById("formulaWidget")) {
      return;
    }

    const widget = document.createElement("section");
    widget.id = "formulaWidget";
    widget.className = "formula-widget";
    widget.innerHTML = `
      <header class="formula-widget-header" id="formulaWidgetHeader">
        <strong>Formula Booklet</strong>
        <div class="formula-widget-actions">
          <button type="button" id="formulaClose" aria-label="Close formula panel">Close</button>
        </div>
      </header>
      <div class="formula-widget-body" id="formulaWidgetBody">
        <div class="formula-pdf-stage" id="formulaPdfStage">
          <iframe id="formulaIframe" title="AA HL Formula Booklet" src="${pdfBaseUrl}#view=FitH"></iframe>
        </div>
      </div>
      <div class="formula-widget-resize" id="formulaWidgetResize" aria-hidden="true"></div>
    `;
    document.body.appendChild(widget);

    const header = document.getElementById("formulaWidgetHeader");
    const closeBtn = document.getElementById("formulaClose");
    const resizeHandle = document.getElementById("formulaWidgetResize");

    const launcher = document.createElement("button");
    launcher.type = "button";
    launcher.id = "formulaLauncher";
    launcher.className = "formula-launcher-btn";
    launcher.textContent = "Formula";
    launcher.hidden = true;
    document.body.appendChild(launcher);

    let dragging = false;
    let dragOffsetX = 0;
    let dragOffsetY = 0;
    let resizing = false;
    let resizeStartX = 0;
    let resizeStartY = 0;
    let resizeStartW = 0;
    let resizeStartH = 0;

    function onMove(ev) {
      if (resizing) {
        const nextW = resizeStartW + (ev.clientX - resizeStartX);
        const nextH = resizeStartH + (ev.clientY - resizeStartY);
        const maxW = Math.max(280, window.innerWidth - 16);
        const maxH = Math.max(260, window.innerHeight - 16);
        widget.style.width = `${clamp(nextW, 280, maxW)}px`;
        widget.style.height = `${clamp(nextH, 260, maxH)}px`;
        return;
      }
      if (!dragging) {
        return;
      }
      const x = ev.clientX - dragOffsetX;
      const y = ev.clientY - dragOffsetY;
      widget.style.left = `${clamp(x, 8, window.innerWidth - 120)}px`;
      widget.style.top = `${clamp(y, 8, window.innerHeight - 80)}px`;
      widget.style.right = "auto";
      widget.style.bottom = "auto";
    }

    function onUp() {
      dragging = false;
      resizing = false;
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    }

    if (header) {
      header.addEventListener("pointerdown", (ev) => {
        if (ev.target instanceof HTMLElement && ev.target.closest(".formula-widget-actions")) {
          return;
        }
        dragging = true;
        const rect = widget.getBoundingClientRect();
        dragOffsetX = ev.clientX - rect.left;
        dragOffsetY = ev.clientY - rect.top;
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
      });
    }

    if (resizeHandle) {
      resizeHandle.addEventListener("pointerdown", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        resizing = true;
        const rect = widget.getBoundingClientRect();
        resizeStartX = ev.clientX;
        resizeStartY = ev.clientY;
        resizeStartW = rect.width;
        resizeStartH = rect.height;
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
      });
    }

    function closeWidget() {
      widget.style.display = "none";
      launcher.hidden = false;
    }

    function openWidget() {
      widget.style.display = "";
      launcher.hidden = true;
    }

    if (closeBtn) {
      closeBtn.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
      });
      closeBtn.addEventListener("click", () => {
        closeWidget();
      });
      closeBtn.addEventListener("pointerup", () => {
        closeWidget();
      });
    }

    launcher.addEventListener("click", () => {
      openWidget();
    });
  }

  window.initFormulaWidget = initFormulaWidget;
})();
