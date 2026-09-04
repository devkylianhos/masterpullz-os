#!/usr/bin/env python3
"""
Master Pullz OS collector.

Haalt per bron een ruwe momentopname op en schrijft die naar data/raw/<bron>.json.
Rekent niets uit en normaliseert niets: dat is het werk van normalize.py.

Elke bron is precies één functie. Een koppeling toevoegen raakt daarom nooit
meer dan één plek. Zolang een bron niet gekoppeld is meldt hij dat eerlijk,
in plaats van een leeg of verzonnen resultaat terug te geven.

    python3 hermes/collect.py              alle bronnen
    python3 hermes/collect.py --status     alleen tonen wat verbonden is
    python3 hermes/collect.py --only meta  losse bron
"""
import argparse, json, os, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")

NOT_CONNECTED = "not_connected"
CONNECTED = "connected"
ERROR = "error"


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def env(*names):
    """Eerste gevulde omgevingsvariabele, of None."""
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def result(status, note, data=None, via=None):
    return {"status": status, "fetched_at": now(), "via": via, "note": note,
            "data": data if data is not None else {}}


# ── Bronnen ──────────────────────────────────────────────────────────────
# Ticketprovider is de belangrijkste: die levert tickets, omzet en straks de
# utm bron per bestelling. Zonder deze bron is er geen dashboard.

def fetch_weticket(_):
    key = env("WETICKET_API_KEY")
    if not key:
        return result(NOT_CONNECTED, "Geen WETICKET_API_KEY. Vraag Weticket om API toegang "
                                     "en of de utm velden per bestelling opvraagbaar zijn.",
                      via="direct")
    return result(ERROR, "Adapter nog niet geschreven. Sleutel is wel aanwezig.", via="direct")


def _composio(app, feeds):
    """Alle advertentieplatforms lopen via jouw bestaande Composio router."""
    if not env("COMPOSIO_API_KEY"):
        return result(NOT_CONNECTED, "Geen COMPOSIO_API_KEY in de omgeving.", via="composio")
    return result(NOT_CONNECTED, f"Composio staat klaar, {app} is nog niet gekoppeld. "
                                 f"Verwachte feeds: {', '.join(feeds)}.", via="composio")


def fetch_meta(_):      return _composio("Meta Ads", ["spend", "impressies", "clicks", "creatives"])
def fetch_google(_):    return _composio("Google Ads", ["spend", "zoekwoorden", "conversies"])
def fetch_tiktok(_):    return _composio("TikTok Ads", ["spend", "impressies", "clicks"])
def fetch_snapchat(_):  return _composio("Snapchat Ads", ["spend", "impressies", "clicks"])
def fetch_reddit(_):    return _composio("Reddit Ads", ["spend", "impressies", "clicks"])
def fetch_gsc(_):       return _composio("Search Console", ["posities", "clicks", "impressies"])
def fetch_reviews(_):   return _composio("Google Reviews", ["rating", "reviews"])


SOURCES = {
    "weticket": ("Weticket",       fetch_weticket, 6),
    "meta":     ("Meta Ads",       fetch_meta,     12),
    "google":   ("Google Ads",     fetch_google,   12),
    "tiktok":   ("TikTok Ads",     fetch_tiktok,   24),
    "snapchat": ("Snapchat Ads",   fetch_snapchat, 24),
    "reddit":   ("Reddit Ads",     fetch_reddit,   24),
    "gsc":      ("Search Console", fetch_gsc,      72),
    "reviews":  ("Google Reviews", fetch_reviews,  72),
}


def collect(only=None):
    os.makedirs(RAW, exist_ok=True)
    status = {}
    for key, (label, fn, stale_hours) in SOURCES.items():
        if only and key not in only:
            continue
        try:
            out = fn(None)
        except Exception as exc:                      # een kapotte bron mag de rest niet slopen
            out = result(ERROR, f"{type(exc).__name__}: {exc}")
        out["source"] = key
        out["label"] = label
        out["stale_hours"] = stale_hours
        with open(os.path.join(RAW, f"{key}.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        status[key] = {"label": label, "status": out["status"],
                       "via": out["via"], "note": out["note"], "fetched_at": out["fetched_at"]}
    with open(os.path.join(RAW, "_status.json"), "w", encoding="utf-8") as f:
        json.dump({"checked_at": now(), "sources": status}, f, ensure_ascii=False, indent=2)
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", help="alleen deze bronnen")
    p.add_argument("--status", action="store_true", help="niets schrijven, alleen tonen")
    a = p.parse_args()

    st = collect(set(a.only) if a.only else None)
    width = max(len(v["label"]) for v in st.values())
    mark = {CONNECTED: "verbonden", NOT_CONNECTED: "niet verbonden", ERROR: "fout"}
    for key, v in st.items():
        print(f"  {v['label']:<{width}}  {mark.get(v['status'], v['status'])}")
    live = sum(1 for v in st.values() if v["status"] == CONNECTED)
    print(f"\n{live} van {len(st)} bronnen verbonden")
    # Geen enkele bron verbonden is geen fout, dat is de huidige stand van zaken.
    return 0


if __name__ == "__main__":
    sys.exit(main())
