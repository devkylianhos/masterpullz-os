# Master Pullz OS · overdracht

Lees dit voordat je iets bouwt. Het staat vol besluiten die met opzet zo zijn
genomen. Draai ze niet terug omdat ze op het eerste gezicht raar lijken.

Klant: Master Pullz Expo, organiseert TCG beurzen in Nederland.
Eerstvolgende editie: Heerenveen ronde 2, 27 september 2026.
Ticketverkoop loopt via Weticket.

## Waar alles staat

| Pad | Wat |
|---|---|
| `contract/validate.py` | Contract v1.0. Keurt de payload goed of af. |
| `data/demo.json` | De fixture. Loopt nu achter op het ontwerp, zie open punten. |
| `data/latest.json` | Wat het dashboard toont. Wordt door de pijplijn geschreven. |
| `src/styles.css` | De echte styling van het product. |
| `hermes/` | Pijplijn, skill en cronjobs. |
| `tools/linkbouwer.html` | Bouwt trackinglinks per beurs en dwingt de naamgeving af. |
| Paper bestand `Dashboard masterpullz` | Het ontwerp. Negen artboards. |

`src/index.html` en `src/render.js` bestaan nog niet. Dat is het grootste gat.

## Besluiten die vastliggen

**De payload bevat alleen metingen.** Tellingen en bedragen. Geen ROAS, CPA,
CTR, conversie of aandeel. Die worden in de UI berekend. Reden: bij de eerste
opzet zaten er verhoudingen in de brief die wiskundig niet konden bestaan naast
de kanaaltabel. Als een agent een ratio mag aanleveren, kan hij een getal
publiceren dat niet klopt met zijn eigen invoer. Deze regel maakt dat onmogelijk.

**Validatie faalt betekent niet publiceren.** De oude payload blijft staan met
zijn eerlijke tijdstempel. Nooit de payload met de hand bijwerken om de
validatie langs te komen.

**Vijf betaalde kanalen: meta, google, tiktok, snapchat, reddit.** Plus een rij
"Direct en overig" voor bezoekers die zonder UTM in de shop landen. E-mail,
organic, direct en referral als aparte kanalen zijn eruit, die worden nu niet
gebruikt.

**De funnel heeft vier stappen**, niet vijf: impressies, shopbezoek, checkout
gestart, ticket gekocht. Advertenties linken rechtstreeks naar de Weticket shop
en slaan de website over. De website is een apart organisch pad.

**Trackinglinks.** `utm_medium` is altijd `cpc`, ook voor social. Waarden als
`socialads` worden door geen enkele tool herkend en belanden bij organisch
verkeer. `utm_campaign` is de editie plus eventueel de campagne, gescheiden door
een dubbel streepje: `heerenveen-2026-09-27--early-bird`. Alles kleine letters.

**Visuele richting is Apple.** Randloze kaarten met een lichte schaduw, radius 18,
vier typematen (30 / 17 / 15 / 13), sectiekoppen buiten de kaart, ingesprongen
scheidingslijnen, Apple systeemkleuren voor status. **De sidebar blijft donker**,
dat is een bewuste keuze en geen omissie.

**De agentlaag heet in het product Operator.** Hermes is de motor eronder.

**De pijplijn is een script, niet een agent.** Ophalen, normaliseren en valideren
is deterministisch werk. Alleen het interpreteren en voorstellen doen is agentwerk.

## Schrijfregels

Geen kastlijntjes of gedachtestreepjes als leesteken, niet in code-commentaar en
niet in klantteksten. Gebruik een komma, dubbele punt, punt of haakjes.
Koppeltekens binnen samenstellingen zoals e-mailagent blijven gewoon staan.

Nederlands in alles wat de klant ziet. Vaste afkortingen als ROAS, CPA, CTR en
CPC blijven Engels. Nederlandse getalnotatie: € 8.740 en 12,4%.

## Open punten, op volgorde

1. **`src/index.html` en `src/render.js` bouwen.** Leest `data/latest.json`,
   rekent alle verhoudingen uit, rendert naar `dist/`. Dit is het product.
2. **`demo.json` gelijktrekken met het ontwerp.** Nu staat er Eventix, andere
   ticketprijzen en een andere editie in dan in Paper. Paper is inhoudelijk
   leidend, de contractvorm blijft leidend.
3. **Contract tegenspraak oplossen.** `validate.py` eist `ctr` bij creatives
   terwijl de docstring zegt dat CTR berekend wordt. Lever `clicks` en
   `impressions` per creative en haal `ctr` uit het contract.
4. **Paper artboards 02 tot en met 07 afmaken.** Die hebben de nieuwe kleuren via
   de tokens maar nog de oude structuur, de oude kanalen en de oude editie.
5. **Bronnen koppelen via Composio**, ticketprovider eerst. Zonder tickets is er
   geen dashboard.
6. **Hosting.** Statisch, altijd bereikbaar, met een toegangspoort op e-mailadres.
   Niet vanaf de Mac serveren, dan is het dashboard offline zodra de laptop dicht is.

## Wat je niet alleen beslist

Vraag het aan Kylian, hij is de opdrachtgever richting de klant.

- De vorm van het contract veranderen
- Iets naar de klant sturen of publiceren
- Advertentiebudget verschuiven of campagnes aanpassen
- Hosting kiezen of een domein koppelen
- Prijzen, capaciteit of doelen aanpassen

## Werk je in Paper?

Alleen als de Paper MCP in `~/.hermes/config.yaml` staat, zie
`hermes/install/paper-mcp.yaml`. Zonder die server kun je het ontwerp niet zien
of aanpassen, en dan blijf je met je handen van de designbesluiten af: bouw dan
in code en meld wat er in Paper moet veranderen.
