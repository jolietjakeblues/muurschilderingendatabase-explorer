#!/usr/bin/env python3
"""
Bouw de statische dataset voor de Muurschilderingendatabase-explorer.

Bronnen:
  1. RCE Linked Data Voorziening, dataset "Muurschilderingen" (SPARQL) --
     gebouwen en schilderingen, queries/gebouwen.sparql en
     queries/paintings.sparql.
  2. RCE Linked Data Voorziening, dataset "cho" (SPARQL) -- skos:prefLabel
     voor de materiaal-/drager-thesaurusconcepten die in (1) alleen als URI
     voorkomen.
  3. Wikidata Query Service (SPARQL) -- labels (en, waar aanwezig, een
     representatieve afbeelding P18) voor de iconografische onderwerpen
     (schema:about), die in (1) alleen als wikidata-URI voorkomen.
  4. muurschilderingendatabase.nl/api/media (Omeka S REST, geen SPARQL) --
     de SPARQL-graph bevat alleen media-URI's, geen thumbnail/origineel-URLs;
     die REST-API wel. Volledig gepagineerd opgehaald or o:item (de
     schildering of het gebouw) gekoppeld.
  5. PDOK Locatieserver (BAG-adressen, REST) -- laatste redmiddel voor
     gebouwen zonder eigen coördinaat en zonder (vindbaar) rijksmonument:
     een deel heeft wel een Reliwiki-link met adres erin (schema:sameAs),
     dat adres geocoderen we hiermee.

Schrijft data/raw/*.json (ruwe extracts, voor herleidbaarheid) en
data/site/*.json + gebouwen.geojson (het datamodel dat de viewer laadt).

Geen live queries vanuit de browser: alles hier voorgebakken, zelfde
architectuurkeuze als het dodenakkers-project waar dit uit voortkomt.
"""
from __future__ import annotations

import json
import math
import re
import sys
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

MUUR_ENDPOINT = "https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Muurschilderingen/sparql"
CHO_ENDPOINT = "https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/cho/sparql"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
OMEKA_MEDIA_API = "https://muurschilderingendatabase.nl/api/media"
PDOK_LOCATIESERVER = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"

REPO_ROOT = Path(__file__).resolve().parent.parent
QUERIES_DIR = REPO_ROOT / "queries"
RAW_DIR = REPO_ROOT / "data" / "raw"
SITE_DIR = REPO_ROOT / "docs" / "data" / "site"

HEADERS_SPARQL = {"Accept": "application/sparql-results+json"}
HEADERS_UA = {"User-Agent": "muurschilderingendatabase-explorer/0.1 (build script; GitHub Pages viewer)"}


def run_sparql(endpoint: str, query: str) -> list[dict]:
    resp = requests.post(endpoint, data={"query": query}, headers={**HEADERS_SPARQL, **HEADERS_UA}, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    rows = []
    for binding in data["results"]["bindings"]:
        row = {var: val["value"] for var, val in binding.items()}
        rows.append(row)
    return rows


def fetch_muur_rows(name: str) -> list[dict]:
    query = (QUERIES_DIR / f"{name}.sparql").read_text(encoding="utf-8")
    rows = run_sparql(MUUR_ENDPOINT, query)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{name}: {len(rows)} rijen uit SPARQL")
    return rows


# --------------------------------------------------------------------------
# Groeperen van multi-valued SPARQL-rijen tot 1 record per subject.
# --------------------------------------------------------------------------

def group_by_subject(rows: list[dict], subject_key: str, single_fields: list[str], multi_fields: list[str]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for row in rows:
        s = row[subject_key]
        entry = grouped.setdefault(s, {"uri": s, **{f: None for f in single_fields}, **{f: set() for f in multi_fields}})
        for f in single_fields:
            if entry[f] is None and row.get(f):
                entry[f] = row[f]
        for f in multi_fields:
            if row.get(f):
                entry[f].add(row[f])
    for entry in grouped.values():
        for f in multi_fields:
            entry[f] = sorted(entry[f])
    return grouped


# --------------------------------------------------------------------------
# Coördinaten: geen lat/lon-onderscheid in het predicate zelf, dus op
# waardebereik classificeren (dataset is Nederland-only).
# --------------------------------------------------------------------------

def split_lat_lon(coords: list[str]) -> tuple[float, float] | None:
    values = [float(c) for c in coords]
    lat = next((v for v in values if 50.0 <= v <= 54.0), None)
    lon = next((v for v in values if 3.0 <= v <= 7.6), None)
    if lat is None or lon is None:
        return None
    return lat, lon


# --------------------------------------------------------------------------
# Thesaurus- en Wikidata-labels.
# --------------------------------------------------------------------------

def fetch_concept_labels(uris: set[str]) -> dict[str, str]:
    """uris kan ook losse tekstwaarden bevatten (bv. 'kalk', 'waskrijt?') i.p.v.
    thesaurus-URI's -- artMedium/artworkSurface zijn in de brondata niet
    consequent altijd concepten. Alleen echte http(s)-URI's opzoeken; de rest
    komt ongewijzigd terug via de aanroeper se concept_labels.get(u, u)."""
    uris = {u for u in uris if u.startswith("http://") or u.startswith("https://")}
    if not uris:
        return {}
    values = " ".join(f"<{u}>" for u in uris)
    query = f"""
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?concept ?label WHERE {{
  VALUES ?concept {{ {values} }}
  ?concept skos:prefLabel ?label .
  FILTER(lang(?label) = "nl" || lang(?label) = "")
}}"""
    rows = run_sparql(CHO_ENDPOINT, query)
    labels = {}
    for row in rows:
        labels.setdefault(row["concept"], row["label"])
    print(f"thesaurus-labels: {len(labels)}/{len(uris)} gevonden")
    return labels


def fetch_wikidata_labels(uris: set[str]) -> dict[str, dict]:
    """Label (nl, fallback en) + optionele afbeelding (P18) per wikidata-entiteit."""
    qids = [u for u in uris if u.startswith("http://www.wikidata.org/entity/")]
    if not qids:
        return {}
    result: dict[str, dict] = {}
    batch_size = 150
    for i in range(0, len(qids), batch_size):
        batch = qids[i : i + batch_size]
        values = " ".join(f"<{u}>" for u in batch)
        query = f"""
SELECT ?item ?label ?image WHERE {{
  VALUES ?item {{ {values} }}
  OPTIONAL {{ ?item rdfs:label ?label . FILTER(lang(?label) = "nl") }}
  OPTIONAL {{ ?item rdfs:label ?labelEn . FILTER(lang(?labelEn) = "en") }}
  OPTIONAL {{ ?item <http://www.wikidata.org/prop/direct/P18> ?image }}
  BIND(COALESCE(?label, ?labelEn) AS ?label)
}}"""
        rows = run_sparql(WIKIDATA_ENDPOINT, query)
        for row in rows:
            entry = result.setdefault(row["item"], {"label": None, "image": None})
            if row.get("label"):
                entry["label"] = row["label"]
            if row.get("image"):
                entry["image"] = row["image"]
    print(f"wikidata-labels: {len(result)}/{len(qids)} entiteiten")
    return result


# --------------------------------------------------------------------------
# Omeka REST: volledige mediacatalogus pagineren, item_id -> [media].
# --------------------------------------------------------------------------

def fetch_all_media() -> dict[str, list[dict]]:
    by_item: dict[str, list[dict]] = defaultdict(list)
    page = 1
    per_page = 100
    total = None
    while True:
        resp = requests.get(
            OMEKA_MEDIA_API, params={"page": page, "per_page": per_page}, headers=HEADERS_UA, timeout=60
        )
        resp.raise_for_status()
        batch = resp.json()
        if total is None:
            total = resp.headers.get("Omeka-S-Total-Results")
            print(f"media: {total} stuks te pagineren")
        if not batch:
            break
        for m in batch:
            item = m.get("o:item")
            if not item:
                continue
            item_id = str(item["o:id"])
            thumbs = m.get("o:thumbnail_urls") or {}
            by_item[item_id].append(
                {
                    "titel": m.get("o:title"),
                    "origineel": m.get("o:original_url"),
                    "large": thumbs.get("large"),
                    "medium": thumbs.get("medium"),
                    "square": thumbs.get("square"),
                    "bron": m.get("o:source"),
                }
            )
        if len(batch) < per_page:
            break
        page += 1
    print(f"media gekoppeld aan {len(by_item)} items")
    return dict(by_item)


WKT_POINT_RE = re.compile(r"Point\s*\(([-\d.]+)\s+([-\d.]+)\)", re.IGNORECASE)
WKT_VERTEX_RE = re.compile(r"[-\d.]+\s+[-\d.]+")


def wkt_centroid_latlon(wkt: str) -> tuple[float, float] | None:
    """Simpel gemiddelde van alle vertices -- geen echte geometrische centroid
    (geen shapely-dependency in dit script), maar voor een kaartmarker (geen
    oppervlakteberekening) is dat voldoende nauwkeurig."""
    m = WKT_POINT_RE.search(wkt)
    if m:
        lon, lat = float(m.group(1)), float(m.group(2))
        return lat, lon
    verts = [tuple(map(float, v.split())) for v in WKT_VERTEX_RE.findall(wkt)]
    if not verts:
        return None
    lon = sum(v[0] for v in verts) / len(verts)
    lat = sum(v[1] for v in verts) / len(verts)
    return lat, lon


def fetch_rm_centroids(rm_numbers: set[str]) -> dict[str, tuple[float, float]]:
    """Fallback-geometrie voor gebouwen zonder eigen mapping-coördinaat: haalt
    de rijksmonumentgeometrie op via een exacte VALUES-join op
    rijksmonumentnummer (geen sfWithin/sfIntersects nodig, dus geen risico op
    de timeouts die dat op dit Virtuoso-endpoint geeft bij grote scans)."""
    if not rm_numbers:
        return {}
    values = " ".join(f'"{n}"' for n in rm_numbers)
    query = f"""
PREFIX ceo: <https://linkeddata.cultureelerfgoed.nl/def/ceo#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
SELECT ?rm ?wkt WHERE {{
  GRAPH <https://linkeddata.cultureelerfgoed.nl/graph/instanties-rce> {{
    VALUES ?rm {{ {values} }}
    ?cho a ceo:Rijksmonument ; ceo:rijksmonumentnummer ?rm ; ceo:heeftGeometrie ?geom .
  }}
  ?geom geo:asWKT ?wkt .
}}"""
    rows = run_sparql(CHO_ENDPOINT, query)
    result: dict[str, tuple[float, float]] = {}
    for row in rows:
        if row["rm"] in result:
            continue
        latlon = wkt_centroid_latlon(row["wkt"])
        if latlon:
            result[row["rm"]] = latlon
    print(f"rijksmonument-centroids als fallback-geometrie: {len(result)}/{len(rm_numbers)} gevonden")
    return result


RELIWIKI_ADDRESS_RE = re.compile(r"/index\.php/[^,]*,(?P<rest>.+)$")


def reliwiki_address(url: str) -> str | None:
    """Reliwiki-URL's coderen 'Plaats,_Straat_Nr_-_Kerknaam' -- pak het
    straat+nr-deel voor v e n een adres. De plaatsnaam halen we niet uit de
    URL (bij namen met een apostrof, zoals 's-Gravenhage, staat die er
    verminkt in); we gebruiken in plaats daarvan het al bekende
    woonplaats-veld van het gebouw zelf."""
    m = RELIWIKI_ADDRESS_RE.search(urllib.parse.unquote(url))
    if not m:
        return None
    rest = m.group("rest").replace("_", " ").strip()
    if " - " not in rest:
        return None
    return rest.split(" - ")[0].strip()


def geocode_pdok(query: str) -> tuple[float, float] | None:
    resp = requests.get(PDOK_LOCATIESERVER, params={"q": query, "rows": 1}, headers=HEADERS_UA, timeout=15)
    resp.raise_for_status()
    docs = resp.json()["response"]["docs"]
    if not docs:
        return None
    m = WKT_POINT_RE.search(docs[0]["centroide_ll"])
    if not m:
        return None
    lon, lat = float(m.group(1)), float(m.group(2))
    return lat, lon


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


PLAUSIBILITEITSGRENS_KM = 30.0


def fetch_plaats_candidates(plaatsen: set[str]) -> dict[str, list[tuple[float, float]]]:
    """Woonplaats-centroïden per plaatsnaam, om de eigen coördinaat van een
    gebouw op plausibiliteit te toetsen (zie PLAUSIBILITEITSGRENS_KM
    hieronder) -- de brondatabase blijkt bij een enkel gebouw een coördinaat
    honderden kilometers verkeerd te hebben (bv. 'Ameide' en 'Molenhoek' die
    in België belandden), zonder dat daar in de data zelf een signaal voor
    is.

    PDOK's fq=type:woonplaats is een vrije-tekstzoekopdracht, geen exacte
    match: voor plaatsnamen die geen eigen BAG-woonplaats zijn (een wijk als
    'Amsterdam-Zuid', of -- databronfout -- een kerknaam in het
    woonplaats-veld) geeft het een compleet ongerelateerd "best passend"
    resultaat terug, wat zonder verdere check valse positieven oplevert.
    Daarom hier alleen kandidaten bewaren waarvan woonplaatsnaam exact (case-
    insensitive) overeenkomt met de gevraagde naam; per plaats kunnen dat er
    ook meerdere zijn (Elsloo bestaat zowel in Limburg als in Friesland) --
    de aanroeper kiest per gebouw de dichtstbijzijnde kandidaat."""
    result: dict[str, list[tuple[float, float]]] = {}
    for plaats in plaatsen:
        if not plaats:
            continue
        try:
            resp = requests.get(
                PDOK_LOCATIESERVER,
                params={"q": plaats, "fq": "type:woonplaats", "rows": 10},
                headers=HEADERS_UA,
                timeout=15,
            )
            resp.raise_for_status()
            docs = resp.json()["response"]["docs"]
        except requests.RequestException:
            continue
        candidates = []
        plaats_norm = plaats.strip().lower()
        for doc in docs:
            naam_norm = (doc.get("woonplaatsnaam") or "").strip().lower()
            # exact, of een BAG-disambiguatiesuffix zoals "Beuningen Gld"
            # voor het Gelderse Beuningen (i.t.t. het gelijknamige Beuningen
            # in Overijssel) -- de spatie voorkomt dat dit toevallig ook
            # woorddelen matcht (bv. "Beek" mag geen "Beekbergen" matchen).
            if naam_norm != plaats_norm and not naam_norm.startswith(plaats_norm + " "):
                continue
            m = WKT_POINT_RE.search(doc["centroide_ll"])
            if m:
                candidates.append((float(m.group(2)), float(m.group(1))))
        if candidates:
            result[plaats] = candidates
    print(f"plaatsen met exacte woonplaats-match voor plausibiliteitscheck: {len(result)}/{len(plaatsen)}")
    return result


def fetch_reliwiki_geocodes(candidates: list[tuple[str, str, str]]) -> dict[str, tuple[float, float]]:
    """candidates: (gebouw_uri, reliwiki_url, woonplaats). Eén PDOK-call per
    kandidaat (klein aantal, geen bulk-endpoint beschikbaar)."""
    result: dict[str, tuple[float, float]] = {}
    for gebouw_uri, reliwiki_url, plaats in candidates:
        addr = reliwiki_address(reliwiki_url)
        if not addr:
            continue
        try:
            latlon = geocode_pdok(f"{addr}, {plaats or ''}".strip(", "))
        except requests.RequestException:
            continue
        if latlon:
            result[gebouw_uri] = latlon
    print(f"reliwiki-adressen gegeocodeerd via PDOK: {len(result)}/{len(candidates)}")
    return result


def clean_year(value: str | None) -> str | None:
    """De bron gebruikt '0' als sentinel voor 'geen datering bekend', niet
    een letterlijk jaar 0 (geen Nederlandse kerk dateert uit 0-99 n.Chr.) --
    geverifieerd op de 20 rijen die dit raken, zie docs/methode.md."""
    return None if value == "0" else value


def item_id_from_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    m = re.search(r"/items/(\d+)$", uri)
    return m.group(1) if m else None


# --------------------------------------------------------------------------
# Main build
# --------------------------------------------------------------------------

def main() -> None:
    gebouw_rows = fetch_muur_rows("gebouwen")
    painting_rows = fetch_muur_rows("paintings")

    gebouwen = group_by_subject(
        gebouw_rows,
        "s",
        single_fields=["titel", "identifier", "rijksmonumentnummer", "woonplaats", "huidigeFunctie", "bouwgeschiedenis", "restauratiegeschiedenis"],
        multi_fields=["sameAs", "coord"],
    )
    # Bronfout: een handvol schema:temporal-waarden zijn per ongeluk een
    # item-URL i.p.v. vrije tekst (kennelijk een verkeerd ingevoerd veld in
    # de brondatabase). group_by_subject pakt de eerste niet-lege waarde per
    # veld, dus zo'n URL kan de echte tekst ("zie bij RM11681MU1") verdringen
    # afhankelijk van SPARQL-rijvolgorde. Filter die stray URL's hier weg
    # i.p.v. de generieke groepeerfunctie hiervoor aan te passen.
    for row in painting_rows:
        if row.get("temporeel", "").startswith("https://muurschilderingendatabase.nl/api/items/"):
            row["temporeel"] = None

    paintings = group_by_subject(
        painting_rows,
        "s",
        single_fields=["titel", "beschrijving", "identifier", "gebouw", "begin", "eind", "temporeel", "locatieomschrijving", "onderdeelVan", "spatial", "primaryMedia"],
        multi_fields=["genre", "about", "medium", "surface"],
    )

    concept_uris = set()
    subject_uris = set()
    for p in paintings.values():
        concept_uris.update(p["medium"])
        concept_uris.update(p["surface"])
        subject_uris.update(p["about"])
    concept_labels = fetch_concept_labels(concept_uris)
    subject_labels = fetch_wikidata_labels(subject_uris)

    media_by_item = fetch_all_media()

    # Eigen coördinaat plausibiliteitschecken tegen de woonplaats: de bron
    # blijkt bij een enkel gebouw een coördinaat honderden kilometers
    # verkeerd te hebben (Ameide en Molenhoek belandden zo in België),
    # zonder dat daar in de data zelf een signaal voor staat. Alleen
    # gebouwen met een eigen coördinaat kosten een plaats-lookup.
    plaatsen_te_checken = {
        g["woonplaats"] for g in gebouwen.values() if g["coord"] and g["woonplaats"]
    }
    plaats_candidates = fetch_plaats_candidates(plaatsen_te_checken)

    own_latlon_by_uri: dict[str, tuple[float, float]] = {}
    afgekeurd = []
    for uri, g in gebouwen.items():
        if not g["coord"]:
            continue
        latlon = split_lat_lon(g["coord"])
        if latlon is None:
            continue
        candidates = plaats_candidates.get(g["woonplaats"])
        if candidates:
            nearest = min(candidates, key=lambda c: haversine_km(*latlon, *c))
            afstand = haversine_km(*latlon, *nearest)
            if afstand > PLAUSIBILITEITSGRENS_KM:
                afgekeurd.append((g["titel"], g["woonplaats"], latlon, nearest, afstand))
                continue  # niet gebruiken, val terug op rijksmonument/reliwiki hieronder
        own_latlon_by_uri[uri] = latlon
    if afgekeurd:
        print(f"eigen coördinaat afgekeurd (>{PLAUSIBILITEITSGRENS_KM:.0f} km van dichtstbijzijnde woonplaats-match): {len(afgekeurd)}")
        for titel, plaats, latlon, nearest, afstand in afgekeurd:
            print(f"  - {titel} ({plaats}): bron {latlon} vs. woonplaats {nearest} -- {afstand:.0f} km")

    # Gebouwen zonder (betrouwbare) eigen coördinaat maar met
    # rijksmonumentnummer (bv. de Grote Kerk van Gouda zelf) krijgen een
    # fallback-punt uit de rijksmonumentgeometrie i.p.v. stilzwijgend van de
    # kaart te verdwijnen.
    rm_fallback_needed = {
        g["rijksmonumentnummer"]
        for uri, g in gebouwen.items()
        if uri not in own_latlon_by_uri and g["rijksmonumentnummer"]
    }
    rm_centroids = fetch_rm_centroids(rm_fallback_needed)

    # Nog steeds geen coördinaat en geen (vindbaar) rijksmonumentnummer?
    # Een deel heeft een Reliwiki-link met adres erin -- laatste redmiddel
    # via PDOK-geocoding op dat adres.
    reliwiki_candidates = [
        (uri, same_as, g["woonplaats"])
        for uri, g in gebouwen.items()
        if uri not in own_latlon_by_uri and g["rijksmonumentnummer"] not in rm_centroids
        for same_as in g["sameAs"]
        if "reliwiki" in same_as
    ]
    reliwiki_geocodes = fetch_reliwiki_geocodes(reliwiki_candidates)

    # -- gebouwen.geojson --
    features = []
    gebouw_id_by_uri: dict[str, str] = {}
    zonder_locatie = []  # niet stilzwijgend laten vallen: apart bewaard voor data/site/gebouwen_zonder_locatie.json
    for uri, g in gebouwen.items():
        gid = item_id_from_uri(uri) or uri.rsplit("/", 1)[-1]
        gebouw_id_by_uri[uri] = gid
        latlon = own_latlon_by_uri.get(uri)
        geometrie_bron = "muurschilderingendatabase"
        if latlon is None and g["rijksmonumentnummer"] in rm_centroids:
            latlon = rm_centroids[g["rijksmonumentnummer"]]
            geometrie_bron = "rijksmonumentenregister_centroid"
        if latlon is None and uri in reliwiki_geocodes:
            latlon = reliwiki_geocodes[uri]
            geometrie_bron = "reliwiki_adres_pdok"
        if latlon is None:
            zonder_locatie.append(
                {
                    "id": gid,
                    "naam": g["titel"],
                    "plaats": g["woonplaats"],
                    "rijksmonumentnummer": g["rijksmonumentnummer"],
                    "bron_item_url": uri,
                    "aantal_schilderingen": sum(1 for p in paintings.values() if p["gebouw"] == uri),
                }
            )
            continue
        lat, lon = latlon
        media = media_by_item.get(gid, [])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "id": gid,
                    "naam": g["titel"],
                    "plaats": g["woonplaats"],
                    "identifier": g["identifier"],
                    "rijksmonumentnummer": g["rijksmonumentnummer"],
                    "monumentenregister_url": (
                        f"https://monumentenregister.cultureelerfgoed.nl/monumenten/{g['rijksmonumentnummer']}"
                        if g["rijksmonumentnummer"]
                        else None
                    ),
                    "huidige_functie": g["huidigeFunctie"],
                    "geometrie_bron": geometrie_bron,
                    "same_as": g["sameAs"],
                    "afbeelding": media[0]["medium"] if media else None,
                },
            }
        )
    gebouwen_fc = {"type": "FeatureCollection", "name": "muurschilderingen_gebouwen", "features": features}

    # -- muurschilderingen.json --
    schilderingen_out = []
    for uri, p in paintings.items():
        pid = item_id_from_uri(uri) or uri.rsplit("/", 1)[-1]
        gebouw_uri = p["gebouw"]
        gebouw_id = gebouw_id_by_uri.get(gebouw_uri) or item_id_from_uri(gebouw_uri)
        media = media_by_item.get(pid, [])
        onderwerpen = [
            {"uri": u, "label": subject_labels.get(u, {}).get("label"), "afbeelding": subject_labels.get(u, {}).get("image")}
            for u in p["about"]
        ]
        schilderingen_out.append(
            {
                "id": pid,
                "titel": p["titel"],
                "beschrijving": p["beschrijving"],
                "identifier": p["identifier"],
                "gebouw_id": gebouw_id,
                "datering": {"van": clean_year(p["begin"]), "tot": clean_year(p["eind"]), "tekst": p["temporeel"]},
                "locatieomschrijving": p["locatieomschrijving"],
                "onderdeel_van": p["onderdeelVan"],
                "interieur_exterieur": p["spatial"],
                "genre": p["genre"],
                "onderwerpen": onderwerpen,
                "materiaal": [concept_labels.get(u, u) for u in p["medium"]],
                "drager": [concept_labels.get(u, u) for u in p["surface"]],
                "afbeelding": {
                    "square": media[0]["square"] if media else None,
                    "medium": media[0]["medium"] if media else None,
                    "large": media[0]["large"] if media else None,
                    "origineel": media[0]["origineel"] if media else None,
                }
                if media
                else None,
                "bron_item_url": uri,
            }
        )

    # -- onderwerpen.json: iconografie-index --
    onderwerpen_index: dict[str, dict] = {}
    for s in schilderingen_out:
        for onderwerp in s["onderwerpen"]:
            entry = onderwerpen_index.setdefault(
                onderwerp["uri"], {"uri": onderwerp["uri"], "label": onderwerp["label"], "afbeelding": onderwerp["afbeelding"], "schildering_ids": []}
            )
            entry["schildering_ids"].append(s["id"])
    onderwerpen_out = sorted(onderwerpen_index.values(), key=lambda e: -len(e["schildering_ids"]))

    stats = {
        "gebouwen_totaal": len(gebouwen),
        "gebouwen_met_geometrie": len(features),
        "gebouwen_zonder_geometrie": len(zonder_locatie),
        "schilderingen_totaal": len(schilderingen_out),
        "schilderingen_met_afbeelding": sum(1 for s in schilderingen_out if s["afbeelding"]),
        "iconografische_onderwerpen": len(onderwerpen_out),
        "gebouwen_met_rijksmonumentnummer": sum(1 for g in gebouwen.values() if g["rijksmonumentnummer"]),
    }

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "gebouwen.geojson").write_text(json.dumps(gebouwen_fc, ensure_ascii=False, indent=None, separators=(",", ":")), encoding="utf-8")
    (SITE_DIR / "muurschilderingen.json").write_text(json.dumps(schilderingen_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (SITE_DIR / "onderwerpen.json").write_text(json.dumps(onderwerpen_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (SITE_DIR / "gebouwen_zonder_locatie.json").write_text(json.dumps(zonder_locatie, ensure_ascii=False, indent=2), encoding="utf-8")

    metadata = {
        "source": "RCE Linked Data Voorziening, dataset Muurschilderingen (+ cho voor thesauruslabels, Wikidata voor iconografielabels)",
        "endpoint": MUUR_ENDPOINT,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
    }
    (SITE_DIR / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
