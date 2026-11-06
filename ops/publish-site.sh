#!/bin/bash
# Called inside the same /tmp/sync-wsc.lock used by cloud cron.
set -euo pipefail
SOURCE=$1
EXPECTED=$2
MANIFEST=$3
BUNDLE=$4
REPO=${WSC_SYNC_REPO:-/opt/wenshucha-site-repo}
WEB=${WSC_SYNC_WEB:-/www/wwwroot/wenshucha.com}
STAMP=${WSC_SYNC_STAMP:-/opt/.wenshucha-site-deployed-rev}
SYNC_SCRIPT=${WSC_SYNC_SCRIPT:-/root/sync-wenshucha-site.sh}
REWRITE=${WSC_SYNC_REWRITE:-/www/server/panel/vhost/rewrite/html_wenshucha.com.conf}
[[ "$EXPECTED" =~ ^[0-9a-f]{40}$ ]] || { echo 'UNKNOWN: invalid revision'; exit 2; }
git -C "$REPO" diff --quiet && git -C "$REPO" diff --cached --quiet || { echo 'UNKNOWN: tracked cloud changes preserved'; exit 2; }
if [ "$(git -C "$REPO" rev-parse HEAD)" != "$EXPECTED" ]; then
  [ -f "$BUNDLE" ] || { echo 'UNKNOWN: source changed and no usable bundle'; exit 2; }
  bash "$SOURCE/ops/install-site-source.sh" "$BUNDLE" "$EXPECTED" "$REPO"
fi
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" != "$EXPECTED" ]; then
  git -C "$REPO" merge-base --is-ancestor "$(cat "$STAMP")" "$EXPECTED" || { echo 'UNKNOWN: stale deployment rejected'; exit 2; }
fi
for required in linkcheck.py ops/research_catalog.py ops/research-intro.tmpl ops/sync-wenshucha-site.sh ops/publish-site.sh ops/install-site-source.sh; do
  [ -f "$REPO/$required" ] && cmp -s "$SOURCE/$required" "$REPO/$required" || { echo "UNKNOWN: guard package differs: $required"; exit 2; }
done
python3 "$REPO/linkcheck.py" "$REPO"
bash -n "$SOURCE/ops/sync-wenshucha-site.sh"
cp "$SYNC_SCRIPT" "$SYNC_SCRIPT.bak_before_committed_deploy"
install -m 700 "$SOURCE/ops/sync-wenshucha-site.sh" "$SYNC_SCRIPT"
if ! cmp -s "$SOURCE/ops/nginx/html_wenshucha.com.conf" "$REWRITE"; then
  backup="$REWRITE.bak_before_committed_deploy"
  cp "$REWRITE" "$backup"
  cp "$SOURCE/ops/nginx/html_wenshucha.com.conf" "$REWRITE"
  if /www/server/nginx/sbin/nginx -t -c /www/server/nginx/conf/nginx.conf; then
    /etc/init.d/nginx reload
  else
    cp "$backup" "$REWRITE"
    exit 1
  fi
fi
rsync -az --exclude='.git' --exclude='.github' --exclude='.gitignore' --exclude='.vercel' \
  --exclude='ops' --exclude='*.py' --exclude='*.sh' --exclude='README*' --exclude='.DS_Store' \
  "$SOURCE/" "$WEB/"
chown -R www:www "$WEB" 2>/dev/null || true
curl_base=(--silent --show-error --fail --resolve www.wenshucha.com:443:127.0.0.1 --max-time 15)
root_code=$(curl "${curl_base[@]}" -o /dev/null -w '%{http_code}' https://www.wenshucha.com/)
index_code=$(curl "${curl_base[@]}" -o /dev/null -w '%{http_code}' https://www.wenshucha.com/index.html)
location=$(curl "${curl_base[@]}" -I https://www.wenshucha.com/index.html | awk 'BEGIN{IGNORECASE=1} /^location:/{gsub(/\r/,""); print $2; exit}')
[ "$root_code" = 200 ] && [ "$index_code" = 301 ] && [ "$location" = 'https://www.wenshucha.com/' ] || { echo 'FAIL: canonical verification'; exit 1; }
curl "${curl_base[@]}" https://www.wenshucha.com/ | grep -q '粤ICP备2025437990号-2'
for hidden in deploy-to-server.sh gen_llms.py linkcheck.py ops/research_catalog.py; do
  code=$(curl --silent --show-error --resolve www.wenshucha.com:443:127.0.0.1 --max-time 15 -o /dev/null -w '%{http_code}' "https://www.wenshucha.com/$hidden")
  [ "$code" != 200 ] || { echo "FAIL: operational file exposed $hidden"; exit 1; }
done
(cd "$WEB" && sha256sum --quiet -c "$MANIFEST")
[ "$(git -C "$REPO" rev-parse HEAD)" = "$EXPECTED" ] || { echo 'UNKNOWN: source changed during publish'; exit 2; }
stamp_tmp="$STAMP.committed.tmp"
printf '%s\n' "$EXPECTED" > "$stamp_tmp"
mv "$stamp_tmp" "$STAMP"
echo "verified-and-stamped $EXPECTED"
