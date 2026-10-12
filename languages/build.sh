#!/bin/sh
# Builds the runbox helper and every language image.
set -e
cd "$(dirname "$0")"
docker build -t codeplay/runbox:latest runbox
for dir in */; do
  lang=${dir%/}
  [ "$lang" = runbox ] && continue
  image=$(sed -n 's/^image: "\(.*\)"/\1/p' "$lang/config.yaml")
  echo "==> $lang ($image)"
  docker build -t "$image" "$lang"
done
