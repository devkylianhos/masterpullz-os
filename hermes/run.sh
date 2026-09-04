#!/bin/sh
# Master Pullz OS pijplijn. Deterministisch, geen agent nodig.
#   sh hermes/run.sh          demo modus
#   sh hermes/run.sh live     uit de echte bronnen
#
# Exit 0 = payload is vervangen.  Exit 1 = payload NIET vervangen, oude blijft
# staan. Dat is met opzet: een dashboard met oude cijfers en een eerlijke
# tijdstempel is beter dan een dashboard met cijfers die niet kloppen.
set -eu
cd "$(dirname "$0")/.."
MODE="${1:-demo}"
LOCK="data/.pipeline.lock"

if [ -d "$LOCK" ]; then
  echo "Vorige run draait nog, deze sla ik over."
  exit 0
fi
mkdir "$LOCK"
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

# Sleutels komen uit de Hermes omgeving.
if [ -f "$HOME/.hermes/.env" ]; then
  set -a; . "$HOME/.hermes/.env"; set +a
fi

echo "1/3  bronnen ophalen"
python3 hermes/collect.py

echo "2/3  normaliseren"
python3 hermes/normalize.py --mode "$MODE"

echo "3/3  valideren"
if python3 contract/validate.py data/latest.json; then
  echo "Payload goedgekeurd."
else
  echo "Validatie mislukt. data/latest.json is NIET gepubliceerd." >&2
  exit 1
fi
