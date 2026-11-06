#!/bin/bash
# One committed source; the complete cloud publication shares cron's flock.
set -euo pipefail
SITE_ROOT="$(cd "$(dirname "$0")" && pwd)"
SITE_REV="$(git -C "$SITE_ROOT" rev-parse HEAD)"
SERVER=root@114.132.74.235
git -C "$SITE_ROOT" diff --quiet && git -C "$SITE_ROOT" diff --cached --quiet || { echo 'UNKNOWN: commit tracked site changes before deployment'; exit 2; }
[ -z "$(git -C "$SITE_ROOT" ls-files --others --exclude-standard)" ] || { echo 'UNKNOWN: use a clean committed checkout'; exit 2; }
python3 "$SITE_ROOT/gen_llms.py" >/dev/null
git -C "$SITE_ROOT" diff --quiet || { echo 'UNKNOWN: generated content is not committed'; exit 2; }
python3 "$SITE_ROOT/linkcheck.py" "$SITE_ROOT" || { rc=$?; echo 'Gate rejected deployment'; exit "$rc"; }
deploy_tmp="$(mktemp -d)"
trap 'rm -rf "$deploy_tmp"' EXIT
git -C "$SITE_ROOT" archive --format=tar -o "$deploy_tmp/source.tar" "$SITE_REV"
cloud_rev="$(ssh "$SERVER" 'git -C /opt/wenshucha-site-repo rev-parse HEAD')"
bundle=none
if [ "$cloud_rev" != "$SITE_REV" ]; then
  git -C "$SITE_ROOT" cat-file -e "$cloud_rev^{commit}" 2>/dev/null && git -C "$SITE_ROOT" merge-base --is-ancestor "$cloud_rev" "$SITE_REV" || { echo 'UNKNOWN: cloud source is newer/divergent; rollback not authorized'; exit 2; }
  git -C "$SITE_ROOT" bundle create "$deploy_tmp/site.bundle" HEAD "^$cloud_rev"
  bundle=site.bundle
fi
python3 - "$SITE_ROOT" "$SITE_REV" "$deploy_tmp/public.sha256" <<'PY'
import hashlib, pathlib, subprocess, sys
root, rev, output = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
names = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-r', '--name-only', '-z', rev]).decode().split('\0')
lines = []
for name in filter(None, names):
    p = pathlib.PurePosixPath(name)
    if any(part in ('.git', '.github', '.gitignore', '.vercel', 'ops') for part in p.parts) or p.suffix in ('.py', '.sh') or p.name.startswith('README') or p.name == '.DS_Store':
        continue
    if '\n' in name or '\\' in name:
        raise SystemExit('UNKNOWN: unsupported manifest filename')
    content = subprocess.check_output(['git', '-C', str(root), 'show', rev+':'+name])
    lines.append(hashlib.sha256(content).hexdigest()+'  '+name+'\n')
output.write_text(''.join(lines))
PY
remote_stage="/tmp/wsc-site-deploy-$SITE_REV"
ssh "$SERVER" "umask 077; mkdir -p '$remote_stage/source'"
scp "$deploy_tmp/source.tar" "$deploy_tmp/public.sha256" "$SERVER:$remote_stage/"
if [ "$bundle" != none ]; then scp "$deploy_tmp/site.bundle" "$SERVER:$remote_stage/"; fi
ssh "$SERVER" "tar -xf '$remote_stage/source.tar' -C '$remote_stage/source'"
# One lock covers source install, current guard, public writes, checks and stamp.
ssh "$SERVER" "flock -w 45 /tmp/sync-wsc.lock bash '$remote_stage/source/ops/publish-site.sh' '$remote_stage/source' '$SITE_REV' '$remote_stage/public.sha256' '$remote_stage/$bundle'"
echo "Published committed source $SITE_REV"
