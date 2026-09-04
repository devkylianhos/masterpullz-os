#!/bin/sh
# Zet de Operator in je Hermes omgeving. Draai dit zelf, ik doe het niet voor je,
# want het verandert de configuratie van een agent die live staat.
#
#   sh hermes/install/install.sh            laat zien wat er zou gebeuren
#   sh hermes/install/install.sh --apply    voert het uit
set -eu
cd "$(dirname "$0")/../.."
APPLY=""
[ "${1:-}" = "--apply" ] && APPLY=1

SKILLDIR="$HOME/.hermes/skills/masterpullz-os"
JOBS="$HOME/.hermes/cron/jobs.json"

echo "Skill      -> $SKILLDIR/SKILL.md"
echo "Cronjobs   -> $JOBS  (mpos-pipeline, mpos-operator)"
echo

if [ -z "$APPLY" ]; then
  echo "Proefdraai. Niets gewijzigd. Voeg --apply toe om het echt te doen."
  exit 0
fi

mkdir -p "$SKILLDIR"
cp hermes/install/SKILL.md "$SKILLDIR/SKILL.md"
echo "skill geplaatst"

cp "$JOBS" "$JOBS.backup-$(date +%Y%m%d-%H%M%S)"
echo "back-up van jobs.json gemaakt"

python3 hermes/install/merge_jobs.py "$JOBS" hermes/install/cron.jobs.json
