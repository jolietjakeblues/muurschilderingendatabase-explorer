#!/usr/bin/env python3
"""
Bouw de statische dataset voor de Muurschilderingendatabase-explorer.

Bronnen:
  1. RCE Linked Data Voorziening, dataset "Muurschilderingen" (SPARQL) --
     gebouwen, schilderingen en makers: queries/gebouwen.sparql,
     queries/paintings.sparql, queries/personen.sparql en
     queries/organisaties.sparql.
  2. RCE Linked Data Voorziening, dataset "cho" (SPARQL) -- skos:prefLabel
     voor de materiaal-/drager-thesaurusconcepten die in (1) alleen als URI
     voorkomen; de rijksmonumentgeometrie als terugvaloptie voor gebouwen
     zonder bruikbare eigen coördinaat; en, voor de proefkoppeling op
     rijksmonumentnummer, de oorspronkelijke functie (alleen formeel
     standpunt) met de hoofdcategorie uit de functiethesaurus.
  3. Wikidata Query Service (SPARQL) -- labels (en, waar aanwezig, een
     representatieve afbeelding P18) voor de iconografische onderwerpen
     (schema:about), die in (1) alleen als wikidata-URI voorkomen.
  4. muurschilderingendatabase.nl/api/media (Omeka S REST, geen SPARQL) --
     de SPARQL-graph bevat alleen media-URI's, geen thumbnail/origineel-URLs;
     die REST-API wel. Volledig gepagineerd opgehaald en op o:item (de
     schildering of het gebouw) gekoppeld.
  5. PDOK Locatieserver (BAG-adressen, REST) -- twee toepassingen. De
     plausibiliteitscheck: elke eigen coördinaat wordt getoetst aan de
     woonplaats van het gebouw. En als laatste redmiddel voor gebouwen
     zonder eigen coördinaat en zonder (vindbaar) rijksmonument: een deel
     heeft wel een Reliwiki-link met adres erin (schema:sameAs), dat adres
     geocoderen we hiermee.
  6. RCE Linked Data Voorziening, dataset "Afbeeldingen" (SPARQL) --
     Beeldbankfoto's per rijksmonumentnummer, voor de proefkoppeling.

Schrijft data/raw/*.json (ruwe extracts, voor herleidbaarheid) en
docs/data/site/*.json + gebouwen.geojson (het datamodel dat de viewer
laadt). Wegschrijven gebeurt pas aan het eind: de build breekt af zonder
iets te overschrijven als een endpoint of PDOK onbereikbaar blijft, of als een kerngetal
meer dan 10% onder de vorige build zakt (ALLOW_SHRINK=1 slaat dat over).

Geen live queries vanuit de browser: alles hier voorgebakken, zelfde
architectuurkeuze als het dodenakkers-project waar dit uit voortkomt.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

MUUR_ENDPOINT = "https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Muurschilderingen/sparql"
CHO_ENDPOINT = "https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/cho/sparql"
AFBEELDINGEN_ENDPOINT = "https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/afbeeldingen/sparql"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
OMEKA_MEDIA_API = "https://muurschilderingendatabase.nl/api/media"
PDOK_LOCATIESERVER = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"

REPO_ROOT = Path(__file__).resolve().parent.parent
QUERIES_DIR = REPO_ROOT / "queries"
RAW_DIR = REPO_ROOT / "data" / "raw"
SITE_DIR = REPO_ROOT / "docs" / "data" / "site"

HEADERS_SPARQL = {"Accept": "application/sparql-results+json"}
HEADERS_UA = {"User-Agent": "muurschilderingendatabase-explorer/0.1 (build script; GitHub Pages viewer)"}


SPARQL_POGINGEN = 5


def run_sparql(endpoint: str, query: str) -> list[dict]:
    # De endpoints geven af en toe een 502/503/504 of verbreken de verbinding;
    # dat is bijna altijd voorbij na een paar seconden. Een 4xx is een fout in
    # de query en wordt niet herhaald.
    for poging in range(SPARQL_POGINGEN):
        try:
            resp = requests.post(endpoint, data={"query": query}, headers={**HEADERS_SPARQL, **HEADERS_UA}, timeout=180)
            if resp.status_code < 500:
                break
            fout: Exception = requests.HTTPError(f"HTTP {resp.status_code} van {endpoint}")
        except (requests.ConnectionError, requests.Timeout) as exc:
            fout = exc
        if poging == SPARQL_POGINGEN - 1:
            raise RuntimeError(f"SPARQL-endpoint onbereikbaar na {SPARQL_POGINGEN} pogingen: {fout}")
        print(f"  {fout} -- nieuwe poging over {5 * 2 ** poging} s")
        time.sleep(5 * 2 ** poging)
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
    # Vaste volgorde: de SPARQL-uitvoer komt per keer anders gesorteerd terug.
    # Zonder dit wisselt "eerste waarde wint" in group_by_subject per build,
    # en is elke verversing van data/raw/ één grote diff.
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
    # Wegschrijven naar data/raw/ gebeurt pas aan het eind van main(), na de
    # krimpcontrole -- een mislukte build laat zo ook de ruwe extracts intact.
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
# Coördinaten: een gebouw kan meerdere markers hebben, elk met twee waarden
# zonder lat/lon-onderscheid in het predicate zelf. Per marker op
# waardebereik classificeren (dataset is Nederland-only), daarna één marker
# per gebouw kiezen.
# --------------------------------------------------------------------------

def split_lat_lon(coords: list[str]) -> tuple[float, float] | None:
    values = [float(c) for c in coords]
    lat = next((v for v in values if 50.0 <= v <= 54.0), None)
    lon = next((v for v in values if 3.0 <= v <= 7.6), None)
    if lat is None or lon is None:
        return None
    return lat, lon


def markers_per_gebouw(rows: list[dict]) -> dict[str, list[dict]]:
    """Per gebouw de markers uit de Omeka mapping-module, elk als
    {"latlon": (lat, lon), "label": ...}. De twee coördinaatwaarden van één
    marker blijven bij elkaar via ?feat; los sorteren over alle markers heen
    kan de breedte van de ene met de lengte van de andere paren."""
    per_feat: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not row.get("feat") or not row.get("coord"):
            continue
        entry = per_feat.setdefault((row["s"], row["feat"]), {"coords": set(), "label": row.get("featLabel")})
        entry["coords"].add(row["coord"])
    result: dict[str, list[dict]] = defaultdict(list)
    for (uri, _feat), entry in sorted(per_feat.items()):
        latlon = split_lat_lon(sorted(entry["coords"]))
        if latlon:
            result[uri].append({"latlon": latlon, "label": entry["label"] or ""})
    return dict(result)


PLAATSMARKER_RE = re.compile(r"^[^,\d]+(,[^,\d]+){1,3},\s*Nederland$")


def pick_marker(markers: list[dict]) -> tuple[float, float] | None:
    """Eén punt per gebouw. Bij meerdere markers is er vaak één op de plaats
    gezet ("Blauwhuis, Súdwest-Fryslân, Fryslân, Nederland") en één op het
    gebouw zelf ("St. Vituskerk, Vitusdyk, Blauwhuis, ..." of een adres met
    huisnummer en postcode). Markers waarvan het label alleen plaats,
    gemeente en provincie noemt vallen af zolang er een andere is; van wat
    overblijft wint het label met de meeste onderdelen. Bij gelijke stand het
    gemiddelde van die markers."""
    if not markers:
        return None
    specifiek = [m for m in markers if not PLAATSMARKER_RE.match(m["label"].strip())]
    kandidaten = specifiek or markers
    onderdelen = lambda m: len([d for d in m["label"].split(",") if d.strip()])
    hoogste = max(onderdelen(m) for m in kandidaten)
    beste = sorted({m["latlon"] for m in kandidaten if onderdelen(m) == hoogste})
    return (sum(b[0] for b in beste) / len(beste), sum(b[1] for b in beste) / len(beste))


# --------------------------------------------------------------------------
# Huidige functie: vrije tekst in de bron, hier gegroepeerd voor het filter.
# --------------------------------------------------------------------------

FUNCTIE_GROEPEN = [
    ("Religieus", r"kerk|kapel|synagoge|religieus|klooster|missiehuis"),
    ("Museum en cultuur", r"museum|cultur|theater|schouwburg|concert|bioscoop|expositie|atelier"),
    ("Onderwijs", r"school|universiteit|faculteit|college|academie|aula"),
    ("Wonen", r"woon|woning|hofje|appartement|buitenhuis"),
    ("Kantoor en bestuur", r"kanto|stadhuis|provinciehuis|bestuur|archief|vergader|bedrijfslocatie|bedrijven"),
    ("Horeca, evenementen en verhuur", r"horeca|hotel|restaurant|evenement|verhuur|brouwerij|sociëteit|theehuis|kamperen|camping"),
    ("Buiten gebruik of gesloopt", r"buiten gebruik|gesloopt|transformatie|^geen$"),
]
FUNCTIE_ONBEKEND = "Onbekend"
FUNCTIE_OVERIG = "Overig"


def functie_groepen(value: str | None) -> list[str]:
    """De bron kent ruim honderd schrijfwijzen voor de huidige functie
    ("kerk", "Kerk / Hervormde kerk", "Kerk / Hervormde Kerk", ...). Voor het
    filter in de kaartweergave gegroepeerd op trefwoord; een gebouw kan in
    meerdere groepen vallen ("Kerk en cultureel centrum"). De oorspronkelijke
    tekst blijft ongewijzigd in huidige_functie staan."""
    tekst = (value or "").strip().lower()
    if not tekst or tekst in ("onbekend", "onduidelijk") or tekst.startswith("http"):
        return [FUNCTIE_ONBEKEND]
    groepen = [naam for naam, patroon in FUNCTIE_GROEPEN if re.search(patroon, tekst)]
    return groepen or [FUNCTIE_OVERIG]


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


WIKIDATA_QID_RE = re.compile(r"https?://(?:www\.)?wikidata\.org/(?:wiki|entity)/(Q\d+)")


def normalize_about(value: str) -> str:
    """schema:about staat in de bron in drie vormen: de entity-URI
    (http://www.wikidata.org/entity/Q1), de pagina-URL
    (https://www.wikidata.org/wiki/Q1) en vrije tekst met zo'n URL erin
    ("duiven (https://www.wikidata.org/wiki/Q2984138)"). Alle drie bedoelen
    dezelfde entiteit; zonder normalisatie krijgen de laatste twee geen label
    en wordt één onderwerp over meerdere indexregels verdeeld. Waarden zonder
    Wikidata-verwijzing (bv. een CHT-term) blijven ongewijzigd."""
    m = WIKIDATA_QID_RE.search(value)
    return f"http://www.wikidata.org/entity/{m.group(1)}" if m else value


def fetch_item_titles(uris: set[str]) -> dict[str, str]:
    """dcterms:title voor willekeurige items uit de Muurschilderingen-dataset,
    ongeacht hun klasse -- voor schema:location-doelen die geen gtm:Gebouw
    zijn en dus niet in queries/gebouwen.sparql meekomen."""
    uris = {u for u in uris if u.startswith("http://") or u.startswith("https://")}
    if not uris:
        return {}
    values = " ".join(f"<{u}>" for u in sorted(uris))
    query = f"""
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT ?s ?titel WHERE {{
  GRAPH ?g {{
    VALUES ?s {{ {values} }}
    ?s dcterms:title ?titel .
  }}
}}"""
    titles: dict[str, str] = {}
    for row in run_sparql(MUUR_ENDPOINT, query):
        titles.setdefault(row["s"], row["titel"])
    return titles


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
                    "id": str(m.get("o:id")),
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


PDOK_POGINGEN = 4


def pdok_docs(params: dict) -> list[dict]:
    """Eén PDOK-zoekopdracht, met herhaalpogingen. Een storing mag niet
    stilzwijgend als 'geen resultaat' tellen: dan vervalt de
    plausibiliteitscheck (en belanden Ameide en Molenhoek weer in België) of
    verdwijnt een gebouw van de kaart, zonder dat de build dat merkt. Na
    PDOK_POGINGEN mislukte pogingen breekt de build daarom af. Alleen een
    4xx op de zoekterm zelf (geen 429) geldt als 'geen resultaat'."""
    laatste: Exception | None = None
    for poging in range(PDOK_POGINGEN):
        try:
            resp = requests.get(PDOK_LOCATIESERVER, params=params, headers=HEADERS_UA, timeout=15)
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                print(f"  PDOK weigert zoekterm {params.get('q')!r} (HTTP {resp.status_code}), overgeslagen")
                return []
            resp.raise_for_status()
            return resp.json()["response"]["docs"]
        except (requests.RequestException, ValueError, KeyError) as exc:
            laatste = exc
            if poging < PDOK_POGINGEN - 1:
                time.sleep(2 ** poging)
    raise RuntimeError(
        f"PDOK Locatieserver onbereikbaar na {PDOK_POGINGEN} pogingen (zoekterm {params.get('q')!r}): {laatste}"
    )


def geocode_pdok(query: str) -> tuple[float, float] | None:
    docs = pdok_docs({"q": query, "rows": 1})
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
        docs = pdok_docs({"q": plaats, "fq": "type:woonplaats", "rows": 10})
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
        latlon = geocode_pdok(f"{addr}, {plaats or ''}".strip(", "))
        if latlon:
            result[gebouw_uri] = latlon
    print(f"reliwiki-adressen gegeocodeerd via PDOK: {len(result)}/{len(candidates)}")
    return result


def primaire_eerst(media: list[dict], primary_uri: str | None) -> list[dict]:
    """Zet de afbeelding die in de bron als o:primary_media is aangewezen
    vooraan; zonder aanwijzing blijft de volgorde van de API staan."""
    m = re.search(r"/media/(\d+)$", primary_uri or "")
    if not m:
        return media
    return sorted(media, key=lambda x: x["id"] != m.group(1))


def clean_year(value: str | None) -> str | None:
    """De bron gebruikt '0' als sentinel voor 'geen datering bekend', niet
    een letterlijk jaar 0 (geen Nederlandse kerk dateert uit 0-99 n.Chr.) --
    geverifieerd op de 20 rijen die dit in september 2026 raakten, zie
    docs/methode.md. Sinds november 2026 komt de waarde in de bron niet meer
    voor; dit blijft staan als vangnet."""
    return None if value == "0" else value


def item_id_from_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    m = re.search(r"/items/(\d+)$", uri)
    return m.group(1) if m else None


# --------------------------------------------------------------------------
# Proefkoppeling met andere RCE-datasets, op rijksmonumentnummer.
# --------------------------------------------------------------------------

def clean_rm(value: str | None) -> str | None:
    """De bron bevat een paar vervuilde nummers ("RM35671", "517621\n").
    Het rijksmonumentnummer is de koppelsleutel naar CHO en de Beeldbank,
    dus hier teruggebracht tot alleen de cijfers."""
    if not value:
        return None
    m = re.search(r"\d+", value)
    return m.group(0) if m else None


INSTANTIES_GRAPH = "https://linkeddata.cultureelerfgoed.nl/graph/instanties-rce"
PHOTOS_GRAPH = "https://linkeddata.cultureelerfgoed.nl/rce/afbeeldingen/graphs/photos"
BEELDBANK_BATCH = 25
FUNCTIE_WORTEL = "bebouwde omgeving"
KOPPEL_BATCH = 100
BEELDBANK_MAX_PER_GEBOUW = 6
SCHILDERING_RE = re.compile(r"schildering|fresco|beschilder", re.IGNORECASE)


def fetch_cho_functies(rm_numbers: set[str]) -> dict[str, dict]:
    """Oorspronkelijke functie per rijksmonument uit de CHO-dataset, met de
    hoofdcategorie uit de functiethesaurus (de term direct onder
    'bebouwde omgeving', bv. 'Religieuze gebouwen' of 'Boerderijen, molens
    en bedrijven'). Alleen kennis met ceo:formeelStandpunt true.

    De functie-koppeling staat in de graph instanties-rce; de labels en de
    broader-keten staan in de thesaurusgraphs, dus buiten die
    GRAPH-restrictie."""
    result: dict[str, dict] = {}
    nummers = sorted(rm_numbers)
    for i in range(0, len(nummers), KOPPEL_BATCH):
        values = " ".join(f'"{n}"' for n in nummers[i : i + KOPPEL_BATCH])
        query = f"""
PREFIX ceo: <https://linkeddata.cultureelerfgoed.nl/def/ceo#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?rm ?cho ?hoofd ?c ?l0 ?l1 ?l2 ?l3 ?l4 WHERE {{
  GRAPH <{INSTANTIES_GRAPH}> {{
    VALUES ?rm {{ {values} }}
    ?cho a ceo:Rijksmonument ; ceo:rijksmonumentnummer ?rm .
    OPTIONAL {{
      ?cho ceo:heeftOorspronkelijkeFunctie ?k .
      ?k ceo:formeelStandpunt true ; ceo:heeftFunctieNaam ?c .
      OPTIONAL {{ ?k ceo:hoofdfunctie ?hoofd }}
    }}
  }}
  OPTIONAL {{ ?c skos:prefLabel ?l0 . FILTER(lang(?l0) = "nl") }}
  OPTIONAL {{
    ?c skos:broader ?b1 . ?b1 skos:prefLabel ?l1 . FILTER(lang(?l1) = "nl")
    OPTIONAL {{
      ?b1 skos:broader ?b2 . ?b2 skos:prefLabel ?l2 . FILTER(lang(?l2) = "nl")
      OPTIONAL {{
        ?b2 skos:broader ?b3 . ?b3 skos:prefLabel ?l3 . FILTER(lang(?l3) = "nl")
        OPTIONAL {{ ?b3 skos:broader ?b4 . ?b4 skos:prefLabel ?l4 . FILTER(lang(?l4) = "nl") }}
      }}
    }}
  }}
}}"""
        for row in run_sparql(CHO_ENDPOINT, query):
            entry = result.setdefault(row["rm"], {"cho_uri": row["cho"], "_functies": {}})
            if not row.get("l0"):
                continue
            keten = [row[k] for k in ("l0", "l1", "l2", "l3", "l4") if row.get(k)]
            if FUNCTIE_WORTEL in keten:
                idx = keten.index(FUNCTIE_WORTEL)
                categorie = keten[idx - 1] if idx > 0 else None
            else:
                categorie = keten[-1]
            functie = entry["_functies"].setdefault(row["l0"], {"hoofd": False, "categorie": None})
            functie["hoofd"] = functie["hoofd"] or row.get("hoofd") == "true"
            functie["categorie"] = functie["categorie"] or categorie
    for entry in result.values():
        functies = sorted(entry.pop("_functies").items(), key=lambda kv: (not kv[1]["hoofd"], kv[0]))
        entry["functies"] = [naam for naam, _ in functies]
        categorieen: list[str] = []
        for _, f in functies:
            if f["categorie"] and f["categorie"] not in categorieen:
                categorieen.append(f["categorie"])
        entry["categorieen"] = categorieen
    print(f"CHO-koppeling: {len(result)}/{len(nummers)} rijksmonumentnummers gevonden, "
          f"{sum(1 for e in result.values() if e['functies'])} met oorspronkelijke functie")
    return result


def fetch_beeldbank(rm_numbers: set[str]) -> dict[str, dict]:
    """Beeldbankfoto's per rijksmonument uit de dataset Afbeeldingen.

    Model (sinds november 2026): een foto verwijst met sdo:about naar een
    monumentknoop binnen de dataset zelf (sdo:LandmarksOrHistoricalBuildings),
    en die knoop draagt het rijksmonumentnummer als sdo:identifier
    (sdo:PropertyValue, propertyID "rijksmonumentnummer"). Er is dus geen
    verwijzing naar de CHO-URI meer nodig.

    Per gebouw het totaal, het aantal waarvan de titel op een schildering
    wijst, en een kleine selectie met die foto's vooraan."""
    per_rm: dict[str, dict[str, dict]] = defaultdict(dict)
    nummers = sorted(rm_numbers)
    for i in range(0, len(nummers), BEELDBANK_BATCH):
        values = " ".join(f'"{n}"' for n in nummers[i : i + BEELDBANK_BATCH])
        query = f"""
PREFIX sdo: <https://schema.org/>
SELECT ?rm ?f ?titel ?thumb ?pagina ?licentie WHERE {{
  GRAPH <{PHOTOS_GRAPH}> {{
    VALUES ?rm {{ {values} }}
    ?id sdo:propertyID "rijksmonumentnummer" ; sdo:value ?rm .
    ?m sdo:identifier ?id .
    ?f a sdo:Photograph ; sdo:about ?m ; sdo:image ?img .
    ?img sdo:thumbnailUrl ?thumb .
    OPTIONAL {{ ?f sdo:name ?titel }}
    OPTIONAL {{ ?f sdo:url ?pagina }}
    OPTIONAL {{ ?f sdo:license ?licentie }}
  }}
}}"""
        for row in run_sparql(AFBEELDINGEN_ENDPOINT, query):
            per_rm[row["rm"]].setdefault(
                row["f"],
                {
                    "titel": row.get("titel"),
                    "thumb": row["thumb"],
                    "url": row.get("pagina"),
                    "licentie": row.get("licentie"),
                },
            )
    result: dict[str, dict] = {}
    for rm, fotos in per_rm.items():
        lijst = sorted(fotos.values(), key=lambda f: (not SCHILDERING_RE.search(f["titel"] or ""), f["titel"] or ""))
        result[rm] = {
            "aantal": len(lijst),
            "aantal_schildering": sum(1 for f in lijst if SCHILDERING_RE.search(f["titel"] or "")),
            "fotos": lijst[:BEELDBANK_MAX_PER_GEBOUW],
        }
    print(f"Beeldbank-koppeling: {len(result)}/{len(nummers)} rijksmonumenten met foto's, "
          f"{sum(r['aantal'] for r in result.values())} foto's, "
          f"{sum(r['aantal_schildering'] for r in result.values())} met een schildering in de titel")
    return result


METADATA_SOURCE = (
    "RCE Linked Data Voorziening, dataset Muurschilderingen (+ cho voor thesauruslabels, "
    "rijksmonumentgeometrie en oorspronkelijke functie; Afbeeldingen voor Beeldbankfoto's; "
    "Wikidata voor iconografielabels; Omeka-API voor afbeeldingen; PDOK voor geocodering)"
)

KRIMPGRENS = 0.9
KRIMP_SLEUTELS = [
    "gebouwen_totaal",
    "gebouwen_met_geometrie",
    "schilderingen_totaal",
    "schilderingen_met_afbeelding",
    "iconografische_onderwerpen",
    "onderwerpen_met_label",
    "makers_gekoppeld",
]


def check_tegen_vorige_build(stats: dict) -> None:
    """Breekt af als een kerngetal meer dan 10% onder de vorige build zakt.
    De bron groeit alleen; een flinke daling betekent vrijwel zeker een
    half antwoord van een van de endpoints (lege SPARQL-uitvoer, Wikidata
    zonder labels, Omeka zonder media), en dat hoort niet over een goede
    build heen geschreven te worden. Bewust overslaan kan met
    ALLOW_SHRINK=1."""
    vorige_pad = SITE_DIR / "metadata.json"
    if not vorige_pad.exists():
        return
    try:
        vorige = json.loads(vorige_pad.read_text(encoding="utf-8")).get("stats", {})
    except (ValueError, OSError):
        return
    gekrompen = [
        f"{k}: {vorige[k]} -> {stats[k]}"
        for k in KRIMP_SLEUTELS
        if isinstance(vorige.get(k), int) and vorige[k] > 0 and stats[k] < KRIMPGRENS * vorige[k]
    ]
    if not gekrompen:
        return
    melding = "build gekrompen t.o.v. de vorige: " + "; ".join(gekrompen)
    if os.environ.get("ALLOW_SHRINK") == "1":
        print(f"WAARSCHUWING ({melding}) -- ALLOW_SHRINK=1, toch doorgegaan")
        return
    raise SystemExit(f"AFGEBROKEN: {melding}. Niets weggeschreven. Zet ALLOW_SHRINK=1 om dit bewust te accepteren.")


# --------------------------------------------------------------------------
# Main build
# --------------------------------------------------------------------------

def main() -> None:
    gebouw_rows = fetch_muur_rows("gebouwen")
    painting_rows = fetch_muur_rows("paintings")
    persoon_rows = fetch_muur_rows("personen")
    organisatie_rows = fetch_muur_rows("organisaties")

    gebouwen = group_by_subject(
        gebouw_rows,
        "s",
        single_fields=["titel", "identifier", "rijksmonumentnummer", "woonplaats", "huidigeFunctie", "bouwgeschiedenis", "restauratiegeschiedenis"],
        multi_fields=["sameAs", "andereNaam", "woonplaatsAnders"],
    )
    markers = markers_per_gebouw(gebouw_rows)
    for g in gebouwen.values():
        # o:title is de weergavenaam van Omeka; ontbreekt die, dan de eerste
        # dcterms:title. De overige titels blijven als andere namen bewaard.
        g["andereNaam"] = sorted({n.strip() for n in g["andereNaam"] if n.strip()})
        g["titel"] = (g["titel"] or "").strip() or (g["andereNaam"][0] if g["andereNaam"] else None)
        g["andereNaam"] = [n for n in g["andereNaam"] if n != g["titel"]]
    for g in gebouwen.values():
        g["rijksmonumentnummer"] = clean_rm(g["rijksmonumentnummer"])

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
        multi_fields=["genre", "about", "medium", "surface", "creator"],
    )

    for p in paintings.values():
        p["about"] = sorted({normalize_about(u) for u in p["about"]})

    personen = group_by_subject(
        persoon_rows, "s", single_fields=["titel", "beschrijving", "geboorte", "sterfte"], multi_fields=["sameAs"]
    )
    organisaties = group_by_subject(
        organisatie_rows, "s", single_fields=["titel", "beschrijving"], multi_fields=["sameAs"]
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
        naam
        for uri, g in gebouwen.items()
        if uri in markers
        for naam in [g["woonplaats"], *g["woonplaatsAnders"]]
        if naam
    }
    plaats_candidates = fetch_plaats_candidates(plaatsen_te_checken)

    own_latlon_by_uri: dict[str, tuple[float, float]] = {}
    afgekeurd = []
    for uri, g in gebouwen.items():
        latlon = pick_marker(markers.get(uri, []))
        if latlon is None:
            continue
        # Alle naamvarianten van de plaats tellen mee: het Friese Oostrum heet
        # in de BAG "Eastrum", en "Oostrum" alleen levert het Limburgse dorp op.
        candidates = [
            c
            for naam in [g["woonplaats"], *g["woonplaatsAnders"]]
            for c in plaats_candidates.get(naam, [])
        ]
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

    alle_rm = {g["rijksmonumentnummer"] for g in gebouwen.values() if g["rijksmonumentnummer"]}
    cho_functies = fetch_cho_functies(alle_rm)
    beeldbank = fetch_beeldbank(alle_rm)

    # -- gebouwen.geojson --
    features = []
    gebouw_id_by_uri: dict[str, str] = {}
    zonder_locatie = []  # niet stilzwijgend laten vallen: apart bewaard voor docs/data/site/gebouwen_zonder_locatie.json
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
                    "reden": "geen_coordinaat",
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
                    "andere_namen": g["andereNaam"],
                    "plaats": g["woonplaats"],
                    "plaats_anders": g["woonplaatsAnders"],
                    "bron_item_url": uri,
                    "identifier": g["identifier"],
                    "rijksmonumentnummer": g["rijksmonumentnummer"],
                    "monumentenregister_url": (
                        f"https://monumentenregister.cultureelerfgoed.nl/monumenten/{g['rijksmonumentnummer']}"
                        if g["rijksmonumentnummer"]
                        else None
                    ),
                    "huidige_functie": g["huidigeFunctie"],
                    "functie_groepen": functie_groepen(g["huidigeFunctie"]),
                    "geometrie_bron": geometrie_bron,
                    # Proefkoppeling: kennis uit het rijksmonumentenregister
                    # (formeel standpunt) en foto's uit de Beeldbank.
                    "rce": (
                        {
                            "cho_uri": cho_functies.get(g["rijksmonumentnummer"], {}).get("cho_uri"),
                            "functies": cho_functies.get(g["rijksmonumentnummer"], {}).get("functies", []),
                            "categorieen": cho_functies.get(g["rijksmonumentnummer"], {}).get("categorieen", []),
                            "beeldbank": beeldbank.get(g["rijksmonumentnummer"]),
                        }
                        if g["rijksmonumentnummer"] in cho_functies or g["rijksmonumentnummer"] in beeldbank
                        else None
                    ),
                    "same_as": g["sameAs"],
                    "afbeelding": media[0]["medium"] if media else None,
                },
            }
        )
    gebouwen_fc = {"type": "FeatureCollection", "name": "muurschilderingen_gebouwen", "features": features}

    # schema:location wijst bij een handvol schilderingen naar een item dat
    # geen gtm:Gebouw is (een los o:Item, een PhysicalObject, of zelfs een
    # andere schildering). Die komen niet uit queries/gebouwen.sparql en
    # zouden anders nergens in de kaartweergave opduiken; hier krijgen ze een
    # eigen regel in de niet-op-de-kaart-lijst, met dezelfde id als het
    # gebouw_id dat hun schilderingen hieronder krijgen.
    locatie_telling: dict[str, int] = defaultdict(int)
    for p in paintings.values():
        if p["gebouw"] and p["gebouw"] not in gebouwen and item_id_from_uri(p["gebouw"]):
            locatie_telling[p["gebouw"]] += 1
    locatie_titels = fetch_item_titles(set(locatie_telling))
    for loc_uri, aantal in sorted(locatie_telling.items()):
        zonder_locatie.append(
            {
                "id": item_id_from_uri(loc_uri),
                "naam": locatie_titels.get(loc_uri),
                "plaats": None,
                "rijksmonumentnummer": None,
                "bron_item_url": loc_uri,
                "aantal_schilderingen": aantal,
                "reden": "geen_gebouwrecord",
            }
        )
    if locatie_telling:
        print(f"locaties die geen gtm:Gebouw zijn: {len(locatie_telling)} ({sum(locatie_telling.values())} schilderingen)")

    # -- muurschilderingen.json --
    # Makers (personen + organisaties) samenvoegen tot één opzoektabel:
    # dcterms:creator op een schildering kan naar beide klassen wijzen.
    maker_id_by_uri: dict[str, str] = {}
    maker_naam_type_by_id: dict[str, dict] = {}
    for uri, pers in personen.items():
        mid = item_id_from_uri(uri) or uri.rsplit("/", 1)[-1]
        maker_id_by_uri[uri] = mid
        maker_naam_type_by_id[mid] = {"naam": pers["titel"], "type": "persoon"}
    for uri, org in organisaties.items():
        mid = item_id_from_uri(uri) or uri.rsplit("/", 1)[-1]
        maker_id_by_uri[uri] = mid
        maker_naam_type_by_id[mid] = {"naam": org["titel"], "type": "organisatie"}

    schilderingen_out = []
    for uri, p in paintings.items():
        pid = item_id_from_uri(uri) or uri.rsplit("/", 1)[-1]
        gebouw_uri = p["gebouw"]
        gebouw_id = gebouw_id_by_uri.get(gebouw_uri) or item_id_from_uri(gebouw_uri)
        media = primaire_eerst(media_by_item.get(pid, []), p["primaryMedia"])
        onderwerpen = [
            {"uri": u, "label": subject_labels.get(u, {}).get("label"), "afbeelding": subject_labels.get(u, {}).get("image")}
            for u in p["about"]
        ]
        makers = [
            {"id": maker_id_by_uri[u], **maker_naam_type_by_id[maker_id_by_uri[u]]}
            for u in p["creator"]
            if u in maker_id_by_uri
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
                "makers": makers,
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

    # -- makers.json: kunstenaars-/organisatie-index --
    makers_index: dict[str, dict] = {}
    for uri, pers in personen.items():
        mid = maker_id_by_uri[uri]
        makers_index[mid] = {
            "id": mid,
            "naam": pers["titel"],
            "type": "persoon",
            "beschrijving": pers["beschrijving"],
            "geboorte": pers["geboorte"],
            "sterfte": pers["sterfte"],
            "same_as": pers["sameAs"],
            "schildering_ids": [],
        }
    for uri, org in organisaties.items():
        mid = maker_id_by_uri[uri]
        makers_index[mid] = {
            "id": mid,
            "naam": org["titel"],
            "type": "organisatie",
            "beschrijving": org["beschrijving"],
            "geboorte": None,
            "sterfte": None,
            "same_as": org["sameAs"],
            "schildering_ids": [],
        }
    for s in schilderingen_out:
        for maker in s["makers"]:
            makers_index[maker["id"]]["schildering_ids"].append(s["id"])
    # Alleen makers met minstens één gekoppelde schildering publiceren --
    # de brondatabase bevat de volledige authority-lijst, ook entries die
    # (nog) nergens aan gekoppeld zijn.
    makers_out = sorted(
        (m for m in makers_index.values() if m["schildering_ids"]),
        key=lambda m: -len(m["schildering_ids"]),
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
        "gebouwen_zonder_geometrie": sum(1 for z in zonder_locatie if z["reden"] == "geen_coordinaat"),
        "locaties_geen_gebouwrecord": len(locatie_telling),
        "schilderingen_locatie_geen_gebouwrecord": sum(locatie_telling.values()),
        "schilderingen_zonder_gebouw": sum(1 for s in schilderingen_out if not s["gebouw_id"]),
        "schilderingen_totaal": len(schilderingen_out),
        "schilderingen_met_afbeelding": sum(1 for s in schilderingen_out if s["afbeelding"]),
        "iconografische_onderwerpen": len(onderwerpen_out),
        "onderwerpen_met_label": sum(1 for o in onderwerpen_out if o["label"]),
        "gebouwen_met_rijksmonumentnummer": sum(1 for g in gebouwen.values() if g["rijksmonumentnummer"]),
        "gebouwen_met_meerdere_markers": sum(1 for m in markers.values() if len(m) > 1),
        "gebouwen_met_andere_namen": sum(1 for g in gebouwen.values() if g["andereNaam"]),
        "gebouwen_met_cho_functie": sum(1 for f in features if (f["properties"]["rce"] or {}).get("functies")),
        "gebouwen_met_beeldbankfoto": sum(1 for f in features if (f["properties"]["rce"] or {}).get("beeldbank")),
        "makers_gekoppeld": len(makers_out),
        "makers_met_geboortedatum": sum(1 for m in makers_out if m["geboorte"]),
        "schilderingen_met_maker": sum(1 for s in schilderingen_out if s["makers"]),
    }

    check_tegen_vorige_build(stats)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("gebouwen", gebouw_rows),
        ("paintings", painting_rows),
        ("personen", persoon_rows),
        ("organisaties", organisatie_rows),
    ):
        (RAW_DIR / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "gebouwen.geojson").write_text(json.dumps(gebouwen_fc, ensure_ascii=False, indent=None, separators=(",", ":")), encoding="utf-8")
    (SITE_DIR / "muurschilderingen.json").write_text(json.dumps(schilderingen_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (SITE_DIR / "onderwerpen.json").write_text(json.dumps(onderwerpen_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (SITE_DIR / "makers.json").write_text(json.dumps(makers_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (SITE_DIR / "gebouwen_zonder_locatie.json").write_text(json.dumps(zonder_locatie, ensure_ascii=False, indent=2), encoding="utf-8")

    metadata = {
        "source": METADATA_SOURCE,
        "endpoint": MUUR_ENDPOINT,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
    }
    (SITE_DIR / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
