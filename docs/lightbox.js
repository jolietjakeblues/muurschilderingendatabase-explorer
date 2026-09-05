// Kleine gedeelde lightbox voor kaart- en iconografiepagina: klik op een
// schilderingthumbnail voor de grote/originele foto op zwarte achtergrond.
// Geen IIIF beschikbaar bij de bron (geverifieerd -- geen /iiif/-endpoints,
// geen o-module-iiifserver-velden in de item-/media-API), dus dit is het
// beste haalbare zonder deep-zoom-tegels: de grootste beschikbare
// Omeka-afgeleide (of het originele bestand, als dat lukt).

(function () {
  let overlay, imgEl, captionEl, loadingEl;

  function build() {
    if (overlay) return;
    overlay = document.createElement("div");
    overlay.id = "lightbox";
    overlay.innerHTML = `
      <button class="lightbox-close" aria-label="Sluiten">✕</button>
      <div class="lightbox-loading">laden…</div>
      <img class="lightbox-img" alt="" />
      <div class="lightbox-caption"></div>
    `;
    document.body.appendChild(overlay);
    imgEl = overlay.querySelector(".lightbox-img");
    captionEl = overlay.querySelector(".lightbox-caption");
    loadingEl = overlay.querySelector(".lightbox-loading");

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    overlay.querySelector(".lightbox-close").addEventListener("click", close);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && overlay.classList.contains("open")) close();
    });
  }

  function open(urls, caption) {
    build();
    // urls: array van kandidaat-URL's, beste eerst (origineel > large > medium).
    // Bij een 404/laadfout (o.a. bij zeer oude/verhuisde bestanden) volgende proberen.
    const candidates = (Array.isArray(urls) ? urls : [urls]).filter(Boolean);
    if (!candidates.length) return;
    let i = 0;
    imgEl.style.display = "none";
    loadingEl.style.display = "block";
    captionEl.textContent = caption || "";
    overlay.classList.add("open");
    document.body.style.overflow = "hidden";

    function tryNext() {
      if (i >= candidates.length) {
        loadingEl.textContent = "afbeelding kon niet geladen worden";
        return;
      }
      const url = candidates[i++];
      imgEl.onload = () => {
        loadingEl.style.display = "none";
        imgEl.style.display = "block";
      };
      imgEl.onerror = tryNext;
      imgEl.src = url;
    }
    tryNext();
  }

  function close() {
    overlay.classList.remove("open");
    document.body.style.overflow = "";
    imgEl.src = "";
  }

  window.openLightbox = open;
})();
