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
          <button type="button" id="formulaZoomOut" aria-label="Zoom out">-</button>
          <button type="button" id="formulaZoomIn" aria-label="Zoom in">+</button>
          <button type="button" id="formulaZoomReset" aria-label="Reset zoom">100%</button>
          <button type="button" id="formulaClose" aria-label="Close formula panel">Close</button>
        </div>
      </header>
      <div class="formula-widget-body" id="formulaWidgetBody">
        <div class="formula-pdf-stage" id="formulaPdfStage">
          <iframe id="formulaIframe" title="AA HL Formula Booklet" src="${pdfBaseUrl}#view=FitH"></iframe>
        </div>
      </div>
    `;
    document.body.appendChild(widget);

    const header = document.getElementById("formulaWidgetHeader");
    const iframe = document.getElementById("formulaIframe");
    const zoomInBtn = document.getElementById("formulaZoomIn");
    const zoomOutBtn = document.getElementById("formulaZoomOut");
    const zoomResetBtn = document.getElementById("formulaZoomReset");
    const closeBtn = document.getElementById("formulaClose");

    const launcher = document.createElement("button");
    launcher.type = "button";
    launcher.id = "formulaLauncher";
    launcher.className = "formula-launcher-btn";
    launcher.textContent = "Formula";
    launcher.hidden = true;
    document.body.appendChild(launcher);

    let zoomPercent = 100;
    let dragging = false;
    let dragOffsetX = 0;
    let dragOffsetY = 0;

    function applyZoom() {
      if (!iframe) {
        return;
      }
      iframe.src = `${pdfBaseUrl}#zoom=${zoomPercent}`;
      if (zoomResetBtn) {
        zoomResetBtn.textContent = `${zoomPercent}%`;
      }
    }

    function onMove(ev) {
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

    if (zoomInBtn) {
      zoomInBtn.addEventListener("click", () => {
        zoomPercent = clamp(zoomPercent + 10, 60, 240);
        applyZoom();
      });
    }
    if (zoomOutBtn) {
      zoomOutBtn.addEventListener("click", () => {
        zoomPercent = clamp(zoomPercent - 10, 60, 240);
        applyZoom();
      });
    }
    if (zoomResetBtn) {
      zoomResetBtn.addEventListener("click", () => {
        zoomPercent = 100;
        applyZoom();
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

    applyZoom();
  }

  window.initFormulaWidget = initFormulaWidget;
})();
