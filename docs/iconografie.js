// Iconografie-browser: elk item in data/site/onderwerpen.json is een
// Wikidata-onderwerp (schema:about op een schema:Painting) met het aantal
// gekoppelde schilderingen. Klikken toont de schilderingen zelf uit
// data/site/muurschilderingen.json, met link terug naar de kaart.

const DATA_BASE = "data/site";
let onderwerpen = [];
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

function placeholderThumb(label) {
  const initial = (label || "?").trim().charAt(0).toUpperCase();
  return `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="#ddd5c7"/><text x="100" y="112" font-size="72" text-anchor="middle" fill="#5c554c" font-family="Georgia,serif">${initial}</text></svg>`
  )}`;
}

function renderGrid(filterText) {
  const grid = document.getElementById("icono-grid");
  grid.innerHTML = "";
  const q = (filterText || "").trim().toLowerCase();
  const visible = onderwerpen.filter((o) => !q || (o.label || "").toLowerCase().includes(q));

  if (!onderwerpen.length) {
    grid.innerHTML = '<p style="color:var(--ink-soft);">Kon de onderwerpenlijst niet laden. Controleer je verbinding en <a href="javascript:location.reload()">probeer opnieuw</a>.</p>';
    return;
  }
  if (!visible.length) {
    grid.innerHTML = `<p style="color:var(--ink-soft);">Geen onderwerpen gevonden${q ? ` voor "${escapeHtml(filterText.trim())}"` : ""}.</p>`;
    return;
  }
  for (const o of visible) {
    const card = document.createElement("div");
    card.className = "icono-card";
    const thumb = document.createElement("div");
    thumb.className = "thumb";
    thumb.style.backgroundImage = `url(${o.afbeelding || placeholderThumb(o.label)})`;
    const info = document.createElement("div");
    info.className = "info";
    info.innerHTML = `<div class="label">${escapeHtml(o.label || o.uri.split("/").pop())}</div><div class="count">${o.schildering_ids.length} schildering${o.schildering_ids.length === 1 ? "" : "en"}</div>`;
    card.appendChild(thumb);
    card.appendChild(info);
    card.addEventListener("click", () => showSubject(o));
    grid.appendChild(card);
  }
}

function showSubject(o) {
  const detail = document.getElementById("icono-detail");
  detail.classList.add("open");
  const paintings = o.schildering_ids.map((id) => schilderingenById.get(id)).filter(Boolean);
  detail.innerHTML = `
    <h2 style="margin:0 0 0.2rem;">${escapeHtml(o.label || o.uri.split("/").pop())}</h2>
    <div style="font-size:0.82rem;color:var(--ink-soft);">
      ${paintings.length} schildering${paintings.length === 1 ? "" : "en"} ·
      <a href="${o.uri}" target="_blank" rel="noopener">Wikidata</a>
    </div>
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
  try {
    const [onderwerpenRes, schilderingenRes, gebouwenRes] = await Promise.all([
      fetch(`${DATA_BASE}/onderwerpen.json`),
      fetch(`${DATA_BASE}/muurschilderingen.json`),
      fetch(`${DATA_BASE}/gebouwen.geojson`),
    ]);
    if (!onderwerpenRes.ok || !schilderingenRes.ok || !gebouwenRes.ok) throw new Error("dataload mislukt");
    onderwerpen = await onderwerpenRes.json();
    const schilderingen = await schilderingenRes.json();
    for (const s of schilderingen) schilderingenById.set(s.id, s);
    const gebouwen = await gebouwenRes.json();
    for (const f of gebouwen.features) gebouwenById.set(f.properties.id, f.properties);
  } catch (err) {
    console.error("iconografie.js: data laden mislukt", err);
  }

  renderGrid("");
  document.getElementById("icono-q").addEventListener("input", (e) => renderGrid(e.target.value));
  document.getElementById("surprise-btn").addEventListener("click", () => {
    const pick = onderwerpen[Math.floor(Math.random() * onderwerpen.length)];
    if (pick) showSubject(pick);
  });
}

main();
