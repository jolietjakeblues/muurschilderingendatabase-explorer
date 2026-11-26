# Methode en herkomst

## Wat dit is

Een statische kaart-, iconografie- en makersverkenner bovenop de linked-data-publicatie
van de [Muurschilderingendatabase](https://muurschilderingendatabase.nl)
(RCE). Geen live queries vanuit de browser: alle data wordt tijdens de build
opgehaald en als platte JSON/GeoJSON gepubliceerd. Onafhankelijk project, geen
officiële RCE-publicatie.

## Bronnen

1. **RCE Linked Data Voorziening, dataset "Muurschilderingen"**
   (`https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Muurschilderingen/sparql`)
   — gebouwen (`gtm:Gebouw`), schilderingen (`schema:Painting`) en hun makers
   (`schema:Person`/`schema:Organization`, gekoppeld via `dcterms:creator`),
   zie `queries/gebouwen.sparql`, `queries/paintings.sparql`,
   `queries/personen.sparql` en `queries/organisaties.sparql`. Dit is
   dezelfde RCE Linked Data-infrastructuur als de Rijksmonumenten/CHO-datasets.
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
   (~3.300 items) wordt gepagineerd opgehaald en gekoppeld via `o:item`. Geen
   IIIF: geen `/iiif/`-endpoints, geen `o-module-iiifserver`-velden in de
   item-/media-API — geverifieerd, geen IIIF Server-module actief bij de bron.
   Daarom een lightbox met de grootst beschikbare Omeka-afgeleide
   (`origineel` > `large` > `medium` > `square`) in plaats van deep-zoom.
5. **PDOK Locatieserver** (`https://api.pdok.nl/bzk/locatieserver/search/v3_1/free`),
   twee toepassingen:
   - **Geometriefallback**: gebouwen zonder eigen coördinaat en zonder
     (vindbaar) rijksmonumentnummer hebben soms wel een Reliwiki-link
     (`schema:sameAs`) waar het adres in de URL zelf gecodeerd staat (bv.
     `.../Vaals,_Kerkstraat_47_-_Protestantse_Kerk`). Dat adres wordt
     losgehaald en tegen PDOK geocodeerd.
   - **Plausibiliteitscheck**: elke eigen coördinaat uit de bron wordt getoetst
     tegen de officiële PDOK-woonplaatslocatie (exacte naam-match, met
     tolerantie voor BAG-disambiguatiesuffixen als "Beuningen Gld" om
     plaatsnaamdubbels — Elsloo bestaat tweemaal — niet per ongeluk af te
     keuren) en verworpen boven 30 km afwijking. Gevonden na een
     gebruikersmelding dat twee gebouwen in België stonden: bleek een bredere
     bronfout, uiteindelijk 4 gebouwen getroffen. Die vier zijn inmiddels in
     de bron hersteld; bij de builds van 24 en 26 november 2026 keurde de check
     niets meer af. Hij blijft aan als vangnet. Zie
     `PLAUSIBILITEITSGRENS_KM` in `scripts/fetch.py`.
6. **RCE Linked Data Voorziening, dataset "Afbeeldingen"**
   (`https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/afbeeldingen/sparql`)
   — Beeldbankfoto's per rijksmonument, voor de koppeling hieronder.
7. **RCE Linked Data Voorziening, dataset "bibliotheek"**
   (`https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/bibliotheek/sparql`)
   — boeken en tijdschriftartikelen per rijksmonument.
8. **RCE Linked Data Voorziening, dataset "monumenten-in-nederland"**
   (`https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/monumenten-in-nederland/sparql`)
   — passages uit de boekenreeks Monumenten in Nederland per rijksmonument.

Alles wordt opgehaald door `scripts/fetch.py`. Ruwe SPARQL-extracten staan in
`data/raw/` (niet gepubliceerd op de site, wel in de repo voor herleidbaarheid),
gesorteerd, zodat de uitkomst niet afhangt van de rijvolgorde van het endpoint.

## Links naar de linked data

De site linkt per item naar de bron als linked data:

- gebouw, schildering en maker naar de browser van de Linked Data Voorziening,
  `https://linkeddata.cultureelerfgoed.nl/rce/Muurschilderingen/browser?resource=<item-URI>`,
  waar de item-URI `https://muurschilderingendatabase.nl/api/items/<id>` is
  (`ldvUrl()` in de JavaScript);
- een rijksmonument naar zijn URI in de dataset cho
  (`https://linkeddata.cultureelerfgoed.nl/cho-kennis/id/rijksmonument/<nr>`),
  gevonden via het rijksmonumentnummer.
De site laadt alleen `docs/data/site/*.json` + `gebouwen.geojson`.

## Datamodel

- `docs/data/site/gebouwen.geojson` — één punt per gebouw. `geometrie_bron` is
  `muurschilderingendatabase` (eigen coördinaat uit de bron, 595 gebouwen),
  `rijksmonumentenregister_centroid` (fallback via rijksmonumentnummer, 36) of
  `reliwiki_adres_pdok` (fallback via een in de Reliwiki-link gecodeerd adres,
  gegeocodeerd met PDOK, 9). `rce` bevat de uitkomst van de koppeling
  (zie hieronder) en is `null` voor gebouwen zonder rijksmonumentnummer.
- `docs/data/site/muurschilderingen.json` — één record per schildering, met
  `gebouw_id` als foreign key en een `makers`-array (elk `{id, naam, type}`,
  type `persoon` of `organisatie`).
- `docs/data/site/onderwerpen.json` — iconografie-index: per Wikidata-subject
  de gekoppelde schildering-id's.
- `docs/data/site/makers.json` — makers-index: per persoon/organisatie naam,
  `type`, geboorte-/sterftedatum (alleen personen), `same_as` (RKD/Wikidata)
  en de gekoppelde schildering-id's. Alleen makers met ≥1 gekoppelde
  schildering worden gepubliceerd (232 van de 272 in de bron: 265 personen en
  7 organisaties); de rest van de
  authority-lijst (nog niet aan een schildering gekoppeld) blijft ongebruikt.
- `docs/data/site/gebouwen_zonder_locatie.json` — alles wat niet op de kaart
  staat, met per regel een `reden`. `geen_coordinaat`: gebouwen zonder
  puntgeometrie via geen van de drie bovenstaande routes, 19 van 659. Een
  deel daarvan zijn geen "echte" gebouwrecords maar losse/ongeïdentificeerde
  items uit de brondatabase (bv. "Onbekend gebouw" met 183 schilderingen, of
  een losse schilderingtitel zonder plaatsnaam) — die hebben sowieso geen
  adres om te geocoderen. `geen_gebouwrecord`: 4 locaties waar schilderingen
  naar verwijzen maar die in de bron geen `gtm:Gebouw` zijn. Zie de knop
  "gebouwen en locaties niet op de kaart" direct onder de statistiekregel in
  de kaartweergave.
- `docs/data/site/metadata.json` — tijdstip van de build en de kerngetallen.
  De krimpcontrole van de volgende build vergelijkt hiermee.

## Koppeling op rijksmonumentnummer

Wat koppelen met andere RCE-datasets oplevert. De sleutel is het
rijksmonumentnummer van het gebouw (opgeschoond tot alleen cijfers,
`clean_rm()`); gebouwen zonder dat nummer doen niet mee. Het resultaat staat
per gebouw in `properties.rce` van `gebouwen.geojson`.

- **Oorspronkelijke functie** (`functies`, `categorieen`, `cho_uri`) uit de
  CHO-dataset (`ceo:heeftOorspronkelijkeFunctie`, alleen kennis met
  `ceo:formeelStandpunt true`), met de hoofdcategorie uit de functiethesaurus:
  de term direct onder "bebouwde omgeving", zoals "Religieuze gebouwen" of
  "Boerderijen, molens en bedrijven". Daarop filtert de keuzelijst
  "Oorspronkelijke functie (RCE)" in de kaartweergave. Zie
  `fetch_cho_functies()`.
- **Beeldbankfoto's** (`beeldbank`) uit de dataset Afbeeldingen, graph
  `photos`. Een foto verwijst met `sdo:about` naar een monumentknoop binnen
  die dataset (`sdo:LandmarksOrHistoricalBuildings`), en die knoop draagt het
  rijksmonumentnummer als `sdo:identifier` (`sdo:PropertyValue` met
  `propertyID` "rijksmonumentnummer"). Per gebouw het totaal, het aantal
  waarvan de titel op een schildering wijst en zes miniaturen, met die foto's
  vooraan. Zie `fetch_beeldbank()`.
- **Passages uit Monumenten in Nederland** (`monumenten_in_nederland`) uit de
  dataset monumenten-in-nederland. Een `min:Passage` draagt
  `min:rijksmonumentnummer` (en `min:noemtRijksmonument` naar de CHO-URI),
  `min:deel`, `sdo:pagination` en `sdo:url` naar de tekst op DBNL. Per passage
  bewaart de verkenner de URI, deel, pagina's, de link en of de tekst een
  schildering noemt; de tekst zelf niet. Zie `fetch_min_passages()`.
- **Literatuur** (`literatuur`) uit de dataset bibliotheek, graphs `books` en
  `article`. Zelfde model als Afbeeldingen: `sdo:about` naar een monumentknoop
  met het rijksmonumentnummer als identifier. Per gebouw het aantal boeken en
  artikelen, hoeveel titels een schildering noemen en de eerste tien titels
  met jaar en link naar de catalogus, schilderingtitels vooraan. Zie
  `fetch_literatuur()`.

"Noemt een schildering" is overal een trefwoordtreffer ("schildering",
"fresco", "beschilder") in titel of tekst, geen inhoudelijke beoordeling.

Stand bij de build van 26 november 2026, voor 579 rijksmonumentnummers:

| Bron | Rijksmonumenten met treffer | Omvang | Noemt een schildering |
|---|---|---|---|
| CHO, oorspronkelijke functie | 562 | — | — |
| Beeldbank | 539 | 60.383 foto's | 8.894 |
| Monumenten in Nederland | 384 | 400 passages | 139 |
| Bibliotheek | 399 | 2.173 boeken, 723 artikelen | 292 |

De 17 nummers die in CHO niet gevonden zijn, zijn vooral recente aanwijzingen
(53xxxx). Foto's, passages en literatuur hangen aan het gebouw, niet aan een
afzonderlijke schildering: daarvoor bestaat geen sleutel.

## Vaste koppelingen

Voor bronnen zonder gedeelde sleutel zijn de koppelingen met de hand gelegd, in
`data/handmatige-koppelingen.json`. Elke regel noemt de bron, de DOI, titel,
soort, auteurs, het `gebouw_id` en/of `maker_id` (itemnummers uit de
Muurschilderingendatabase) en de reden van de koppeling. `scripts/fetch.py`
leest het bestand zonder netwerkaanroep (`load_handmatige_koppelingen()`) en
zet de koppelingen in `vaste_koppelingen` op het gebouw (`gebouwen.geojson`)
en de maker (`makers.json`). De build waarschuwt als een koppeling naar een
gebouw of maker wijst die niet (meer) gepubliceerd wordt.

Nu vier datasets uit het DANS Data Station Social Sciences and Humanities:

| Dataset | DOI | Gekoppeld aan |
|---|---|---|
| Interview Peter Dijkman over de gewelfschilderingen in Naarden | 10.17026/DANS-2BX-V5CU | Grote kerk, Naarden (14832) |
| Interview Willem Haakma Wagenaar over de gewelfschilderingen in Naarden | 10.17026/DANS-X2E-HMB2 | Grote kerk, Naarden (14832) |
| Interview with Vishwa Mehra on the vault paintings in Naarden | 10.17026/DANS-XC9-U77M | Grote kerk, Naarden (14832) |
| Muurschilderingen van F.H. Bach te Beltrum | 10.17026/SS/UGDHSJ | O.L.V. ten Hemelopnemingkerk, Beltrum (10468) en F.H. Bach (10571) |

Criterium: de dataset gaat over dat ene gebouw of die ene maker. Niet
gekoppeld zijn daarom de algemene interviews over het restauratievak (Jonker,
Verheij, Haakma Wagenaar, Bremer), die geen enkel gebouw als onderwerp hebben,
en bouwhistorische rapporten over gebouwen die niet in de
Muurschilderingendatabase staan (o.a. St.-Remigiuskerk Hengelo, De Wheeme
Zwolle, Fokker Terminal Den Haag). De DANS Data Stations hebben een
zoek-API maar geen veld met het rijksmonumentnummer; een automatische
koppeling zou op losse woorden matchen.

## Bekende beperkingen

- Een deel van de `schema:artMedium`/`artworkSurface`-waarden is losse tekst
  i.p.v. een thesaurus-URI in de brondata (bv. `"kalk op pleister"` bij 223
  schilderingen) — die komen ongewijzigd door. Zie
  `data/gevonden-datafouten.md` voor het volledige overzicht van bronfouten.
- `schema:about` staat in de brondata in drie vormen: de entity-URI
  (`http://www.wikidata.org/entity/Q…`), de pagina-URL
  (`https://www.wikidata.org/wiki/Q…`) en vrije tekst met zo'n URL erin (bv.
  `"duiven (https://www.wikidata.org/wiki/Q2984138)"`). Het bouwscript
  herleidt alle drie tot de entity-URI (`normalize_about()`), zodat ze een
  label krijgen en één onderwerp niet over meerdere indexregels verdeeld
  raakt. Waarden zonder Wikidata-verwijzing (een CHT-term, een beeldbanklink)
  blijven ongewijzigd.
- Schilderingen waarvan `schema:location` naar een item wijst dat geen
  `gtm:Gebouw` is, of die helemaal geen locatie hebben, staan niet op de
  kaart. Ze zijn wel te openen via de knop "niet op de kaart" in de
  kaartweergave (`reden: geen_gebouwrecord` in `gebouwen_zonder_locatie.json`,
  respectievelijk de verzamelregel "Schilderingen zonder gekoppeld gebouw").
- De build breekt af, zonder iets weg te schrijven, als een SPARQL-endpoint na
  vijf pogingen of PDOK na vier pogingen onbereikbaar blijft, of als een kerngetal meer dan 10% onder de vorige build
  zakt (`check_tegen_vorige_build()`; bewust overslaan met `ALLOW_SHRINK=1`).
- Van de 901 iconografische onderwerpen hebben er 5 geen label: 3
  Wikidata-items zonder `nl`- of `en`-label en 2 verwijzingen naar een
  CHT-term. Die tonen het laatste deel van de URI.
- Coördinaten van gebouwen komen uit een Omeka mapping-module zonder
  expliciet lat/lon-onderscheid per triple; het bouwscript classificeert per
  marker op waardebereik (Nederland: breedte 50–54°, lengte 3–7,5°).
- 35 gebouwen hebben meerdere markers, vaak één op de plaats ("Blauwhuis,
  Súdwest-Fryslân, Fryslân, Nederland") en één op het gebouw zelf. Markers
  waarvan het label alleen plaats, gemeente en provincie noemt vallen af
  zolang er een andere is; daarna wint het label met de meeste onderdelen, en
  bij gelijke stand het gemiddelde (`pick_marker()`). Dat is een vuistregel
  op het label, geen zekerheid; de verschuiving ten opzichte van de oude
  werkwijze is hooguit zo'n 400 meter.
- De naam van een gebouw is `o:title`, de weergavenaam die Omeka zelf
  gebruikt. 109 gebouwen hebben daarnaast andere titels (bv. de Friese naam);
  die staan in `andere_namen`, worden in het detailpaneel getoond en zijn
  doorzoekbaar. Hetzelfde voor anderstalige plaatsnamen (`plaats_anders`).
- De huidige functie is vrije tekst in de bron, in ruim honderd
  schrijfwijzen. Het filter werkt op `functie_groepen`: een indeling op
  trefwoord in negen groepen (`FUNCTIE_GROEPEN` in `scripts/fetch.py`), waarbij
  een gebouw in meerdere groepen kan vallen. 205 gebouwen hebben geen
  bruikbare waarde ("Onbekend"), 19 vallen in "Overig". De oorspronkelijke
  tekst blijft in `huidige_functie` staan.
- Als afbeelding van een schildering geldt de media die in de bron als
  `o:primary_media` is aangewezen; zonder aanwijzing de eerste uit de API.
- De bron gebruikte `"0"` als sentinel voor "geen datering bekend" bij 20
  schilderingen (bv. wijdingskruizen zonder vastgestelde datering) — geen
  letterlijk jaar 0. Het bouwscript zet dit om naar `null`. Sinds november
  2026 komt de waarde in de bron niet meer voor; de omzetting blijft staan.
- Is van een schildering maar één jaartal bekend, dan toont de kaartweergave
  de vrije dateringstekst uit de bron, en zonder die tekst "vanaf" of "tot"
  het jaartal.
- Van de 232 gepubliceerde makers is een deel geen individueel geïdentificeerde
  persoon maar een naamloze authority-list-entry (bv. "A) Anonieme
  kerkdecoratieschilder", of de generieke RKD/Wikidata-entiteit "anoniem" met
  153 gekoppelde schilderingen) — nodig om ook ongeïdentificeerde makers als
  telbare entiteit te kunnen koppelen, maar geen echte biografie.

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
- Oorspronkelijke functie: rijksmonumentenregister (dataset cho), formeel
  standpunt van de RCE.
- Beeldbankfoto's in het detailpaneel: Beeldbank RCE, per foto een eigen
  licentie (overwegend CC BY-SA 3.0/4.0); elke miniatuur linkt naar de
  detailpagina met maker en licentie.
- Monumenten in Nederland: alleen deel, pagina's en links worden getoond. De
  tekst van de passages is auteursrechtelijk beschermd en staat op DBNL; de
  verkenner neemt hem niet over.
- Literatuur: titel, jaar en link uit de bibliotheekcatalogus van de RCE.
- DANS: alleen titel, soort, auteurs en DOI; de data zelf staat bij DANS, met
  de daar vermelde licentie en toegangsvoorwaarden.
- Iconografielabels en -afbeeldingen: Wikidata / Wikimedia Commons, per
  onderwerp eigen licentie (doorgaans CC0/CC BY-SA); zie de Wikidata-link per
  onderwerp.
- Makersgegevens: doorklik naar [RKD](https://rkd.nl) en Wikidata waar
  beschikbaar; biografische tekst komt uit de brondatabase zelf.
- Kaartbasis: OpenStreetMap-bijdragers, tiles via OpenFreeMap.
- Deze repository (code + samengestelde datasets): CC BY 4.0, zie `LICENSE`.
