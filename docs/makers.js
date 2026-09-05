// Makers-browser: elk item in data/site/makers.json is een persoon of
// organisatie (schema:Person/Organization, gekoppeld via dcterms:creator)
// met het aantal gekoppelde schilderingen. Klikken toont de schilderingen
// zelf uit data/site/muurschilderingen.json, met link terug naar de kaart.

const DATA_BASE = "data/site";
let makers = [];
let schilderingenById = new Map();
let gebouwenById = new Map();

function noPhotoPlaceholder() {
  if (Math.random() < 0.01) {
    return `<a class="no-photo ecce-homo" href="https://en.wikipedia.org/wiki/Ecce_Homo_(El%C3%ADas_Garc%C3%ADa_Mart%C3%ADnez)" target="_blank" rel="noopener" title="Ecce Homo, Borja (2012) — dit had ook kunnen gebeuren"><span class="emoji">🙈</span>oeps</a>`;
  }
  return '<div class="no-photo">nog geen foto beschikbaar</div>';
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function placeholderThumb(label, type) {
  const initial = (label || "?").trim().charAt(0).toUpperCase();
  const bg = type === "organisatie" ? "#c9b79c" : "#ddd5c7";
  return `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="${bg}"/><text x="100" y="112" font-size="72" text-anchor="middle" fill="#5c554c" font-family="Georgia,serif">${initial}</text></svg>`
  )}`;
}

function lifeSpan(m) {
  if (!m.geboorte && !m.sterfte) return "";
  const jaar = (d) => (d ? d.slice(0, 4) : "?");
  return `${jaar(m.geboorte)}–${jaar(m.sterfte)}`;
}

function isAnoniem(naam) {
  return /anoniem/i.test(naam || "");
}

function renderGrid(filterText, typeFilter) {
  const grid = document.getElementById("icono-grid");
  grid.innerHTML = "";
  const q = (filterText || "").trim().toLowerCase();
  const visible = makers
    .filter((m) => !typeFilter || m.type === typeFilter)
    .filter((m) => !q || (m.naam || "").toLowerCase().includes(q));

  if (!makers.length) {
    grid.innerHTML = '<p style="color:var(--ink-soft);">Kon de makerslijst niet laden. Controleer je verbinding en <a href="javascript:location.reload()">probeer opnieuw</a>.</p>';
    return;
  }
  if (!visible.length) {
    grid.innerHTML = `<p style="color:var(--ink-soft);">Geen makers gevonden${q ? ` voor "${escapeHtml(filterText.trim())}"` : ""}.</p>`;
    return;
  }
  for (const m of visible) {
    const card = document.createElement("div");
    card.className = "icono-card";
    const thumb = document.createElement("div");
    thumb.className = "thumb";
    thumb.style.backgroundImage = `url(${placeholderThumb(m.naam, m.type)})`;
    const info = document.createElement("div");
    info.className = "info";
    const span = lifeSpan(m);
    info.innerHTML = `
      <div class="label">${escapeHtml(m.naam || "(onbekend)")}</div>
      <div class="count">${span ? span + " · " : ""}${m.schildering_ids.length} schildering${m.schildering_ids.length === 1 ? "" : "en"}${m.type === "organisatie" ? " · organisatie" : ""}</div>
    `;
    card.appendChild(thumb);
    card.appendChild(info);
    card.addEventListener("click", () => showMaker(m));
    grid.appendChild(card);
  }
  const intro = document.getElementById("makers-intro");
  if (intro) {
    const totaal = makers.length;
    const personen = makers.filter((m) => m.type === "persoon" && !isAnoniem(m.naam)).length;
    intro.textContent = `${totaal} makers met minstens één gekoppelde schildering, waarvan ${personen} bij naam bekende kunstenaars/restaurateurs (de rest: organisaties of niet nader geïdentificeerde makers).`;
  }
}

function showMaker(m) {
  const detail = document.getElementById("icono-detail");
  detail.classList.add("open");
  const paintings = m.schildering_ids.map((id) => schilderingenById.get(id)).filter(Boolean);
  const span = lifeSpan(m);
  const links = (m.same_as || []).map((uri) => {
    const label = uri.includes("wikidata.org") ? "Wikidata" : uri.includes("rkd.nl") ? "RKD" : "bron";
    return `<a href="${uri}" target="_blank" rel="noopener">${label}</a>`;
  });
  detail.innerHTML = `
    <h2 style="margin:0 0 0.2rem;">${escapeHtml(m.naam || "(onbekend)")}</h2>
    <div style="font-size:0.82rem;color:var(--ink-soft);">
      ${span ? span + " · " : ""}${paintings.length} schildering${paintings.length === 1 ? "" : "en"}${m.type === "organisatie" ? " · organisatie" : ""}
      ${links.length ? " · " + links.join(" · ") : ""}
    </div>
    ${m.beschrijving ? `<p style="font-size:0.85rem;max-width:70ch;">${escapeHtml(m.beschrijving)}</p>` : ""}
    <div class="gallery"></div>
  `;
  const gallery = detail.querySelector(".gallery");
  for (const s of paintings) {
    const gebouw = gebouwenById.get(s.gebouw_id);
    const img = s.afbeelding?.square || s.afbeelding?.medium;
    const fig = document.createElement("figure");
    const gebouwLink = gebouw ? `<a href="index.html?gebouw=${encodeURIComponent(gebouw.id)}">${escapeHtml(gebouw.naam || gebouw.plaats || "")}</a>` : "";
    fig.innerHTML = `
      ${img ? `<img class="zoomable" src="${img}" loading="lazy" alt="" />` : noPhotoPlaceholder()}
      <figcaption>${escapeHtml(s.titel || "")}${gebouwLink ? " — " + gebouwLink : ""}</figcaption>
    `;
    if (img) {
      fig.querySelector("img").addEventListener("click", () => {
        openLightbox(
          [s.afbeelding?.origineel, s.afbeelding?.large, s.afbeelding?.medium, s.afbeelding?.square],
          s.titel || ""
        );
      });
    }
    gallery.appendChild(fig);
  }
  detail.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function main() {
  const rerender = () =>
    renderGrid(document.getElementById("icono-q").value, document.getElementById("maker-type-filter").value);

  try {
    const [makersRes, schilderingenRes, gebouwenRes] = await Promise.all([
      fetch(`${DATA_BASE}/makers.json`),
      fetch(`${DATA_BASE}/muurschilderingen.json`),
      fetch(`${DATA_BASE}/gebouwen.geojson`),
    ]);
    if (!makersRes.ok || !schilderingenRes.ok || !gebouwenRes.ok) throw new Error("dataload mislukt");
    makers = await makersRes.json();
    const schilderingen = await schilderingenRes.json();
    for (const s of schilderingen) schilderingenById.set(s.id, s);
    const gebouwen = await gebouwenRes.json();
    for (const f of gebouwen.features) gebouwenById.set(f.properties.id, f.properties);
  } catch (err) {
    console.error("makers.js: data laden mislukt", err);
  }

  rerender();
  document.getElementById("icono-q").addEventListener("input", rerender);
  document.getElementById("maker-type-filter").addEventListener("change", rerender);
  document.getElementById("surprise-btn").addEventListener("click", () => {
    const pick = makers[Math.floor(Math.random() * makers.length)];
    if (pick) showMaker(pick);
  });

  const params = new URLSearchParams(location.search);
  if (params.get("maker")) {
    const m = makers.find((x) => x.id === params.get("maker"));
    if (m) showMaker(m);
  }
}

main();
