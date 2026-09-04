# Methode en herkomst

## Wat dit is

Een statische kaart- en iconografieverkenner bovenop de linked-data-publicatie
van de [Muurschilderingendatabase](https://muurschilderingendatabase.nl)
(RCE). Geen live queries vanuit de browser: alle data wordt tijdens de build
opgehaald en als platte JSON/GeoJSON gepubliceerd. Onafhankelijk project, geen
officiële RCE-publicatie.

## Bronnen

1. **RCE Linked Data Voorziening, dataset "Muurschilderingen"**
   (`https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Muurschilderingen/sparql`)
   — gebouwen (`gtm:Gebouw`) en schilderingen (`schema:Painting`), zie
   `queries/gebouwen.sparql` en `queries/paintings.sparql`. Dit is dezelfde
   RCE Linked Data-infrastructuur als de Rijksmonumenten/CHO-datasets.
2. **RCE Linked Data Voorziening, dataset "cho"** — `skos:prefLabel` voor de
   materiaal-/drager-thesaurusconcepten (`schema:artMedium`,
   `schema:artworkSurface`), en als fallback-geometrie: de rijksmonumentgeometrie
   (via exacte join op `ceo:rijksmonumentnummer`) voor gebouwen die zelf geen
   coördinaat hebben in de brondataset.
3. **Wikidata Query Service** — labels (`rdfs:label`, voorkeur `nl`, fallback
   `en`) en een representatieve afbeelding (`wdt:P18`) voor de iconografische
   onderwerpen (`schema:about`).
4. **muurschilderingendatabase.nl/api (Omeka S REST)** — de SPARQL-graph bevat
   alleen media-URI's, geen thumbnail-URL's. De volledige mediacatalogus
   (~2.900 items) wordt gepagineerd opgehaald en gekoppeld via `o:item`.
5. **PDOK Locatieserver** (`https://api.pdok.nl/bzk/locatieserver/search/v3_1/free`)
   — laatste geometriefallback: gebouwen zonder eigen coördinaat en zonder
   (vindbaar) rijksmonumentnummer hebben soms wel een Reliwiki-link
   (`schema:sameAs`) waar het adres in de URL zelf gecodeerd staat (bv.
   `.../Vaals,_Kerkstraat_47_-_Protestantse_Kerk`). Dat adres wordt
   losgehaald en tegen PDOK geocodeerd.

Alles wordt opgehaald door `scripts/fetch.py`. Ruwe SPARQL-extracten staan in
`data/raw/` (niet gepubliceerd op de site, wel in de repo voor herleidbaarheid).
De site laadt alleen `docs/data/site/*.json` + `gebouwen.geojson`.

## Datamodel

- `docs/data/site/gebouwen.geojson` — één punt per gebouw. `geometrie_bron` is
  `muurschilderingendatabase` (eigen coördinaat uit de bron),
  `rijksmonumentenregister_centroid` (fallback via rijksmonumentnummer) of
  `reliwiki_adres_pdok` (fallback via een in de Reliwiki-link gecodeerd adres,
  gegeocodeerd met PDOK).
- `docs/data/site/muurschilderingen.json` — één record per schildering, met
  `gebouw_id` als foreign key.
- `docs/data/site/onderwerpen.json` — iconografie-index: per Wikidata-subject
  de gekoppelde schildering-id's.
- `docs/data/site/gebouwen_zonder_locatie.json` — gebouwen zonder puntgeometrie
  via geen van de drie bovenstaande routes. Niet stilzwijgend laten vallen:
  ~24 van 576 gebouwen. Een deel daarvan zijn geen "echte" gebouwrecords maar
  losse/ongeïdentificeerde items uit de brondatabase (bv. titels als
  "Onbekend gebouw" of een losse schilderingtitel zonder plaatsnaam) — die
  hebben sowieso geen adres om te geocoderen. Zie de knop "gebouwen zonder
  coördinaten" direct onder de statistiekregel in de kaartweergave.

## Bekende beperkingen

- Sommige `schema:artMedium`/`artworkSurface`-waarden zijn losse tekst i.p.v.
  een thesaurus-URI in de brondata (bv. `"waskrijt?"`) — die komen ongewijzigd
  door.
- Een deel van de Wikidata-`schema:about`-waarden in de brondata is zelf al
  een vrije tekst met een ingebedde wikidata-link (bv.
  `"duiven (https://www.wikidata.org/wiki/Q2984138)")`) in plaats van een
  schone URI-referentie; die worden getoond zoals ze zijn, niet herschreven.
- Van de ~948 iconografische Wikidata-onderwerpen leverde Wikidata voor een
  deel geen `nl`- of `en`-label op (verwijderde/samengevoegde items); die tonen
  het Q-nummer.
- Coördinaten van gebouwen komen uit een Omeka mapping-module zonder
  expliciet lat/lon-onderscheid per triple; het bouwscript classificeert op
  waardebereik (Nederland: breedte 50–54°, lengte 3–7,5°).

## Herbouwen

```bash
pip install -r requirements.txt
python scripts/fetch.py
```

Schrijft `data/raw/*.json` en `docs/data/site/*`. Geen destructieve stappen;
overschrijft alleen de gegenereerde bestanden.

## Vragen over kleurhistorisch onderzoek

Deze verkenner is een technisch zijproject, geen loket. Voor inhoudelijke
vragen over kleurhistorisch onderzoek en/of reconstructieschilderwerk kun je
terecht bij Mariël Polman (m.polman@cultureelerfgoed.nl), RCE.

Gaat het niet om een rijksmonument maar om onderzoek of onderhoud van
schilderingen uit de wederopbouwperiode of post-65, dan is Reinout Morelissen
(r.morelissen@cultureelerfgoed.nl), RCE, het aanspreekpunt.

Algemene informatie over het specialisme Kleur en Schilderingen:

- [Thema Kleur en schilderingen — RCE-kennisbank](https://kennis.cultureelerfgoed.nl/index.php/Thema/Kleur_en_schilderingen)
- [Schilderwerk en kleurhistorie — cultureelerfgoed.nl](https://www.cultureelerfgoed.nl/onderwerpen/schilderwerk-en-kleurhistorie)

## Licenties en attributie

- Broninhoud: RCE Muurschilderingendatabase / RCE Linked Data Voorziening.
- Iconografielabels en -afbeeldingen: Wikidata / Wikimedia Commons, per
  onderwerp eigen licentie (doorgaans CC0/CC BY-SA); zie de Wikidata-link per
  onderwerp.
- Kaartbasis: OpenStreetMap-bijdragers, tiles via OpenFreeMap.
- Deze repository (code + samengestelde datasets): CC BY 4.0, zie `LICENSE`.
