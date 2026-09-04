// Kaartweergave van gebouwen met geregistreerde muurschilderingen.
// Laadt data/site/gebouwen.geojson (punten) en data/site/muurschilderingen.json
// (schilderingen per gebouw) statisch -- geen live SPARQL vanuit de browser.

const DATA_BASE = "data/site";

const state = {
  gebouwen: null, // GeoJSON FeatureCollection
  schilderingenByGebouw: new Map(),
  zonderLocatie: [],
  map: null,
  markers: new Map(), // id -> maplibregl.Marker
  activeId: null,
};

async function loadData() {
  const [gebouwenRes, schilderingenRes, zonderLocatieRes] = await Promise.all([
    fetch(`${DATA_BASE}/gebouwen.geojson`),
    fetch(`${DATA_BASE}/muurschilderingen.json`),
    fetch(`${DATA_BASE}/gebouwen_zonder_locatie.json`),
  ]);
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
  const visible = state.gebouwen.features.filter(matchesFilters).sort((a, b) => (a.properties.naam || "").localeCompare(b.properties.naam || ""));

  document.getElementById("stats-line").textContent = `${visible.length} van ${state.gebouwen.features.length} gebouwen`;

  for (const feature of visible) {
    const p = feature.properties;
    const div = document.createElement("div");
    div.className = "gebouw-item" + (p.id === state.activeId ? " active" : "");
    const thumb = document.createElement("div");
    thumb.className = "thumb";
    if (p.afbeelding) thumb.style.backgroundImage = `url(${p.afbeelding})`;
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
    });
    list.appendChild(div);
  }
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
    card.innerHTML = `
      ${img ? `<img src="${img}" loading="lazy" alt="" />` : '<div style="width:84px;height:84px;border-radius:6px;background:var(--line);flex-shrink:0;"></div>'}
      <div class="body">
        <div class="titel">${escapeHtml(s.titel || "(zonder titel)")}</div>
        ${dat ? `<div class="datering">${escapeHtml(String(dat))}</div>` : ""}
        ${s.locatieomschrijving ? `<div class="locatie">${escapeHtml(s.locatieomschrijving)}</div>` : ""}
        <div class="tags">${tags.slice(0, 6).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>
      </div>
    `;
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
    <div class="plaats-line">${state.zonderLocatie.length} gebouwen in de brondata hebben geen puntgeometrie (eigen noch via rijksmonumentnummer) en staan daarom niet op de kaart. Hun schilderingen blijven wel bewaard in de dataset.</div>
    ${rows}
  `;
  document.getElementById("detail").classList.add("open");
}

async function main() {
  initMap();
  await loadData();
  populateFunctieFilter();
  renderMarkers(); // vult de lijst meteen; kaartmarkers volgen zodra de stijl geladen is
  state.map.on("load", renderMarkers);

  document.getElementById("q").addEventListener("input", renderMarkers);
  document.getElementById("f-functie").addEventListener("change", renderMarkers);
  document.getElementById("f-rm").addEventListener("change", renderMarkers);
  document.getElementById("detail-close").addEventListener("click", closeDetail);

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
