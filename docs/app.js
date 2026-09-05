// Kaartweergave van gebouwen met geregistreerde muurschilderingen.
// Laadt data/site/gebouwen.geojson (punten) en data/site/muurschilderingen.json
// (schilderingen per gebouw) statisch -- geen live SPARQL vanuit de browser.

const DATA_BASE = "data/site";

// Periode-emmers voor het histogramfilter. De grenzen volgen geen kunsthistorische
// canon maar de vraag die dit filter beantwoordt: is een schildering middeleeuws,
// vroegmodern/negentiende-eeuws, interbellum (opvallende piek in de data), of
// wederopbouw/post-65 (het onderscheid dat de RCE zelf hanteert tussen
// kleurhistorisch onderzoek en het post-65-specialisme).
const ERAS = [
  { id: "middeleeuwen", label: "≤1499", start: -9999, end: 1499 },
  { id: "1500-1799", label: "1500–1799", start: 1500, end: 1799 },
  { id: "1800-1919", label: "1800–1919", start: 1800, end: 1919 },
  { id: "interbellum", label: "1920–1944", start: 1920, end: 1944 },
  { id: "wederopbouw", label: "1945–1965", start: 1945, end: 1965 },
  { id: "post65", label: "1965–heden", start: 1966, end: 9999 },
];

const state = {
  gebouwen: null, // GeoJSON FeatureCollection
  schilderingenByGebouw: new Map(),
  zonderLocatie: [],
  map: null,
  markers: new Map(), // id -> maplibregl.Marker
  activeId: null,
  activeEras: new Set(), // leeg = geen periodefilter
  eraCache: new Map(), // gebouwId -> Set(era.id)
};

async function loadData() {
  state.gebouwen = { type: "FeatureCollection", features: [] }; // veilige fallback als de fetch hieronder faalt
  try {
    const [gebouwenRes, schilderingenRes, zonderLocatieRes] = await Promise.all([
      fetch(`${DATA_BASE}/gebouwen.geojson`),
      fetch(`${DATA_BASE}/muurschilderingen.json`),
      fetch(`${DATA_BASE}/gebouwen_zonder_locatie.json`),
    ]);
    if (!gebouwenRes.ok || !schilderingenRes.ok || !zonderLocatieRes.ok) throw new Error("dataload mislukt");
    state.gebouwen = await gebouwenRes.json();
    state.zonderLocatie = await zonderLocatieRes.json();
    const schilderingen = await schilderingenRes.json();
    for (const s of schilderingen) {
      if (!s.gebouw_id) continue;
      if (!state.schilderingenByGebouw.has(s.gebouw_id)) {
        state.schilderingenByGebouw.set(s.gebouw_id, []);
      }
      state.schilderingenByGebouw.get(s.gebouw_id).push(s);
    }
  } catch (err) {
    console.error("app.js: data laden mislukt", err);
  }
}

function initMap() {
  state.map = new maplibregl.Map({
    container: "map",
    style: "https://tiles.openfreemap.org/styles/liberty",
    center: [5.29, 52.1],
    zoom: 6.7,
  });
  state.map.addControl(new maplibregl.NavigationControl(), "top-left");
}

function periodOf(gebouwId) {
  const paintings = state.schilderingenByGebouw.get(gebouwId) || [];
  const years = [];
  for (const p of paintings) {
    if (p.datering?.van) years.push(parseInt(p.datering.van, 10));
    if (p.datering?.tot) years.push(parseInt(p.datering.tot, 10));
  }
  const valid = years.filter((y) => !isNaN(y));
  if (!valid.length) return null;
  return [Math.min(...valid), Math.max(...valid)];
}

function paintingYearRange(p) {
  const van = p.datering?.van ? parseInt(p.datering.van, 10) : NaN;
  const tot = p.datering?.tot ? parseInt(p.datering.tot, 10) : NaN;
  if (isNaN(van) && isNaN(tot)) return null;
  if (isNaN(van)) return [tot, tot];
  if (isNaN(tot)) return [van, van];
  return van <= tot ? [van, tot] : [tot, van];
}

function buildingEras(gebouwId) {
  if (state.eraCache.has(gebouwId)) return state.eraCache.get(gebouwId);
  const eras = new Set();
  for (const p of state.schilderingenByGebouw.get(gebouwId) || []) {
    const range = paintingYearRange(p);
    if (!range) continue;
    for (const era of ERAS) {
      if (range[0] <= era.end && range[1] >= era.start) eras.add(era.id);
    }
  }
  state.eraCache.set(gebouwId, eras);
  return eras;
}

function renderPeriodeFilter() {
  const counts = new Map(ERAS.map((e) => [e.id, 0]));
  for (const f of state.gebouwen.features) {
    for (const eraId of buildingEras(f.properties.id)) {
      counts.set(eraId, counts.get(eraId) + 1);
    }
  }
  const max = Math.max(1, ...counts.values());
  const wrap = document.getElementById("periode-filter");
  wrap.innerHTML = "";
  for (const era of ERAS) {
    const n = counts.get(era.id);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "periode-bar" + (state.activeEras.has(era.id) ? " active" : "");
    btn.title = `${era.label}: ${n} gebouw${n === 1 ? "" : "en"}`;
    const barHeight = Math.max(3, Math.round((n / max) * 44));
    btn.innerHTML = `<span class="bar" style="height:${barHeight}px"></span><span class="label">${era.label}</span>`;
    btn.addEventListener("click", () => {
      if (state.activeEras.has(era.id)) state.activeEras.delete(era.id);
      else state.activeEras.add(era.id);
      renderPeriodeFilter();
      renderMarkers();
    });
    wrap.appendChild(btn);
  }
}

function populateFunctieFilter() {
  const select = document.getElementById("f-functie");
  const seen = new Set();
  for (const f of state.gebouwen.features) {
    const fn = f.properties.huidige_functie;
    if (fn) seen.add(fn);
  }
  for (const fn of [...seen].sort()) {
    const opt = document.createElement("option");
    opt.value = fn;
    opt.textContent = fn;
    select.appendChild(opt);
  }
}

function matchesFilters(feature) {
  const q = document.getElementById("q").value.trim().toLowerCase();
  const functie = document.getElementById("f-functie").value;
  const rm = document.getElementById("f-rm").value;
  const p = feature.properties;
  if (q) {
    const hay = `${p.naam || ""} ${p.plaats || ""}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  if (functie && p.huidige_functie !== functie) return false;
  if (rm === "ja" && !p.rijksmonumentnummer) return false;
  if (rm === "nee" && p.rijksmonumentnummer) return false;
  if (state.activeEras.size) {
    const eras = buildingEras(p.id);
    if (![...state.activeEras].some((e) => eras.has(e))) return false;
  }
  return true;
}

function renderMarkers() {
  renderList();
  if (!state.map || !state.map.loaded()) return; // markers volgen zodra de kaartstijl geladen is
  for (const marker of state.markers.values()) marker.remove();
  state.markers.clear();

  for (const feature of state.gebouwen.features) {
    if (!matchesFilters(feature)) continue;
    const [lon, lat] = feature.geometry.coordinates;
    const el = document.createElement("div");
    const count = (state.schilderingenByGebouw.get(feature.properties.id) || []).length;
    el.style.width = "12px";
    el.style.height = "12px";
    el.style.borderRadius = "50%";
    el.style.background = feature.properties.rijksmonumentnummer ? "#8a2e2e" : "#b98b3e";
    el.style.border = "2px solid #fff";
    el.style.boxShadow = "0 0 0 1px rgba(0,0,0,0.25)";
    el.style.cursor = "pointer";
    el.title = `${feature.properties.naam} (${count} schildering${count === 1 ? "" : "en"})`;
    el.addEventListener("click", () => openDetail(feature.properties.id));

    const marker = new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(state.map);
    state.markers.set(feature.properties.id, marker);
  }
}

function renderList() {
  const list = document.getElementById("gebouw-list");
  list.innerHTML = "";

  if (!state.gebouwen.features.length) {
    document.getElementById("stats-line").textContent = "";
    list.innerHTML = '<p style="color:var(--ink-soft);padding:0.8rem 1rem;">Kon de gebouwenlijst niet laden. Controleer je verbinding en <a href="javascript:location.reload()">probeer opnieuw</a>.</p>';
    return;
  }

  const visible = state.gebouwen.features.filter(matchesFilters).sort((a, b) => (a.properties.naam || "").localeCompare(b.properties.naam || ""));

  document.getElementById("stats-line").textContent = `${visible.length} van ${state.gebouwen.features.length} gebouwen`;

  if (!visible.length) {
    list.innerHTML = '<p style="color:var(--ink-soft);padding:0.8rem 1rem;">Geen gebouwen gevonden met deze filters.</p>';
    return;
  }

  for (const feature of visible) {
    const p = feature.properties;
    const div = document.createElement("div");
    div.className = "gebouw-item" + (p.id === state.activeId ? " active" : "");
    const thumb = document.createElement("div");
    if (p.afbeelding) {
      thumb.className = "thumb";
      thumb.style.backgroundImage = `url(${p.afbeelding})`;
    } else {
      thumb.className = "thumb no-photo";
      thumb.textContent = "geen foto";
    }
    const meta = document.createElement("div");
    meta.className = "meta";
    const count = (state.schilderingenByGebouw.get(p.id) || []).length;
    meta.innerHTML = `<div class="naam">${escapeHtml(p.naam || "(zonder naam)")}</div><div class="plaats">${escapeHtml(p.plaats || "")} · ${count} schildering${count === 1 ? "" : "en"}</div>`;
    div.appendChild(thumb);
    div.appendChild(meta);
    div.addEventListener("click", () => {
      openDetail(p.id);
      const [lon, lat] = feature.geometry.coordinates;
      state.map.flyTo({ center: [lon, lat], zoom: Math.max(state.map.getZoom(), 13) });
      collapseSidebarOnMobile();
    });
    list.appendChild(div);
  }
}

function isMobile() {
  return window.matchMedia("(max-width: 760px)").matches;
}

function collapseSidebarOnMobile() {
  if (isMobile()) document.getElementById("sidebar").classList.remove("expanded");
}

function noPhotoPlaceholder() {
  if (Math.random() < 0.01) {
    return `<a class="no-photo ecce-homo" href="https://en.wikipedia.org/wiki/Ecce_Homo_(El%C3%ADas_Garc%C3%ADa_Mart%C3%ADnez)" target="_blank" rel="noopener" title="Ecce Homo, Borja (2012) — dit had ook kunnen gebeuren"><span class="emoji">🙈</span>oeps</a>`;
  }
  return '<div class="no-photo">nog geen foto beschikbaar</div>';
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function openDetail(gebouwId) {
  state.activeId = gebouwId;
  const feature = state.gebouwen.features.find((f) => f.properties.id === gebouwId);
  if (!feature) return;
  const p = feature.properties;
  const paintings = (state.schilderingenByGebouw.get(gebouwId) || []).sort(
    (a, b) => (parseInt(a.datering?.van) || 9999) - (parseInt(b.datering?.van) || 9999)
  );
  const period = periodOf(gebouwId);

  const links = [];
  if (p.monumentenregister_url) links.push([p.monumentenregister_url, "Monumentenregister"]);
  for (const uri of p.same_as || []) {
    if (uri.includes("wikidata.org")) links.push([uri, "Wikidata"]);
    else if (uri.includes("reliwiki")) links.push([uri, "Reliwiki"]);
  }

  const body = document.getElementById("detail-body");
  body.innerHTML = `
    <h2>${escapeHtml(p.naam || "(zonder naam)")}</h2>
    <div class="plaats-line">${escapeHtml(p.plaats || "")}${p.huidige_functie ? " · " + escapeHtml(p.huidige_functie) : ""}${period ? ` · schilderingen ${period[0]}–${period[1]}` : ""}</div>
    <div class="links">${links.map(([href, label]) => `<a href="${href}" target="_blank" rel="noopener">${label}</a>`).join("")}</div>
    <div id="painting-cards"></div>
  `;
  const cardsWrap = document.getElementById("painting-cards");
  if (!paintings.length) {
    cardsWrap.innerHTML = '<p style="color:var(--ink-soft);font-size:0.85rem;">Geen schilderingen gekoppeld aan dit gebouw in de brondata.</p>';
  }
  for (const s of paintings) {
    const card = document.createElement("div");
    card.className = "painting-card";
    const img = s.afbeelding?.square || s.afbeelding?.medium;
    const dat = s.datering?.van && s.datering?.tot
      ? (s.datering.van === s.datering.tot ? s.datering.van : `${s.datering.van}–${s.datering.tot}`)
      : (s.datering?.tekst || "");
    const tags = [...s.onderwerpen.map((o) => o.label || o.uri.split("/").pop()), ...s.materiaal, ...s.drager].filter(Boolean);
    const makerLine = (s.makers || [])
      .map((m) => `<a href="makers.html?maker=${encodeURIComponent(m.id)}">${escapeHtml((m.naam || "").replace(/^A\)\s*/, ""))}</a>`)
      .join(", ");
    card.innerHTML = `
      ${img ? `<img class="zoomable" src="${img}" loading="lazy" alt="" />` : noPhotoPlaceholder()}
      <div class="body">
        <div class="titel">${escapeHtml(s.titel || "(zonder titel)")}</div>
        ${dat ? `<div class="datering">${escapeHtml(String(dat))}</div>` : ""}
        ${s.locatieomschrijving ? `<div class="locatie">${escapeHtml(s.locatieomschrijving)}</div>` : ""}
        ${makerLine ? `<div class="maker">door ${makerLine}</div>` : ""}
        <div class="tags">${tags.slice(0, 6).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>
      </div>
    `;
    if (img) {
      card.querySelector("img").addEventListener("click", () => {
        openLightbox(
          [s.afbeelding?.origineel, s.afbeelding?.large, s.afbeelding?.medium, s.afbeelding?.square],
          s.titel || ""
        );
      });
    }
    cardsWrap.appendChild(card);
  }

  document.getElementById("detail").classList.add("open");
  renderList();
}

function closeDetail() {
  state.activeId = null;
  document.getElementById("detail").classList.remove("open");
  renderList();
}

function openZonderLocatie() {
  state.activeId = null;
  const body = document.getElementById("detail-body");
  const rows = state.zonderLocatie
    .slice()
    .sort((a, b) => (a.plaats || "").localeCompare(b.plaats || ""))
    .map(
      (g) =>
        `<div class="painting-card" style="align-items:flex-start;">
          <div class="body">
            <div class="titel">${escapeHtml(g.naam || "(zonder naam)")}</div>
            <div class="locatie">${escapeHtml(g.plaats || "")}${g.aantal_schilderingen ? ` · ${g.aantal_schilderingen} schildering${g.aantal_schilderingen === 1 ? "" : "en"} in de brondata` : ""}</div>
            <div class="links" style="margin-top:0.3rem;"><a href="${g.bron_item_url}" target="_blank" rel="noopener">bron</a>${g.rijksmonumentnummer ? `<a href="https://monumentenregister.cultureelerfgoed.nl/monumenten/${g.rijksmonumentnummer}" target="_blank" rel="noopener">monumentenregister</a>` : ""}</div>
          </div>
        </div>`
    )
    .join("");
  body.innerHTML = `
    <h2>Gebouwen zonder coördinaten</h2>
    <div class="plaats-line">${state.zonderLocatie.length} gebouwen hebben geen vindbare puntgeometrie (niet in de bron zelf, niet via rijksmonumentnummer, niet via een Reliwiki-adres) en staan daarom niet op de kaart. Hun schilderingen blijven wel bewaard in de dataset — zie de bronlink per gebouw hieronder.</div>
    ${rows}
  `;
  document.getElementById("detail").classList.add("open");
}

function surpriseMe() {
  const candidates = state.gebouwen.features.filter(
    (f) => (state.schilderingenByGebouw.get(f.properties.id) || []).length > 0
  );
  if (!candidates.length) return;
  const feature = candidates[Math.floor(Math.random() * candidates.length)];
  openDetail(feature.properties.id);
  const [lon, lat] = feature.geometry.coordinates;
  state.map.flyTo({ center: [lon, lat], zoom: Math.max(state.map.getZoom(), 13) });
  collapseSidebarOnMobile();
}

async function main() {
  initMap();
  await loadData();
  populateFunctieFilter();
  renderPeriodeFilter();
  renderMarkers(); // vult de lijst meteen; kaartmarkers volgen zodra de stijl geladen is
  state.map.on("load", renderMarkers);

  document.getElementById("q").addEventListener("input", renderMarkers);
  document.getElementById("f-functie").addEventListener("change", renderMarkers);
  document.getElementById("f-rm").addEventListener("change", renderMarkers);
  document.getElementById("detail-close").addEventListener("click", closeDetail);

  const handle = document.getElementById("sidebar-handle");
  const toggleSidebar = () => document.getElementById("sidebar").classList.toggle("expanded");
  handle.addEventListener("click", toggleSidebar);
  handle.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleSidebar(); }
  });

  document.getElementById("surprise-btn").addEventListener("click", surpriseMe);

  if (state.zonderLocatie.length) {
    const btn = document.getElementById("zonder-locatie-btn");
    btn.style.display = "block";
    btn.textContent = `+ ${state.zonderLocatie.length} gebouwen zonder coördinaten →`;
    btn.addEventListener("click", openZonderLocatie);
  }

  const params = new URLSearchParams(location.search);
  if (params.get("gebouw")) openDetail(params.get("gebouw"));
}

main();
