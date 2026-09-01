#!/usr/bin/env bash
set -euo pipefail

target_dir="${1:-external/starmie_data}"
mkdir -p "$target_dir"

archive="$target_dir/viznet_tables.tar.gz"
curl -L --fail --continue-at - \
  -o "$archive" \
  https://sato-data.s3.us-east-2.amazonaws.com/viznet_tables.tar.gz
tar -xzf "$archive" -C "$target_dir"

echo "VizNet tables downloaded under: $target_dir"
