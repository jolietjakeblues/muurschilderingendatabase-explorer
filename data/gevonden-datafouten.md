# Gevonden datafouten in de Muurschilderingendatabase

Bevindingen tijdens het bouwen van deze verkenner bovenop de linked-data-
publicatie van de Muurschilderingendatabase. Bedoeld om door te geven aan de
bronhouders van [muurschilderingendatabase.nl](https://muurschilderingendatabase.nl) --
niets hiervan is in de brondatabase zelf gecorrigeerd, alleen in de
afgeleide data van deze verkenner (zie `scripts/fetch.py` voor hoe).

Peildatum: build van 2026-09-04/05. Item-URL's verwijzen naar de Omeka-API
van de brondatabase (`https://muurschilderingendatabase.nl/api/items/<id>`);
open die als `.../admin/item/<id>` voor de bewerkbare beheeromgeving.

---

## 1. Coördinaten honderden kilometers mis (4 gebouwen)

De eigen mapping-coördinaat van een gebouw (Omeka mapping-module) is bij
deze vier gebouwen honderden kilometers verkeerd -- alle vier belandden in
België of aan de verkeerde kant van Nederland. Ontdekt doordat een
gebruiker opmerkte dat Ameide en Molenhoek in België lagen; een
systematische check (elke eigen coördinaat tegen de officiële PDOK-
woonplaatslocatie) vond er nog twee.

| Gebouw | Item | Foutieve coördinaat (lat, lon) | Hoort ongeveer bij |
|---|---|---|---|
| Herv. Kerk, Ameide | [items/15019](https://muurschilderingendatabase.nl/api/items/15019) | 50.8773, 4.962269 (Wallonië, bij Nijvel) | 51.947, 4.965 (Ameide, Utrecht) |
| O.L. Vrouw van Zeven Smarten, Molenhoek | [items/13756](https://muurschilderingendatabase.nl/api/items/13756) | 51.1739, 3.862603 (West-Vlaanderen, bij Kortrijk) | 51.770, 5.880 (Molenhoek, Limburg, bij Mook) |
| Kapel in 't Zand, Roermond | [items/14323](https://muurschilderingendatabase.nl/api/items/14323) | 51.90866, 4.477047 (bij Delft) | 51.190, 6.010 (Roermond) |
| Nicolaas, Nieuwveen | [items/15034](https://muurschilderingendatabase.nl/api/items/15034) | 51.37175, 3.471661 (Zeeuws-Vlaanderen) | 52.205, 4.765 (Nieuwveen, Zuid-Holland) |

Geen zichtbaar patroon gevonden (geen consistente coördinaattranspositie of
teken/aseenheidfout) -- lijkt op individuele invoerfouten bij het plaatsen
van de marker in de Omeka-mapping-widget.

## 2. Woonplaats-veld bevat de gebouwnaam, niet de plaatsnaam (1 gebouw)

| Gebouw | Item | Woonplaats-veld bevat | Zou moeten zijn |
|---|---|---|---|
| St.-Maria Magdalenakerk, Goes | [items/11924](https://muurschilderingendatabase.nl/api/items/11924) | `St.-Maria Magdalenakerk` | `Goes` |

De gebouwtitel zelf ("..., Goes") heeft de juiste plaats wel; alleen het
aparte woonplaats-veld is fout ingevuld.

## 3. "0" als datering-sentinel i.p.v. leeg veld (20 schilderingen)

`hasEarliestBeginTimeStamp`/`hasLatestEndTimeStamp` staan bij twintig
schilderingen op de tekstwaarde `"0"` in plaats van leeg. Dat leest een
afnemer al snel als "jaar 0", wat voor een Nederlands gebouw natuurlijk
onmogelijk is. Vrijwel allemaal ongedateerde wijdingskruizen/decoratieve
elementen zonder vastgestelde periode:

- [items/8551](https://muurschilderingendatabase.nl/api/items/8551) -- "6 Kroning van Maria"
- [items/8572](https://muurschilderingendatabase.nl/api/items/8572) -- "5 dierfiguur"
- [items/8574](https://muurschilderingendatabase.nl/api/items/8574) -- "7 twee vrouwen met dierfiguur rechtsboven"
- [items/8245](https://muurschilderingendatabase.nl/api/items/8245) -- "10 a t/m h verschillende wijdingskruizen"
- [items/8246](https://muurschilderingendatabase.nl/api/items/8246) -- "11 a t/m e wapenschilden en tekens"
- [items/8534](https://muurschilderingendatabase.nl/api/items/8534) t/m [8543](https://muurschilderingendatabase.nl/api/items/8543), [8545](https://muurschilderingendatabase.nl/api/items/8545) -- "10a" t/m "10k. Decoratieve cirkel" (11 items)
- [items/8546](https://muurschilderingendatabase.nl/api/items/8546), [8547](https://muurschilderingendatabase.nl/api/items/8547), [8554](https://muurschilderingendatabase.nl/api/items/8554), [8573](https://muurschilderingendatabase.nl/api/items/8573) -- "9a/9b/9 Wijdingskruis", "6 wijdingskruis"

## 4. `schema:temporal` bevat een interne item-URL i.p.v. tekst (3 schilderingen)

Bij drie schilderingen staat in het temporal-veld een `.../api/items/<id>`-
URL naar een ander item, in plaats van een tekstuele datering. Vermoedelijk
per ongeluk een link geplakt waar een omschrijving hoorde te staan.

| Item | Foutieve waarde | Vermoedelijk bedoeld |
|---|---|---|
| [items/10172](https://muurschilderingendatabase.nl/api/items/10172) "Tekstcartouche derde travee noordmuur" | `.../items/10170` | vrije tekst, zie evt. het gelinkte item 10170 |
| [items/10173](https://muurschilderingendatabase.nl/api/items/10173) "Tekstcartouche vijfde travee noordmuur" | `.../items/10170` | idem |
| [items/10234](https://muurschilderingendatabase.nl/api/items/10234) "Sint-Christoffel" | `.../items/10147` | idem |

Bijkomstig: bij minstens één zustertravee ([items/10172](https://muurschilderingendatabase.nl/api/items/10172),
tweede voorkomen in de brondata) staat wél de juiste tekst `"zie bij
RM11681MU1"` naast deze foutieve URL -- lijkt op een dubbele/verkeerd
samengevoegde waarde voor hetzelfde veld.

## 5. `schema:about` (iconografie) soms vrije tekst met ingebedde link i.p.v. schone URI (10 schilderingen)

In plaats van een schone Wikidata-URI staat het veld soms op een string als
`"duiven (https://www.wikidata.org/wiki/Q2984138)"` -- een leesbaar label
met de link erachteraan, geen bruikbare RDF-referentie voor wie dit veld
als URI wil consumeren.

- [items/14577](https://muurschilderingendatabase.nl/api/items/14577) -- `skelet (https://www.wikidata.org/wiki/Q7881)`
- [items/14586](https://muurschilderingendatabase.nl/api/items/14586) -- `eend (https://www.wikidata.org/wiki/Q3736439)`
- [items/14557](https://muurschilderingendatabase.nl/api/items/14557), [14386](https://muurschilderingendatabase.nl/api/items/14386), [14512](https://muurschilderingendatabase.nl/api/items/14512), [14516](https://muurschilderingendatabase.nl/api/items/14516), [14517](https://muurschilderingendatabase.nl/api/items/14517), [14518](https://muurschilderingendatabase.nl/api/items/14518), [14603](https://muurschilderingendatabase.nl/api/items/14603), [14606](https://muurschilderingendatabase.nl/api/items/14606) -- `vrouw (https://www.wikidata.org/wiki/Q467)`
- [items/14384](https://muurschilderingendatabase.nl/api/items/14384) -- `karikatuur (https://www.wikidata.org/wiki/Q482919)`
- [items/14412](https://muurschilderingendatabase.nl/api/items/14412) -- `Kozakken (https://www.wikidata.org/wiki/Q47805)`
- [items/14413](https://muurschilderingendatabase.nl/api/items/14413) -- `Fransen (https://www.wikidata.org/wiki/Q9070972)`
- [items/14444](https://muurschilderingendatabase.nl/api/items/14444), [14445](https://muurschilderingendatabase.nl/api/items/14445), [14513](https://muurschilderingendatabase.nl/api/items/14513), [14595](https://muurschilderingendatabase.nl/api/items/14595) -- `militair (https://www.wikidata.org/wiki/Q47064)`
- [items/14522](https://muurschilderingendatabase.nl/api/items/14522) -- `Pierrette (https://www.wikidata.org/wiki/Q17309)`
- [items/14561](https://muurschilderingendatabase.nl/api/items/14561) -- `man (https://www.wikidata.org/wiki/Q8441)`

## 6. `schema:artMedium`/`artworkSurface` soms vrije tekst i.p.v. thesaurusconcept (minder dringend)

37 verschillende waarden in totaal voor materiaal/drager; drie daarvan zijn
losse tekst in plaats van een thesaurus-URI, bijvoorbeeld `"waskrijt?"`,
`"kalk"`, `"overig"` (exacte items niet apart bijgehouden -- makkelijk
terug te vinden door in de admin te filteren op deze drie materiaal-/
drager-waarden). Minder urgent dan de bovenstaande punten: leesbaar voor
een mens, alleen niet machinaal koppelbaar aan de rest van de thesaurus.

---

## Wat hier al automatisch mee gebeurt in deze verkenner

- **§1**: coördinaat verworpen als hij >30 km van de officiële PDOK-
  woonplaatslocatie ligt; valt dan terug op de rijksmonumentgeometrie of
  een uit een Reliwiki-link geëxtraheerd adres. Zie `scripts/fetch.py`,
  `PLAUSIBILITEITSGRENS_KM`.
- **§3**: `"0"` wordt uitgefilterd naar `null`. Zie `clean_year()` in
  `scripts/fetch.py`.
- **§4**: de specifieke stray-URL-waarde `.../items/10170` wordt uitgefilterd
  (puntfix, geen generieke detectie van dit patroon). Zie de `temporeel`-
  filter in `scripts/fetch.py`, vlak voor `group_by_subject(painting_rows, ...)`.
- **§2, §5, §6**: niet gecorrigeerd, alleen hierboven gedocumenteerd -- te
  weinig gevallen/te riskant om automatisch te gokken wat de bedoelde
  waarde was.
