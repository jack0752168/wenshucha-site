#!/bin/bash
# Run under the existing cloud sync flock. Source only: never writes webroot/stamp.
set -euo pipefail
bundle=$1
expected=$2
repo=$3
[[ "$expected" =~ ^[0-9a-f]{40}$ ]] || { echo 'UNKNOWN: invalid source revision'; exit 2; }
[ -d "$repo/.git" ] || { echo 'UNKNOWN: cloud source checkout missing'; exit 2; }
git -C "$repo" diff --quiet && git -C "$repo" diff --cached --quiet || {
  echo 'UNKNOWN: cloud checkout has tracked changes; preserved'; exit 2;
}
git -C "$repo" bundle verify "$bundle" >/dev/null
current=$(git -C "$repo" rev-parse HEAD)
git -C "$repo" fetch -q "$bundle" HEAD
[ "$(git -C "$repo" rev-parse FETCH_HEAD)" = "$expected" ] || {
  echo 'UNKNOWN: bundle revision differs from deployment'; exit 2;
}
git -C "$repo" merge-base --is-ancestor "$current" "$expected" || {
  echo 'UNKNOWN: newer/divergent cloud source preserved; rollback not authorized'; exit 2;
}
for required in linkcheck.py ops/research_catalog.py ops/research-intro.tmpl ops/sync-wenshucha-site.sh ops/publish-site.sh ops/install-site-source.sh; do
  git -C "$repo" cat-file -e "$expected:$required" || {
    echo "UNKNOWN: source lacks required guard: $required"; exit 2;
  }
done
git -C "$repo" reset -q --hard "$expected"
git -C "$repo" update-ref refs/remotes/origin/main "$expected"
echo "source-installed $expected"
