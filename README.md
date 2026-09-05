# Muurschilderingendatabase-explorer

Een kaart-, iconografie- en makersverkenner bovenop de linked-data-publicatie
van de [Muurschilderingendatabase](https://muurschilderingendatabase.nl)
(RCE): kerken en andere gebouwen met geregistreerde muurschilderingen,
doorzoekbaar op plaats, rijksmonumentstatus, periode, iconografisch onderwerp
en maker.

Onafhankelijk project, geen officiële RCE-publicatie.

## Wat je kunt doen

- **Kaart**: alle gebouwen met geregistreerde muurschilderingen, filterbaar op
  naam/plaats, huidige functie, rijksmonumentstatus en periode (histogram met
  zes tijdvakken, van middeleeuwen tot post-65 — 29% van de schilderingen is
  20e-eeuws, met een piek in het interbellum). Klik een gebouw voor een
  detailpaneel met alle gekoppelde schilderingen (datering, locatie in het
  gebouw, materiaal/drager, maker, afbeelding, links naar
  Monumentenregister/Wikidata/Reliwiki).
- **Iconografie**: alle ~950 afgebeelde onderwerpen (heiligen, dieren,
  ornamentiek, taferelen, …) als doorzoekbare galerij, elk doorklikbaar naar
  de schilderingen waarin het voorkomt en het gebouw waar die zich bevindt.
- **Makers**: 217 kunstenaars en restauratieateliers met minstens één
  gekoppelde schildering (210 bij naam bekend, met geboorte-/sterfjaar en
  doorklik naar RKD/Wikidata waar beschikbaar), elk met een galerij van hun
  werk.
- **Lightbox**: klik een schilderingafbeelding voor de grootst beschikbare
  versie op donkere achtergrond (geen IIIF/deep-zoom beschikbaar bij de bron —
  geverifieerd, zie `docs/methode.md`).
- Mobielvriendelijk: kaart en lijst worden op een telefoon uitschuivende
  bottom sheets i.p.v. een vaste zijkolom.

## Architectuur

Statische site, geen backend, geen live SPARQL vanuit de browser:

```
RCE Linked Data (SPARQL: Muurschilderingen + cho)
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
`docs/data/site/`. Run het opnieuw (handmatig, of via de geplande
GitHub Action) om nieuwe schilderingen/gebouwen uit de bron mee te nemen.

## Licentie

Code en samengestelde datasets: CC BY 4.0, zie [`LICENSE`](LICENSE). Zie
[`docs/methode.md`](docs/methode.md) voor attributie per brondataset.
