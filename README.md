# Muurschilderingendatabase-explorer

Een kaart-, iconografie- en makersverkenner bovenop de linked-data-publicatie
van de [Muurschilderingendatabase](https://muurschilderingendatabase.nl)
(RCE): kerken en andere gebouwen met geregistreerde muurschilderingen,
doorzoekbaar op plaats, rijksmonumentstatus, periode, iconografisch onderwerp
en maker.

Onafhankelijk project, geen officiële RCE-publicatie.

## Wat je kunt doen

- **Kaart**: 637 gebouwen met geregistreerde muurschilderingen, filterbaar op
  naam/plaats, huidige functie, rijksmonumentstatus, oorspronkelijke functie
  volgens het rijksmonumentenregister en periode (histogram met zes
  tijdvakken, van middeleeuwen tot post-65 — 29% van de schilderingen is
  20e-eeuws of later, met een piek in het interbellum). Klik een gebouw voor
  een detailpaneel met alle gekoppelde schilderingen (datering, locatie in het
  gebouw, materiaal/drager, maker, afbeelding, links naar
  Monumentenregister/Wikidata/Reliwiki).
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

Cijfers: build van 24 november 2026 (2866 schilderingen in 656 gebouwen). De
actuele stand staat in `docs/data/site/metadata.json`.

## Proefkoppeling met andere RCE-datasets

Een proef om te laten zien wat koppelen op rijksmonumentnummer oplevert. Van de
580 gebouwen met zo'n nummer krijgen er in het detailpaneel:

- 563 hun **oorspronkelijke functie** uit het rijksmonumentenregister (dataset
  cho, alleen het formele standpunt van de RCE), met de hoofdcategorie uit de
  functiethesaurus. Daarop filtert de keuzelijst "Oorspronkelijke functie
  (RCE)": 418 gebouwen vallen onder "Religieuze gebouwen", 11 onder
  "Boerderijen, molens en bedrijven".
- 539 **foto's uit de Beeldbank** (dataset Afbeeldingen): het aantal per
  gebouw, hoeveel daarvan een schildering in de titel noemen en zes
  miniaturen. Samen 59.524 foto's, waarvan 8.877 met een schildering in de
  titel.

De foto's hangen aan het gebouw, niet aan een afzonderlijke schildering. Zie
`docs/methode.md` voor de querypaden.

## Architectuur

Statische site, geen backend, geen live SPARQL vanuit de browser:

```
RCE Linked Data (SPARQL: Muurschilderingen + cho + Afbeeldingen)
  + Wikidata Query Service (iconografielabels)
  + Omeka REST-API (afbeeldingen)
  + PDOK Locatieserver (geometriefallback + plausibiliteitscheck)
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
af als PDOK na vier pogingen onbereikbaar blijft, of als een kerngetal meer
dan 10% onder de vorige build zakt. Is zo'n daling terecht, draai dan met
`ALLOW_SHRINK=1`.

## Licentie

Code en samengestelde datasets: CC BY 4.0, zie [`LICENSE`](LICENSE). Zie
[`docs/methode.md`](docs/methode.md) voor attributie per brondataset.
