#!/bin/sh
# Builds the sandbox images (when any is missing, e.g. a newly added language),
# starts the stack and loads the sample questions. Runs on every Codespace
# start; later starts are quick.
set -e
cd "$(dirname "$0")/.."
for image in $(sed -n 's/^image: "\(.*\)"/\1/p' languages/*/config.yaml); do
  docker image inspect "$image" >/dev/null 2>&1 || { sh languages/build.sh; break; }
done
docker compose up -d --build
until docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')" 2>/dev/null; do
  sleep 2
done
docker compose exec -T api sh -c 'python -m api.seed examples/*/*.json'
echo
echo "Code Playground is running: open the Ports tab and click the globe next to port 8000."
