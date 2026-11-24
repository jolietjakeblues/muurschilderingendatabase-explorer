# Gevonden datafouten in de Muurschilderingendatabase

Bevindingen tijdens het bouwen van deze verkenner bovenop de linked-data-
publicatie van de Muurschilderingendatabase. Bedoeld om door te geven aan de
bronhouders van [muurschilderingendatabase.nl](https://muurschilderingendatabase.nl) --
niets hiervan is in de brondatabase zelf gecorrigeerd, alleen in de
afgeleide data van deze verkenner (zie `scripts/fetch.py` voor hoe).

Peildatum: build van 2026-11-24 (2866 schilderingen, 656 gebouwen). De eerste
versie van dit overzicht had als peildatum 2026-09-04/05; wat sindsdien in de
bron is hersteld, staat onderaan. Item-nummers verwijzen naar de Omeka-API van
de brondatabase (`https://muurschilderingendatabase.nl/api/items/<id>`); open
die als `.../admin/item/<id>` voor de bewerkbare beheeromgeving.

---

## 1. Woonplaats-veld bevat de gebouwnaam erbij (1 gebouw)

| Gebouw | Item | Woonplaats-veld bevat | Zou moeten zijn |
|---|---|---|---|
| Sint-Bonifatiuskerk, Alphen aan den Rijn | [items/15869](https://muurschilderingendatabase.nl/api/items/15869) | `Sint-Bonifatiuskerk, Alphen aan den Rijn` | `Alphen aan den Rijn` |

Minder ernstig, zelfde veld: [items/14318](https://muurschilderingendatabase.nl/api/items/14318)
(Martinus, Spekholzerheide) heeft `Kerkrade (Spekholzerheide)`. Tien gebouwen
hebben helemaal geen woonplaats.

## 2. Dateringsvelden met een onmogelijke of afwijkende waarde (4 schilderingen)

`hasEarliestBeginTimeStamp`/`hasLatestEndTimeStamp` bevatten overal een
jaartal van vier cijfers, behalve hier:

| Item | Begin | Eind | Wat er mis is |
|---|---|---|---|
| [items/7967](https://muurschilderingendatabase.nl/api/items/7967) "Heilige Andreas" | `1500` | `150` | eindjaar mist een cijfer, vermoedelijk 1500 |
| [items/14138](https://muurschilderingendatabase.nl/api/items/14138) "Beschilderd koepelgewelf" | `1949` | `1948` | begin na eind |
| [items/14005](https://muurschilderingendatabase.nl/api/items/14005) "Datum 2 april '40" | `1940-04-02` | `1940-04-02` | volledige datum in een jaarveld |
| [items/16623](https://muurschilderingendatabase.nl/api/items/16623) "Zeegezicht met schepen en vliegtuigen" | `1940-02-15` | `1940-02-15` | idem |

De volledige datums zijn inhoudelijk juist, maar wie het veld als jaartal
leest, moet er rekening mee houden.

## 3. `schema:temporal` bevat een URL i.p.v. tekst (2 schilderingen)

| Item | Waarde |
|---|---|
| [items/14086](https://muurschilderingendatabase.nl/api/items/14086) "Mariacyclus" | `https://resolver.kb.nl/resolve?urn=KBPERS01:003011015:mpeg21:a00017` |
| [items/14089](https://muurschilderingendatabase.nl/api/items/14089) "Verlossingscyclus (Hemelvaart en Laatste Oordeel)" | dezelfde URL |

Een krantenartikel als bron voor de datering hoort in een bronveld, niet in de
tekstuele datering. Beide items hebben wel een begin- en eindjaar (1280-1300).

## 4. `schema:about` (iconografie) in de pagina-vorm van Wikidata (90 schilderingen)

Bij 90 schilderingen staat een onderwerp als
`https://www.wikidata.org/wiki/Q…` (de webpagina) in plaats van
`http://www.wikidata.org/entity/Q…` (de entiteit): 112 verschillende waarden,
178 koppelingen. Alle in de recentere invoer (items 13942 t/m 16633), bv.
[items/13942](https://muurschilderingendatabase.nl/api/items/13942) en
[items/14654](https://muurschilderingendatabase.nl/api/items/14654) met
`https://www.wikidata.org/wiki/Q201171`.

Gevolg voor afnemers: hetzelfde onderwerp bestaat onder twee URI's, en de
pagina-vorm levert op Wikidata geen label op. Op te sporen met een filter op
`/wiki/` in het veld.

Twee schilderingen verwijzen in dit veld naar een CHT-term in plaats van
Wikidata: [items/12075](https://muurschilderingendatabase.nl/api/items/12075)
en [items/16354](https://muurschilderingendatabase.nl/api/items/16354). Dat
hoeft geen fout te zijn, maar het is de enige afwijking van de Wikidata-lijn.

## 5. `schema:artMedium`/`artworkSurface` als vrije tekst of in de pagina-vorm van de AAT

**Drager als vrije tekst.** Verreweg de grootste groep: `kalk op pleister`
bij 223 schilderingen (items 8190 t/m 8607, één invoerreeks). Daarnaast
`kalk` (5), `kalei` (4), `pleister` (3), en eenmalig `Pleister`,
`Pleisterlaag op kalk`, `pleisterlaag met kalk`, `kalkverf`,
`Cementhoudende pleister` en `overig`.

**Materiaal als vrije tekst.** `temperaverf, ei of caseine` (4: items 8448,
8459, 8475, 8478), en eenmalig `caseïne of ei, olie en was`
([16343](https://muurschilderingendatabase.nl/api/items/16343)), `Keimfarben`
en `silicaatverf` ([16297](https://muurschilderingendatabase.nl/api/items/16297)),
`zwarte oker` ([10390](https://muurschilderingendatabase.nl/api/items/10390))
en `siliconenharsemulsie` + `acryl` in één waarde met een regeleinde ertussen
([16308](https://muurschilderingendatabase.nl/api/items/16308)).

**Materiaal in de pagina-vorm van de AAT.** Twaalf schilderingen (items 13988,
13991, 13998, 13999, 14000, 14019-14022, 15986, 16220, 16221) verwijzen naar
`http://vocab.getty.edu/page/aat/<nr>` in plaats van het concept
`http://vocab.getty.edu/aat/<nr>`. Zelfde probleem als bij §4: de pagina-URL
is geen concept en krijgt geen label.

Leesbaar voor een mens, maar niet machinaal koppelbaar aan de thesaurus.

## 6. Rijksmonumentnummer vervuild of dubbel (4 gebouwen)

| Gebouw | Item | Waarde | Opmerking |
|---|---|---|---|
| Etzenraderhof, Jabeek | [items/14157](https://muurschilderingendatabase.nl/api/items/14157) | `RM35671` | voorvoegsel "RM" |
| Herv. Kerk, Vaals | [items/14162](https://muurschilderingendatabase.nl/api/items/14162) | `RM36625` | voorvoegsel "RM" |
| Woonhuis, Gouda | [items/15874](https://muurschilderingendatabase.nl/api/items/15874) | `517621` + regeleinde | regeleinde achter het nummer |
| Kasteel Wijnandsrade | [items/12028](https://muurschilderingendatabase.nl/api/items/12028) | `30901` en `30902` | twee nummers; kan terecht zijn (complex) |

Het nummer is de sleutel naar het rijksmonumentenregister en de Beeldbank; met
voorvoegsel of regeleinde werkt die koppeling niet.

## 7. `schema:location` wijst niet naar een gebouwrecord, of ontbreekt (19 schilderingen)

**Locatie is geen `gtm:Gebouw`** (11 schilderingen op 4 locaties). Het
doelitem bestaat, maar heeft een ander type, waardoor het niet tussen de
gebouwen staat:

| Locatie | Item | Schilderingen |
|---|---|---|
| Voormalige Galileërkerk | [items/10239](https://muurschilderingendatabase.nl/api/items/10239) | 10244, 10247, 10248, 10249, 10250, 10251 |
| Oostlijn (metrolijn in Amsterdam) | [items/11639](https://muurschilderingendatabase.nl/api/items/11639) | 10246, 11640, 13139 |
| Metrostation Waterlooplein, Amsterdam | [items/11641](https://muurschilderingendatabase.nl/api/items/11641) | 11643 |
| Rietveld-Schröderhuis, Utrecht | [items/16177](https://muurschilderingendatabase.nl/api/items/16177) | 16179 |

Het Rietveld-Schröderhuis ([items/16177](https://muurschilderingendatabase.nl/api/items/16177))
is zelf als `schema:Painting` getypeerd en heeft geen locatie.

**Geen locatie** (8 schilderingen): [10650](https://muurschilderingendatabase.nl/api/items/10650)
"Triomfboog", [10724](https://muurschilderingendatabase.nl/api/items/10724),
[10816](https://muurschilderingendatabase.nl/api/items/10816),
[10940](https://muurschilderingendatabase.nl/api/items/10940),
[10995](https://muurschilderingendatabase.nl/api/items/10995),
[11897](https://muurschilderingendatabase.nl/api/items/11897),
[15847](https://muurschilderingendatabase.nl/api/items/15847) "Grisailles
buitengevel Hofwijck" en 16177 hierboven.

## 8. Gebouwrecords die een schildering lijken te zijn (4 records)

Vier items van het type `gtm:Gebouw` hebben de titel van een schildering, geen
plaats, geen coördinaat en geen gekoppelde schilderingen:
[items/13216](https://muurschilderingendatabase.nl/api/items/13216)
"Plafondschildering met ornamenten en medaillons",
[items/14014](https://muurschilderingendatabase.nl/api/items/14014) "Melkkoe",
[items/15251](https://muurschilderingendatabase.nl/api/items/15251) "Restant
muurschildering" en
[items/15375](https://muurschilderingendatabase.nl/api/items/15375) "Laatste
Oordeel". Vermoedelijk met het verkeerde sjabloon ingevoerd.

Ter kennisgeving: 183 schilderingen hangen aan het verzamelrecord "Onbekend
gebouw" ([items/12129](https://muurschilderingendatabase.nl/api/items/12129)).
Dat is geen fout, maar die schilderingen zijn zo niet te plaatsen.

## 9. Meerdere waarden in een veld dat er één hoort te hebben (10 schilderingen)

| Veld | Item | Waarden |
|---|---|---|
| locatie | [items/15390](https://muurschilderingendatabase.nl/api/items/15390) "De bespotting van Noach" | gebouw 15389 en 15392 |
| locatie | [items/12769](https://muurschilderingendatabase.nl/api/items/12769) "Biddende man" | gebouw 12643 en 12768 |
| beginjaar | [items/10981](https://muurschilderingendatabase.nl/api/items/10981) "Allegorie op het vakbondswezen" | 1899 en 1902 |
| eindjaar | items 12136, 12137, 12139, 12143, 12144 | 1932 en 1933 |
| `schema:temporal` | [items/16416](https://muurschilderingendatabase.nl/api/items/16416) en [16417](https://muurschilderingendatabase.nl/api/items/16417) | drie historische gebeurtenissen (1950, 1951, 1977) |

Bij 16416/16417 staan gebeurtenissen in het dateringsveld; in de ene staat
"Zuid-Molukse", in de andere "Zuid Molukse".

## 10. Huidige functie bevat een URL of is niet genormaliseerd

Twee gebouwen hebben een URL in `ceo:heeftHuidigeFunctie`:

| Gebouw | Item | Waarde |
|---|---|---|
| Nederlands-Hervormde Kerk te Hantumhuizen | [items/10187](https://muurschilderingendatabase.nl/api/items/10187) | `https://aldefrysketsjerken.nl/hantumhuzen` (naast `kerkdiensten en voor verhuur`) |
| Stadsschouwburg, Amsterdam | [items/15821](https://muurschilderingendatabase.nl/api/items/15821) | `https://www.wikidata.org/wiki/Q24354` |

Breder: het veld is vrije tekst met ruim honderd schrijfwijzen voor een
handvol functies (`kerk`, `Kerk`, `Kerk / Hervormde kerk`, `Kerk / Hervormde
Kerk`, `Kerk / Protestanse kerk`, ...) en ontbreekt bij ongeveer 200 gebouwen.
Een keuzelijst of thesaurusterm zou het filterbaar maken.

## 11. Meerdere markers per gebouw, waarvan één op de plaats (35 gebouwen)

35 gebouwen hebben meer dan één marker in de mapping-module. Vaak is er één op
de plaats gezet en één op het gebouw, bv.
[items/10433](https://muurschilderingendatabase.nl/api/items/10433) (St.
Vituskerk te Blauwhuis): "Blauwhuis, Súdwest-Fryslân, Fryslân, Nederland"
naast tweemaal "St. Vituskerk, Vitusdyk, Blauwhuis, ...". Bij
[items/15773](https://muurschilderingendatabase.nl/api/items/15773)
(Kanonkazemat Diefdijk-Zuid) liggen de twee bijna 4 km uit elkaar. Een afnemer
weet niet welke marker de bedoelde is; de overbodige verwijderen lost dat op.

## 12. Ter controle: rijksmonumentnummers die niet in de CHO-dataset staan (15 gebouwen)

Deze nummers leveren geen `ceo:Rijksmonument` op in de RCE-dataset cho. Het
zijn vooral forten van de Hollandse Waterlinies met een recent nummer
(53xxxx), dus waarschijnlijk klopt het nummer en loopt cho achter of gaat het
om een ander objecttype. Niet zeker een fout in de Muurschilderingendatabase.

Fort Everdingen (531650), Fort Honswijk (531624), Fort de Batterijen (531561),
Fort bij Asperen (531771), WKU Tull en 't Waal (531611), Lunet aan de Snel
(531619), Fort De Bilt (532373), Fort Ruigenhoek (532306), Fort Vechten
(531252), Fort Voordorp (532351), Fort bij Rijnauwen (531112), Fort
Nieuwersluis (531452), Kasteel Rijnhuizen (522603), Fogelsangh State (408906)
en Schoolgebouwencomplex Amsterdam (527796).

---

## Sinds de eerste versie hersteld in de bron

Vastgesteld op de build van 2026-11-24; deze punten uit de versie van september
komen niet meer voor.

- **Coördinaten honderden kilometers mis** (Ameide 15019, Molenhoek 13756,
  Kapel in 't Zand Roermond 14323, Nieuwveen 15034): alle vier liggen nu op de
  juiste plek. Geen enkele eigen coördinaat wordt nog afgekeurd.
- **Woonplaats-veld van de St.-Maria Magdalenakerk** (11924): nu `Goes`.
- **`"0"` als datering-sentinel** (20 schilderingen): komt niet meer voor.
- **Interne item-URL in `schema:temporal`** (10172, 10173, 10234): verdwenen.
  Wel twee nieuwe gevallen met een externe URL, zie §3.
- **`schema:about` als vrije tekst met ingebedde link**
  (`"duiven (https://www.wikidata.org/wiki/Q2984138)"`): komt niet meer voor.
  De waarden zijn nu kale URL's, maar in de pagina-vorm, zie §4.

## Wat hier automatisch mee gebeurt in deze verkenner

- **§2**: niets; de waarden komen ongewijzigd door. `150` maakt dat het
  detailpaneel "150-1500" toont.
- **§3**: niets. De tekst wordt alleen getoond als begin- of eindjaar
  ontbreekt, dus deze twee URL's zijn niet zichtbaar. Het filter in
  `scripts/fetch.py` vangt alleen interne item-URL's af.
- **§4**: beide vormen worden herleid tot de entity-URI. Zie
  `normalize_about()`.
- **§5**: vrije tekst wordt getoond zoals hij is; de AAT-pagina-URL's krijgen
  geen label.
- **§6**: het nummer wordt teruggebracht tot de cijfers (`clean_rm()`); bij
  twee nummers wint het laagste.
- **§7**: de vier locaties en de schilderingen zonder locatie staan in de
  lijst "niet op de kaart" en zijn daar te openen.
- **§9**: de rijen worden eerst gesorteerd, daarna wint de eerste waarde. De
  keuze is dus willekeurig maar bij elke build dezelfde.
- **§10**: een URL telt als "Onbekend"; de overige waarden worden op
  trefwoord gegroepeerd voor het filter (`functie_groepen()`).
- **§11**: markers met alleen plaats, gemeente en provincie in het label
  vallen af als er een specifiekere is (`pick_marker()`).
- **Coördinaten**: de plausibiliteitscheck (30 km van de PDOK-woonplaats,
  `PLAUSIBILITEITSGRENS_KM`) blijft aan, ook nu hij niets meer afkeurt.
- **`"0"` als jaartal**: `clean_year()` blijft staan voor het geval de
  sentinel terugkomt.
