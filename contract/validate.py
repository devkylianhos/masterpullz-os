#!/usr/bin/env python3
"""
Master Pullz OS payload validator.

Checks a dashboard payload against contract v1.0 before it is allowed to reach
the UI. Zero third-party dependencies so it runs inside a Hermes cron script.

    python3 contract/validate.py data/latest.json
    python3 contract/validate.py data/latest.json --json

Exit codes:  0 = clean (warnings allowed)   1 = errors found   2 = unreadable

Design rule this enforces: the payload carries MEASUREMENTS ONLY. Every ratio
(ROAS, CPA, CTR, conversion, share, sell-through) is computed by the dashboard.
An agent therefore cannot publish a ratio that disagrees with its own inputs.
"""
import json, sys, argparse
from datetime import datetime, timezone

CONTRACT = "1.0"
STALE_HOURS = {"eventix": 6, "meta": 12, "google": 12, "ga4": 24, "tiktok": 24,
               "mailchimp": 48, "crm": 48, "gsc": 72, "gbp": 72, "compint": 72}
DEFAULT_STALE_HOURS = 48

E, W = [], []
def err(path, msg): E.append((path, msg))
def warn(path, msg): W.append((path, msg))

def need(obj, path, *keys):
    """Require keys to be present; returns False if any are missing."""
    ok = True
    for k in keys:
        if not isinstance(obj, dict) or k not in obj or obj[k] is None:
            err(f"{path}.{k}", "ontbreekt")
            ok = False
    return ok

def num(v, path, allow_zero=True, allow_none=False):
    if v is None and allow_none:
        return None
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        err(path, f"moet een getal zijn, kreeg {type(v).__name__}")
        return None
    if v < 0:
        err(path, f"mag niet negatief zijn ({v})")
        return None
    if v == 0 and not allow_zero:
        err(path, "mag niet nul zijn")
        return None
    return v

def eq(actual, expected, path, what, tol=0):
    """Reconciliation check. tol is an absolute tolerance."""
    if actual is None or expected is None:
        return
    if abs(actual - expected) > tol:
        gap = actual - expected
        err(path, f"{what}: {actual:,.2f} telt niet op naar {expected:,.2f} "
                  f"(verschil {gap:+,.2f})".replace(",", "."))

def parse_ts(s, path):
    if not isinstance(s, str):
        err(path, "moet een ISO 8601 tijdstempel zijn")
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        err(path, f"geen geldige ISO 8601 tijdstempel: {s!r}")
        return None


def validate(p):
    # ---------- envelope ----------
    if p.get("contract_version") != CONTRACT:
        err("contract_version",
            f"verwacht {CONTRACT!r}, kreeg {p.get('contract_version')!r}")
    gen = parse_ts(p.get("generated_at"), "generated_at")
    if gen:
        now = datetime.now(gen.tzinfo or timezone.utc)
        if gen > now:
            warn("generated_at", "ligt in de toekomst")
        elif (now - gen).total_seconds() > 3 * 3600:
            warn("generated_at",
                 f"payload is {(now-gen).total_seconds()/3600:.1f} uur oud")
    if p.get("environment") not in ("demo", "live"):
        err("environment", "moet 'demo' of 'live' zijn")

    if not need(p, "", "config", "edition", "sources", "data"):
        return
    cfg, ed, d = p["config"], p["edition"], p["data"]

    # ---------- config ----------
    need(cfg, "config", "product_name", "client_name", "locale", "currency",
         "channels", "ticket_types")
    chan_ids = {c["id"] for c in cfg.get("channels", []) if "id" in c}
    tt = {t["id"]: t for t in cfg.get("ticket_types", []) if "id" in t}
    if not chan_ids:
        err("config.channels", "leeg")
    if not tt:
        err("config.ticket_types", "leeg")
    paid_ids = {c["id"] for c in cfg.get("channels", []) if c.get("paid")}

    need(ed, "edition", "id", "label", "event_date", "goals")
    goals = ed.get("goals", {})
    need(goals, "edition.goals", "tickets", "revenue", "ad_budget")

    # ---------- sources ----------
    src_ids = set()
    for i, s in enumerate(p.get("sources", [])):
        path = f"sources[{i}]"
        if not need(s, path, "id", "label", "status"):
            continue
        src_ids.add(s["id"])
        if s["status"] not in ("connected", "syncing", "attention", "disconnected"):
            err(f"{path}.status", f"onbekende status {s['status']!r}")
        if s["status"] in ("connected", "syncing"):
            ts = parse_ts(s.get("last_sync"), f"{path}.last_sync")
            if ts and gen:
                age = (gen - ts).total_seconds() / 3600
                limit = STALE_HOURS.get(s["id"], DEFAULT_STALE_HOURS)
                if age > limit:
                    warn(f"{path}.last_sync",
                         f"{s['label']} is {age:.0f} uur oud (grens {limit} uur); "
                         "zet status op 'attention' of ververs de bron")
        elif s["status"] == "disconnected" and s.get("last_sync"):
            err(f"{path}.last_sync",
                "een niet verbonden bron mag geen synctijd claimen")

    # ---------- headline ----------
    t = d.get("tickets", {})
    need(t, "data.tickets", "sold", "revenue", "orders", "unique_customers")
    sold = num(t.get("sold"), "data.tickets.sold", allow_zero=False)
    rev = num(t.get("revenue"), "data.tickets.revenue")
    orders = num(t.get("orders"), "data.tickets.orders", allow_zero=False)
    uniq = num(t.get("unique_customers"), "data.tickets.unique_customers")
    if sold and orders and orders > sold:
        err("data.tickets.orders", f"meer orders ({orders}) dan tickets ({sold})")
    if uniq and orders and uniq > orders:
        err("data.tickets.unique_customers",
            f"meer unieke klanten ({uniq}) dan orders ({orders})")
    spend = num(d.get("spend", {}).get("total"), "data.spend.total")

    # ---------- pace ----------
    pace = d.get("pace", {})
    if need(pace, "data.pace", "days", "current", "target"):
        days = pace["days"]
        n = len(days)
        if any(days[i] <= days[i + 1] for i in range(n - 1)):
            err("data.pace.days", "moet strikt aflopend zijn (60 naar 0)")
        if days and days[-1] != 0:
            err("data.pace.days", "laatste waarde moet 0 zijn (de eventdag)")
        for k in ("current", "previous", "target", "forecast", "low", "high"):
            if k not in pace:
                continue
            if len(pace[k]) != n:
                err(f"data.pace.{k}",
                    f"lengte {len(pace[k])} wijkt af van days ({n})")
                continue
            vals = [(i, v) for i, v in enumerate(pace[k]) if v is not None]
            for i, v in vals:
                num(v, f"data.pace.{k}[{i}]")
            for a, b in zip(vals, vals[1:]):
                if b[1] < a[1]:
                    err(f"data.pace.{k}[{b[0]}]",
                        f"cumulatieve reeks daalt ({a[1]} naar {b[1]})")
        cur = [v for v in pace.get("current", []) if v is not None]
        if cur and sold:
            eq(cur[-1], sold, "data.pace.current",
               "laatste gemeten punt versus data.tickets.sold")
        for k in ("forecast", "low", "high"):
            s_ = [v for v in pace.get(k, []) if v is not None]
            if s_ and cur and s_[0] != cur[-1]:
                err(f"data.pace.{k}",
                    f"moet starten op de huidige stand ({cur[-1]}), niet {s_[0]}")

    fc = d.get("forecast", {})
    if fc:
        lo, mid, hi = fc.get("conservative"), fc.get("expected"), fc.get("optimistic")
        if None not in (lo, mid, hi) and not (lo <= mid <= hi):
            err("data.forecast",
                f"scenario's staan niet op volgorde: {lo} / {mid} / {hi}")
        if sold and lo is not None and lo < sold:
            err("data.forecast.conservative",
                f"eindstand ({lo}) kan niet lager zijn dan nu verkocht ({sold})")
        if fc.get("break_even") is None and not fc.get("break_even_blocked_by"):
            warn("data.forecast.break_even_blocked_by",
                 "geen break-even en geen reden; noem de ontbrekende bron")
        blocker = fc.get("break_even_blocked_by")
        if blocker and blocker not in src_ids:
            err("data.forecast.break_even_blocked_by",
                f"verwijst naar onbekende bron {blocker!r}")

    # ---------- channels ----------
    chans = d.get("channels", [])
    seen = set()
    c_tk = c_rev = c_vis = c_co = p_spend = 0
    for i, c in enumerate(chans):
        path = f"data.channels[{i}]"
        if "id" not in c:
            err(path + ".id", "ontbreekt"); continue
        if c["id"] in seen:
            err(path + ".id", f"dubbele channel id {c['id']!r}")
        seen.add(c["id"])
        if c["id"] not in chan_ids and c["id"] != "unattributed":
            err(path + ".id",
                f"{c['id']!r} staat niet in config.channels")
        for k in ("spend", "impressions", "clicks", "visitors", "checkouts",
                  "tickets", "revenue"):
            num(c.get(k), f"{path}.{k}")
        c_tk += c.get("tickets") or 0
        c_rev += c.get("revenue") or 0
        c_vis += c.get("visitors") or 0
        c_co += c.get("checkouts") or 0
        if c["id"] in paid_ids:
            p_spend += c.get("spend") or 0
        elif c.get("spend"):
            err(path + ".spend",
                f"{c['id']!r} is geen betaald kanaal maar heeft spend")
        if (c.get("clicks") or 0) > (c.get("impressions") or 0) and c["id"] in paid_ids:
            err(path + ".clicks", "meer klikken dan impressies")
        if (c.get("tickets") or 0) > (c.get("checkouts") or 0):
            err(path + ".tickets",
                f"meer tickets ({c.get('tickets')}) dan checkouts ({c.get('checkouts')})")
    eq(c_tk, sold, "data.channels[].tickets",
       "som van kanaaltickets versus data.tickets.sold")
    eq(c_rev, rev, "data.channels[].revenue",
       "som van kanaalomzet versus data.tickets.revenue")
    eq(p_spend, spend, "data.channels[].spend",
       "som van betaalde spend versus data.spend.total")
    if c_tk != sold:
        err("data.channels", "voeg het verschil toe als kanaal 'unattributed' "
                             "in plaats van de cijfers te laten afwijken")

    # ---------- campaigns roll up into their channel ----------
    roll = {}
    for i, c in enumerate(d.get("campaigns", [])):
        path = f"data.campaigns[{i}]"
        if not need(c, path, "id", "name", "channel", "spend", "tickets",
                    "revenue", "status"):
            continue
        if c["channel"] not in chan_ids:
            err(path + ".channel", f"onbekend kanaal {c['channel']!r}")
        if c["status"] not in ("scaling", "stable", "watch", "pause"):
            err(path + ".status", f"onbekende status {c['status']!r}")
        r = roll.setdefault(c["channel"], {"spend": 0, "tickets": 0, "revenue": 0})
        for k in ("spend", "tickets", "revenue"):
            v = num(c.get(k), f"{path}.{k}")
            r[k] += v or 0
    by_id = {c.get("id"): c for c in chans}
    for cid, r in roll.items():
        ch = by_id.get(cid)
        if not ch:
            err(f"data.campaigns[channel={cid}]",
                "campagnes voor een kanaal dat niet in data.channels staat")
            continue
        for k in ("spend", "tickets", "revenue"):
            eq(r[k], ch.get(k), f"data.campaigns[channel={cid}].{k}",
               f"som van campagne-{k} versus kanaaltotaal")

    # ---------- creatives may be a subset, but never exceed their channel ----------
    cre_spend = {}
    for i, c in enumerate(d.get("creatives", [])):
        path = f"data.creatives[{i}]"
        if not need(c, path, "id", "name", "channel", "spend", "tickets",
                    "revenue", "ctr", "frequency", "recommendation"):
            continue
        if c["channel"] not in chan_ids:
            err(path + ".channel", f"onbekend kanaal {c['channel']!r}")
        if c["recommendation"] not in ("scale", "keep", "watch", "fatigue", "new_hook"):
            err(path + ".recommendation", f"onbekende waarde {c['recommendation']!r}")
        if not 0 <= (c.get("ctr") or 0) <= 100:
            err(path + ".ctr", "CTR moet tussen 0 en 100 liggen")
        cre_spend[c["channel"]] = cre_spend.get(c["channel"], 0) + (c.get("spend") or 0)
    for cid, s in cre_spend.items():
        ch = by_id.get(cid)
        if ch and s > (ch.get("spend") or 0) + 0.01:
            err(f"data.creatives[channel={cid}].spend",
                f"creatives ({s:,.0f}) besteden meer dan het kanaal ({ch.get('spend'):,.0f})")

    # ---------- funnel ----------
    fun = d.get("funnel", [])
    for a, b in zip(fun, fun[1:]):
        if (b.get("value") or 0) > (a.get("value") or 0):
            err(f"data.funnel[{b.get('id')}]",
                f"stap is groter dan de vorige ({b.get('value')} > {a.get('value')})")
    fmap = {s.get("id"): s.get("value") for s in fun}
    if "purchase" in fmap:
        eq(fmap["purchase"], sold, "data.funnel.purchase",
           "laatste funnelstap versus data.tickets.sold")
    if "visitors" in fmap and chans:
        eq(fmap["visitors"], c_vis, "data.funnel.visitors",
           "funnelbezoekers versus som van kanaalbezoekers")
    if "checkout" in fmap and chans:
        eq(fmap["checkout"], c_co, "data.funnel.checkout",
           "funnelcheckouts versus som van kanaalcheckouts")

    # ---------- weekly ----------
    wk = d.get("weekly", [])
    if wk:
        eq(sum(w.get("spend") or 0 for w in wk), spend, "data.weekly[].spend",
           "som van weekspend versus data.spend.total")
        paid_rev = sum(c.get("revenue") or 0 for c in chans
                       if c.get("id") in paid_ids)
        eq(sum(w.get("revenue") or 0 for w in wk), paid_rev,
           "data.weekly[].revenue",
           "som van weekomzet versus toegerekende omzet uit betaalde kanalen")

    # ---------- ticket mix is a partition of the tickets ----------
    mix = d.get("ticket_mix", [])
    m_sold = m_rev = 0
    for i, m in enumerate(mix):
        path = f"data.ticket_mix[{i}]"
        if not need(m, path, "id", "sold", "revenue"):
            continue
        if m["id"] not in tt:
            err(path + ".id", f"{m['id']!r} staat niet in config.ticket_types")
            continue
        price, cap = tt[m["id"]].get("price"), tt[m["id"]].get("capacity")
        m_sold += m["sold"]; m_rev += m["revenue"]
        if price is not None:
            eq(m["revenue"], m["sold"] * price, path + ".revenue",
               f"omzet versus verkocht x prijs ({price})")
        if cap is not None and m["sold"] > cap:
            err(path + ".sold",
                f"{m['sold']} verkocht terwijl de capaciteit {cap} is")
    if mix:
        eq(m_sold, sold, "data.ticket_mix[].sold", "som versus data.tickets.sold")
        eq(m_rev, rev, "data.ticket_mix[].revenue", "som versus data.tickets.revenue")

    # ---------- geo is a partition too ----------
    geo = d.get("geo", [])
    if geo:
        eq(sum(g.get("tickets") or 0 for g in geo), sold, "data.geo[].tickets",
           "som versus data.tickets.sold")
        eq(sum(g.get("revenue") or 0 for g in geo), rev, "data.geo[].revenue",
           "som versus data.tickets.revenue")
        eq(sum(g.get("spend") or 0 for g in geo), spend, "data.geo[].spend",
           "toegerekende spend per regio versus data.spend.total", tol=25)

    # ---------- web ----------
    web = d.get("web", {})
    if need(web, "data.web", "visitors", "sessions", "devices", "landing_pages"):
        if web["sessions"] < web["visitors"]:
            err("data.web.sessions", "minder sessies dan unieke bezoekers")
        eq(web["visitors"], c_vis, "data.web.visitors",
           "versus som van kanaalbezoekers")
        for key, field in (("devices", "sessions"), ("landing_pages", "sessions")):
            eq(sum(x.get(field) or 0 for x in web[key]), web["sessions"],
               f"data.web.{key}[].{field}", "som versus data.web.sessions")
            eq(sum(x.get("tickets") or 0 for x in web[key]), sold,
               f"data.web.{key}[].tickets", "som versus data.tickets.sold")

    # ---------- customers ----------
    cu = d.get("customers", {})
    if need(cu, "data.customers", "new", "returning"):
        eq(cu["new"] + cu["returning"], uniq, "data.customers",
           "nieuw plus terugkerend versus data.tickets.unique_customers")
        parts = (cu.get("returning_from_previous"), cu.get("returning_from_older"))
        if None not in parts:
            eq(sum(parts), cu["returning"], "data.customers.returning_from_*",
               "som versus data.customers.returning")
        if cu.get("multi_edition") is not None and cu["multi_edition"] > cu["returning"]:
            err("data.customers.multi_edition",
                "meer meerdere-edities-bezoekers dan terugkerende klanten")
        if cu.get("database_size") is not None and uniq and cu["database_size"] < uniq:
            err("data.customers.database_size",
                "klantenbestand kleiner dan het aantal huidige klanten")

    # ---------- attendance ----------
    at = d.get("attendance", {})
    if at:
        if need(at, "data.attendance", "edition_id", "sold", "scanned"):
            if at["scanned"] > at["sold"]:
                err("data.attendance.scanned", "meer gescand dan verkocht")
            if at.get("unique_visitors") and at["unique_visitors"] > at["scanned"]:
                err("data.attendance.unique_visitors", "meer bezoekers dan scans")
            parts = (at.get("first_time"), at.get("returning"))
            if None not in parts and at.get("unique_visitors"):
                eq(sum(parts), at["unique_visitors"], "data.attendance.first_time+returning",
                   "som versus data.attendance.unique_visitors")
        if at.get("edition_id") == ed.get("id"):
            err("data.attendance.edition_id",
                "scandata van de huidige editie kan pas na het event bestaan")

    # ---------- retargeting ----------
    for i, s in enumerate(d.get("retargeting", [])):
        path = f"data.retargeting[{i}]"
        if not need(path and s, path, "id", "label", "size", "cta", "channel"):
            continue
        if s.get("pool") is not None and s["size"] > s["pool"]:
            err(path + ".size", f"segment ({s['size']}) groter dan de bron ({s['pool']})")
        if not 0 <= (s.get("prior_conversion") or 0) <= 100:
            err(path + ".prior_conversion", "moet tussen 0 en 100 liggen")

    # ---------- email ----------
    em = [e for e in d.get("email", []) if not e.get("edition_id")
          or e.get("edition_id") == ed.get("id")]
    if em:
        ch_email = by_id.get("email")
        if ch_email:
            eq(sum(e.get("tickets") or 0 for e in em), ch_email.get("tickets"),
               "data.email[].tickets", "som versus kanaal 'email'")
            eq(sum(e.get("revenue") or 0 for e in em), ch_email.get("revenue"),
               "data.email[].revenue", "som versus kanaal 'email'")
    for i, e in enumerate(d.get("email", [])):
        for k in ("open_rate", "click_rate"):
            if not 0 <= (e.get(k) or 0) <= 100:
                err(f"data.email[{i}].{k}", "moet tussen 0 en 100 liggen")
        if (e.get("click_rate") or 0) > (e.get("open_rate") or 0):
            warn(f"data.email[{i}].click_rate", "hoger dan de open rate")

    # ---------- seo ----------
    seo = d.get("seo", [])
    if seo:
        ch_org = by_id.get("organic")
        if ch_org:
            eq(sum(s.get("clicks") or 0 for s in seo), ch_org.get("clicks"),
               "data.seo[].clicks", "som versus kanaal 'organic'")
        for i, s in enumerate(seo):
            if s.get("impressions") and (s.get("clicks") or 0) > s["impressions"]:
                err(f"data.seo[{i}].clicks", "meer klikken dan impressies")

    # ---------- reviews ----------
    rv = d.get("reviews", {})
    if rv:
        total = sum(x.get("count") or 0 for x in rv.get("distribution", []))
        if total and rv.get("responded", 0) > total:
            err("data.reviews.responded", "meer antwoorden dan reviews")
        for x in rv.get("distribution", []):
            if x.get("stars") not in (1, 2, 3, 4, 5):
                err("data.reviews.distribution", f"ongeldig aantal sterren {x.get('stars')}")

    # ---------- alerts ----------
    pages = {"overzicht", "tickets", "marketing", "bezoekers", "retargeting",
             "creatives", "email", "seo", "concurrentie", "reviews", "alerts",
             "bronnen", "instellingen"}
    for i, a in enumerate(d.get("alerts", [])):
        path = f"data.alerts[{i}]"
        if not need(a, path, "id", "severity", "title", "body", "cta", "target"):
            continue
        if a["severity"] not in ("good", "warn", "bad", "info"):
            err(path + ".severity", f"onbekende severity {a['severity']!r}")
        if a["target"] not in pages:
            err(path + ".target", f"{a['target']!r} is geen bestaand scherm")

    # ---------- budget sanity ----------
    if spend is not None and goals.get("ad_budget") and spend > goals["ad_budget"]:
        warn("data.spend.total",
             f"budget overschreden: {spend:,.0f} van {goals['ad_budget']:,.0f}")


def main():
    ap = argparse.ArgumentParser(description="Valideer een Master Pullz OS payload")
    ap.add_argument("payload")
    ap.add_argument("--json", action="store_true", help="machineleesbare uitvoer")
    ap.add_argument("--strict", action="store_true", help="waarschuwingen tellen als fouten")
    a = ap.parse_args()
    try:
        p = json.load(open(a.payload, encoding="utf-8"))
    except Exception as ex:
        print(f"KAN PAYLOAD NIET LEZEN: {ex}", file=sys.stderr)
        sys.exit(2)

    validate(p)
    failed = bool(E) or (a.strict and bool(W))

    if a.json:
        print(json.dumps({"ok": not failed,
                          "errors": [{"path": p_, "message": m} for p_, m in E],
                          "warnings": [{"path": p_, "message": m} for p_, m in W]},
                         ensure_ascii=False, indent=2))
    else:
        for p_, m in E:
            print(f"FOUT   {p_}: {m}")
        for p_, m in W:
            print(f"LET OP {p_}: {m}")
        if not E and not W:
            print(f"OK  {a.payload} voldoet aan contract {CONTRACT}")
        else:
            print(f"\n{len(E)} fouten, {len(W)} waarschuwingen")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
