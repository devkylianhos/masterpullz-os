# Operator

De agentlaag van Master Pullz OS. Draait op Hermes.

## Waarom het zo gesplitst is

De pijplijn is deterministisch: ophalen, normaliseren, valideren. Daar komt geen
taalmodel aan te pas. Die draait daarom als **script job** met `no_agent: true`,
elk uur, en kost niets.

Het interpreteren is dat wel: tempo lezen, kanalen vergelijken, vermoeidheid
zien, voorstellen formuleren. Die draait **één keer per dag als agent**, na de
pijplijn, en leest een payload die al gevalideerd is.

Daarmee kan de agent de cijfers niet meer verzinnen: hij krijgt ze aangeleverd
en de validator heeft ze al nagerekend.

## Bestanden

| Bestand | Doet |
|---|---|
| `collect.py` | Ruwe momentopname per bron naar `data/raw/`. Eén functie per bron. |
| `normalize.py` | Ruw naar één payload in `data/latest.json`. Verwijdert berekende velden. |
| `run.sh` | De hele keten. Exit 1 betekent: niet publiceren. |
| `install/SKILL.md` | De skill met de grenzen erin. |
| `install/cron.jobs.json` | De twee cronjobs. |
| `install/install.sh` | Zet skill en jobs in `~/.hermes`. |

## Nu draaien

```sh
sh hermes/run.sh          # demo modus, werkt vandaag al
python3 hermes/collect.py # alleen kijken welke bronnen verbonden zijn
```

## Installeren in Hermes

```sh
sh hermes/install/install.sh          # proefdraai
sh hermes/install/install.sh --apply  # echt doen, maakt eerst een back-up
```

## Een bron koppelen

1. Koppel de app in Composio.
2. Schrijf de adapter in `collect.py`. Dat is één functie die ruwe data teruggeeft.
3. Schrijf de mapper in `normalize.py`. Alleen tellingen en bedragen, geen verhoudingen.
4. `sh hermes/run.sh live`. Faalt de validatie, dan is de mapping nog niet goed.

De ticketprovider gaat eerst. Zonder tickets is er geen dashboard.

## Open punt in het contract

`validate.py` eist `ctr` bij creatives, terwijl de docstring van het contract
zegt dat CTR door de UI berekend wordt. `normalize.py` laat het veld daarom
staan en meldt de tegenspraak bij elke run. Oplossen door per creative `clicks`
en `impressions` te leveren en `ctr` uit het contract te halen.
