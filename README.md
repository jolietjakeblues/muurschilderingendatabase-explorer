# Muurschilderingendatabase-explorer

Een kaart- en iconografieverkenner bovenop de linked-data-publicatie van de
[Muurschilderingendatabase](https://muurschilderingendatabase.nl) (RCE):
kerken en andere gebouwen met geregistreerde muurschilderingen, doorzoekbaar
op plaats, rijksmonumentstatus en periode, met een aparte iconografie-browser
die schilderingen groepeert op wat erop staat (via Wikidata-onderwerpen).

Onafhankelijk project, geen officiële RCE-publicatie. Ontstaan als zijspoor
van [dodenakkers](https://github.com/jolietjakeblues/dodenakkers) (begraafplaatsen
Zuid-Holland), toen bleek dat de RCE ook een linked-data-dataset voor
muurschilderingen publiceert met een directe koppelsleutel
(`rijksmonumentnummer`) naar het reguliere rijksmonumentenregister.

## Wat je kunt doen

- **Kaart**: alle gebouwen met geregistreerde muurschilderingen, filterbaar op
  naam/plaats, huidige functie en rijksmonumentstatus. Klik een gebouw voor
  een detailpaneel met alle gekoppelde schilderingen (datering, locatie in het
  gebouw, materiaal/drager, afbeelding, links naar Monumentenregister/Wikidata/Reliwiki).
- **Iconografie**: alle ~950 afgebeelde onderwerpen (heiligen, dieren,
  ornamentiek, taferelen, …) als doorzoekbare galerij, elk doorklikbaar naar
  de schilderingen waarin het voorkomt en het gebouw waar die zich bevindt.

## Architectuur

Statische site, geen backend, geen live SPARQL vanuit de browser:

```
RCE Linked Data (SPARQL: Muurschilderingen + cho)
  + Wikidata Query Service (iconografielabels)
  + Omeka REST-API (afbeeldingen)
        │
        ▼  scripts/fetch.py
docs/data/site/*.json + gebouwen.geojson
        │
        ▼
docs/index.html + iconografie.html  (vanilla JS, MapLibre GL)
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
