# Muurschilderingendatabase-explorer

Een kaart-, iconografie- en makersverkenner bovenop de linked-data-publicatie
van de [Muurschilderingendatabase](https://muurschilderingendatabase.nl)
(RCE): kerken en andere gebouwen met geregistreerde muurschilderingen,
doorzoekbaar op plaats, rijksmonumentstatus, periode, iconografisch onderwerp
en maker.

Onafhankelijk project, geen officiële RCE-publicatie.

## Wat je kunt doen

- **Kaart**: 640 gebouwen met geregistreerde muurschilderingen, filterbaar op
  naam/plaats (ook op andere namen, zoals de Friese), huidige functie
  (gegroepeerd), rijksmonumentstatus, oorspronkelijke functie volgens het
  rijksmonumentenregister en periode (histogram met zes tijdvakken, van
  middeleeuwen tot post-65 — 29% van de schilderingen is 20e-eeuws of later,
  met een piek in het interbellum). Klik een gebouw voor een detailpaneel met
  alle gekoppelde schilderingen (datering, locatie in het gebouw,
  materiaal/drager, maker, beschrijving, afbeelding, links naar
  Monumentenregister/Wikidata/Reliwiki).
- **Links naar de linked data**: elk gebouw, elke schildering en elke maker
  linkt naar zijn eigen pagina in de Linked Data Voorziening van de RCE
  (dataset Muurschilderingen); een rijksmonument daarnaast naar zijn URI in de
  dataset cho.
- **Niet op de kaart**: 19 gebouwen zonder vindbare locatie, 4 locaties die in
  de bron geen gebouwrecord zijn en 8 schilderingen zonder gebouw staan in een
  aparte lijst onder de filters; hun schilderingen zijn daar gewoon te openen.
- **Iconografie**: de ~900 afgebeelde onderwerpen (heiligen, dieren,
  ornamentiek, taferelen, …) als doorzoekbare galerij, elk doorklikbaar naar
  de schilderingen waarin het voorkomt en het gebouw waar die zich bevindt.
- **Makers**: 232 kunstenaars en restauratieateliers met minstens één
  gekoppelde schildering (225 bij naam bekend, met geboorte-/sterfjaar en
  doorklik naar RKD/Wikidata waar beschikbaar), elk met een galerij van hun
  werk.
- **Lightbox**: klik een schilderingafbeelding voor de grootst beschikbare
  versie op donkere achtergrond (geen IIIF/deep-zoom beschikbaar bij de bron —
  geverifieerd, zie `docs/methode.md`).
- Mobielvriendelijk: kaart en lijst worden op een telefoon uitschuivende
  bottom sheets i.p.v. een vaste zijkolom.

Cijfers: build van 26 november 2026 (2868 schilderingen in 659 gebouwen). De
actuele stand staat in `docs/data/site/metadata.json`.

## Koppeling met andere RCE-datasets

Wat koppelen op rijksmonumentnummer oplevert. Van de 583 gebouwen met zo'n
nummer krijgen er in het detailpaneel:

- 566 hun **oorspronkelijke functie** uit het rijksmonumentenregister (dataset
  cho, alleen het formele standpunt van de RCE), met de hoofdcategorie uit de
  functiethesaurus. Daarop filtert de keuzelijst "Oorspronkelijke functie
  (RCE)": 420 gebouwen vallen onder "Religieuze gebouwen", 11 onder
  "Boerderijen, molens en bedrijven".
- 542 **foto's uit de Beeldbank** (dataset Afbeeldingen): het aantal per
  gebouw, hoeveel daarvan een schildering in de titel noemen en zes
  miniaturen. Samen 60.383 foto's, waarvan 8.894 met een schildering in de
  titel.
- 386 de **passage uit Monumenten in Nederland** (dataset
  monumenten-in-nederland): deel en pagina's, met een link naar de tekst op
  DBNL en naar de passage als linked data. Van de 400 passages noemen er 139
  een schildering. De tekst zelf wordt niet overgenomen.
- 397 **literatuur uit de bibliotheek van de RCE** (dataset bibliotheek): het
  aantal boeken en artikelen en de eerste tien titels met link naar de
  catalogus, titels over schilderingen vooraan. Samen 2.173 boeken en 723
  artikelen, waarvan 292 met een schildering in de titel.

Foto's, passages en literatuur hangen aan het gebouw, niet aan een
afzonderlijke schildering. Zie `docs/methode.md` voor de querypaden.

## Vaste koppelingen (DANS)

Voor bronnen zonder gedeelde sleutel staan de koppelingen met de hand in
[`data/handmatige-koppelingen.json`](data/handmatige-koppelingen.json): per
dataset de DOI en het gebouw of de maker waar die over gaat. Nu vier datasets
uit de DANS Data Stations: drie interviews over de gewelfschilderingen in de
Grote Kerk te Naarden en het vooronderzoek naar de muurschilderingen van F.H.
Bach in Beltrum (gekoppeld aan de kerk en aan de maker). Een nieuwe koppeling
toevoegen is een regel in dat bestand en een nieuwe build.

## Architectuur

Statische site, geen backend, geen live SPARQL vanuit de browser:

```
RCE Linked Data (SPARQL: Muurschilderingen + cho + Afbeeldingen
                         + bibliotheek + monumenten-in-nederland)
  + Wikidata Query Service (iconografielabels)
  + Omeka REST-API (afbeeldingen)
  + PDOK Locatieserver (geometriefallback + plausibiliteitscheck)
  + data/handmatige-koppelingen.json (vaste koppelingen, nu DANS)
        │
        ▼  scripts/fetch.py
docs/data/site/*.json + gebouwen.geojson
        │
        ▼
docs/index.html + iconografie.html + makers.html  (vanilla JS, MapLibre GL)
```

Zie [`docs/methode.md`](docs/methode.md) voor de volledige herkomst,
datamodel en bekende beperkingen.

## Lokaal draaien

```bash
pip install -r requirements.txt
python scripts/fetch.py        # ververst docs/data/site/
cd docs && python -m http.server 8000
```

## Hosten

GitHub Pages, bron: branch `main`, map `/docs` (Settings → Pages). Geen
build-Action nodig — de site is al statisch gegenereerd.

## Data verversen

`scripts/fetch.py` is idempotent en overschrijft alleen `data/raw/` en
`docs/data/site/`. Run het opnieuw (handmatig, of via de maandelijkse
GitHub Action) om nieuwe schilderingen/gebouwen uit de bron mee te nemen.

De build schrijft niets weg als de uitkomst niet te vertrouwen is: hij breekt
af als een SPARQL-endpoint na vijf pogingen of PDOK na vier pogingen
onbereikbaar blijft, of als een kerngetal meer dan 10% onder de vorige build
zakt. De ruwe extracts worden gesorteerd weggeschreven, zodat een verversing
alleen de echte wijzigingen in de bron als diff laat zien. Is zo'n daling terecht, draai dan met
`ALLOW_SHRINK=1`.

## Licentie

Code en samengestelde datasets: CC BY 4.0, zie [`LICENSE`](LICENSE). Zie
[`docs/methode.md`](docs/methode.md) voor attributie per brondataset.
