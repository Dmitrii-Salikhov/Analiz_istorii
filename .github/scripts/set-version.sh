#!/usr/bin/env bash
# Set version.txt and desktop/package.json from GITHUB_REF_NAME or $1 (e.g. v1.3.3).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

RAW="${GITHUB_REF_NAME:-${1:-}}"
if [[ -z "$RAW" ]]; then
  echo "Usage: set-version.sh v1.3.3  (or set GITHUB_REF_NAME)" >&2
  exit 1
fi
VERSION="${RAW#v}"
echo "$VERSION" > version.txt
export VERSION
node <<'NODE'
const fs = require('fs');
const version = process.env.VERSION;
if (!version) throw new Error('VERSION env missing');
const p = 'desktop/package.json';
const j = JSON.parse(fs.readFileSync(p, 'utf8'));
j.version = version;
fs.writeFileSync(p, JSON.stringify(j, null, 2) + '\n');
console.log('version.txt + desktop/package.json ->', version);
NODE
