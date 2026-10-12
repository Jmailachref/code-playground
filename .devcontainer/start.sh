#!/bin/sh
# Builds the sandbox images (first start only), starts the stack and loads the
# sample questions. Runs on every Codespace start; later starts are quick.
set -e
cd "$(dirname "$0")/.."
docker image inspect codeplay/python:3.13 >/dev/null 2>&1 || sh languages/build.sh
docker compose up -d --build
until docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')" 2>/dev/null; do
  sleep 2
done
docker compose exec -T api sh -c 'python -m api.seed examples/*.json'
echo
echo "Code Playground is running: open the Ports tab and click the globe next to port 8000."
