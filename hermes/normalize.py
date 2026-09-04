#!/usr/bin/env python3
"""
Master Pullz OS normalizer.

Zet de ruwe momentopnames uit data/raw om naar één payload in data/latest.json,
volgens contract v1.0. Dit is de enige plek waar bronveldnamen voorkomen.

Harde regel, overgenomen uit het contract: de payload bevat alleen METINGEN.
Geen ROAS, geen CPA, geen percentages, geen aandelen. Die worden door de UI
berekend. Daardoor kan er nooit een verhouding in staan die niet klopt met
zijn eigen invoer.

    python3 hermes/normalize.py --mode demo   fixture met verse tijdstempel
    python3 hermes/normalize.py --mode live   uit de echte bronnen
"""
import argparse, json, os, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DEMO = os.path.join(ROOT, "data", "demo.json")
OUT = os.path.join(ROOT, "data", "latest.json")

# Velden die nooit in de payload horen. Als een adapter er ooit eentje meestuurt
# gooit normalize hem er hier uit, zodat de regel niet stilletjes kan verwateren.
VERBODEN = {"roas", "cpa", "cpc", "conversie", "conversion_rate",
            "share", "aandeel", "sell_through", "percentage", "pct"}

# Velden die volgens de contract-docstring berekend horen te worden, maar die
# validate.py op dit moment nog als invoer EIST. Die halen we er niet uit, want
# dan faalt de validatie. Ze worden wel elke run gemeld, zodat de tegenspraak
# zichtbaar blijft tot hij is opgelost.
GEDOOGD = {"ctr": "validate.py eist ctr bij creatives, terwijl het contract zegt "
                  "dat CTR berekend wordt. Los op door clicks en impressions per "
                  "creative te leveren en ctr uit het contract te halen."}


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def strip_ratios(node, path="payload", found=None, tolerated=None):
    """Verwijdert berekende velden. Gedoogde velden blijven staan, maar worden gemeld."""
    if found is None:
        found, tolerated = [], set()
    if isinstance(node, dict):
        for k, v in list(node.items()):
            low = k.lower()
            if low in VERBODEN:
                found.append(f"{path}.{k}")
                node.pop(k)
            else:
                if low in GEDOOGD:
                    tolerated.add(low)
                strip_ratios(v, f"{path}.{k}", found, tolerated)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            strip_ratios(v, f"{path}[{i}]", found, tolerated)
    return found, tolerated


def read_status():
    p = os.path.join(RAW, "_status.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("sources", {})


def build_demo():
    """De fixture, met een verse tijdstempel zodat de ouderdomscheck niet afgaat."""
    if not os.path.exists(DEMO):
        print("data/demo.json ontbreekt", file=sys.stderr)
        return None
    with open(DEMO, encoding="utf-8") as f:
        payload = json.load(f)
    payload["generated_at"] = now()
    payload["environment"] = "demo"
    return payload


def build_live():
    """Uit data/raw. Faalt bewust hard zolang de belangrijkste bron ontbreekt."""
    status = read_status()
    connected = [k for k, v in status.items() if v.get("status") == "connected"]
    if "weticket" not in connected:
        print("De ticketprovider is niet verbonden. Zonder tickets is er geen payload.",
              file=sys.stderr)
        print("Draai zolang met --mode demo.", file=sys.stderr)
        return None
    # Vanaf hier komt per bron een mapper. Elke bron levert alleen tellingen
    # en bedragen aan; verhoudingen blijven weg.
    print("Live mapping is nog niet geschreven. Voeg per bron een mapper toe.",
          file=sys.stderr)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["demo", "live"], default="demo")
    a = p.parse_args()

    payload = build_demo() if a.mode == "demo" else build_live()
    if payload is None:
        return 1

    weg, gedoogd = strip_ratios(payload)
    if weg:
        print(f"LET OP {len(weg)} berekende velden verwijderd uit de payload:")
        for w in weg[:8]:
            print(f"  {w}")
    for veld in sorted(gedoogd):
        print(f"CONTRACT  veld '{veld}' blijft staan. {GEDOOGD[veld]}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    status = read_status()
    live = sum(1 for v in status.values() if v.get("status") == "connected")
    print(f"data/latest.json geschreven · modus {a.mode} · {live} van {len(status) or 8} bronnen verbonden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
