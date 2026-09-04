#!/usr/bin/env python3
"""
Voegt de Master Pullz jobs toe aan de Hermes cronlijst.

Neemt een bestaande job als vorm-sjabloon, zodat elk veld dat Hermes verwacht
aanwezig is. Bestaande jobs met hetzelfde id worden overgeschreven, de rest
blijft ongemoeid.
"""
import json, sys, time
from datetime import datetime, timezone

RUNSTATE = {"state": "idle", "paused_at": None, "paused_reason": None,
            "next_run_at": None, "last_run_at": None, "last_status": None,
            "last_error": None, "last_delivery_error": None, "failure_streak": 0,
            "fire_claim": None, "preflight_alerted": False, "last_dispatch": None,
            "monitor_state": None}


def main(jobs_path, new_path):
    with open(jobs_path, encoding="utf-8") as f:
        doc = json.load(f)
    existing = doc.get("jobs", [])
    if not existing:
        print("jobs.json heeft geen bestaande job om de vorm van te lenen.", file=sys.stderr)
        return 1
    template = {k: v for k, v in existing[0].items()}

    with open(new_path, encoding="utf-8") as f:
        incoming = json.load(f)["jobs"]

    now = datetime.now(timezone.utc).isoformat()
    by_id = {j["id"]: j for j in existing}
    for job in incoming:
        merged = dict(template)          # alle velden die Hermes kent
        merged.update(RUNSTATE)          # runstatus leeg
        merged.update(job)               # onze waarden erover
        merged.setdefault("created_at", now)
        merged["schedule_display"] = job["schedule"].get("display", "")
        was = "bijgewerkt" if job["id"] in by_id else "toegevoegd"
        by_id[job["id"]] = merged
        print(f"  {job['id']:<16} {was}   {merged['schedule_display']}")

    doc["jobs"] = list(by_id.values())
    doc["updated_at"] = now
    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"\n{len(doc['jobs'])} jobs in totaal. Herstart Hermes of wacht op de volgende tick.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
