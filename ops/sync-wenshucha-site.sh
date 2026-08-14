#!/bin/bash
# 腾讯云每 5 分钟自愈同步：GitHub → webroot。
# 这份文件是 /root/sync-wenshucha-site.sh 的唯一版本源，部署脚本会自动安装。
set -u

REPO=/opt/wenshucha-site-repo
WEB=/www/wwwroot/wenshucha.com
STAMP=/opt/.wenshucha-site-deployed-rev
URL=https://github.com/jack0752168/wenshucha-site.git
REWRITE_SRC="$REPO/ops/nginx/html_wenshucha.com.conf"
REWRITE_TARGET=/www/server/panel/vhost/rewrite/html_wenshucha.com.conf
QUARANTINE=/www/backup/wenshucha-webroot-quarantine-auto

log() { echo "[$(date '+%F %T')] $*"; }

if [ ! -d "$REPO/.git" ]; then
  timeout 120 git clone -q --depth 1 "$URL" "$REPO" || { log "clone 超时/失败"; exit 1; }
fi
cd "$REPO" || exit 1
timeout 90 git fetch -q --depth 1 origin main 2>/dev/null || exit 0
timeout 30 git reset -q --hard origin/main || exit 1
REV=$(git rev-parse HEAD)

# 仓库自己有错就拒绝覆盖线上；不能把“同步成功”当成“站点健康”。
if [ -f "$REPO/linkcheck.py" ]; then
  python3 "$REPO/linkcheck.py" "$REPO" >/tmp/wenshucha-linkcheck.log 2>&1 || {
    log "linkcheck 未通过，拒绝部署"
    tail -30 /tmp/wenshucha-linkcheck.log
    exit 1
  }
fi

# 宝塔重存配置可能覆盖 canonical/保护规则。即使 Git revision 没变也要自愈。
if [ -f "$REWRITE_SRC" ] && ! cmp -s "$REWRITE_SRC" "$REWRITE_TARGET"; then
  rewrite_backup="${REWRITE_TARGET}.bak_autoheal"
  cp "$REWRITE_TARGET" "$rewrite_backup" || exit 1
  cp "$REWRITE_SRC" "$REWRITE_TARGET" || exit 1
  if /www/server/nginx/sbin/nginx -t -c /www/server/nginx/conf/nginx.conf >/tmp/wenshucha-nginx-test.log 2>&1; then
    /etc/init.d/nginx reload >/dev/null 2>&1
    log "nginx rewrite 已自愈"
  else
    cp "$rewrite_backup" "$REWRITE_TARGET"
    cat /tmp/wenshucha-nginx-test.log
    log "nginx rewrite 新版本无效，已回滚"
    exit 1
  fi
fi

# 没有新 revision 时仍完成上面的 nginx 自愈，然后才退出。
[ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$REV" ] && exit 0

# 只同步公开站点资产。运维代码、仓库说明和本地杂项永远不能进 webroot。
rsync -a \
  --exclude='.git' --exclude='.github' --exclude='.gitignore' --exclude='.vercel' \
  --exclude='ops' --exclude='*.py' --exclude='*.sh' --exclude='README*' --exclude='.DS_Store' \
  "$REPO"/ "$WEB"/ || exit 1

# 双保险：若历史同步或人工操作再次把敏感路径放回来，移入可恢复隔离区而非删除。
mkdir -p "$QUARANTINE"
chmod 700 "$QUARANTINE"
for rel in deploy-to-server.sh gen_llms.py linkcheck.py ops; do
  path="$WEB/$rel"
  if [ -e "$path" ]; then
    dest="$QUARANTINE/$(basename "$rel").$(date +%s)"
    mv -- "$path" "$dest"
    log "已隔离非网站路径 /$rel"
  fi
done

chown -R www:www "$WEB" 2>/dev/null

# 从 origin 本机验证最终 HTTPS 行为，绕开公网/VPN 瞬断。
curl_base=(--silent --show-error --insecure --resolve www.wenshucha.com:443:127.0.0.1 --max-time 15)
root_code=$(curl "${curl_base[@]}" -o /dev/null -w '%{http_code}' https://www.wenshucha.com/)
index_code=$(curl "${curl_base[@]}" -o /dev/null -w '%{http_code}' https://www.wenshucha.com/index.html)
index_location=$(curl "${curl_base[@]}" -I https://www.wenshucha.com/index.html | awk 'BEGIN{IGNORECASE=1} /^location:/{gsub(/\r/,""); print $2; exit}')
if [ "$root_code" != "200" ] || [ "$index_code" != "301" ] || [ "$index_location" != "https://www.wenshucha.com/" ]; then
  log "canonical 回归失败：/=$root_code；/index.html=$index_code → ${index_location:-无 Location}"
  exit 1
fi

home_icp=$(curl "${curl_base[@]}" https://www.wenshucha.com/ | grep -o '粤ICP备2025437990号-2' | head -1 || true)
if [ "$home_icp" != "粤ICP备2025437990号-2" ]; then
  log "首页完整备案号缺失"
  exit 1
fi

for hidden_path in deploy-to-server.sh gen_llms.py linkcheck.py ops/nginx/html_wenshucha.com.conf; do
  hidden_code=$(curl "${curl_base[@]}" -o /dev/null -w '%{http_code}' "https://www.wenshucha.com/$hidden_path")
  if [ "$hidden_code" = "200" ]; then
    log "非网站文件仍可公开下载：/$hidden_path"
    exit 1
  fi
done

echo "$REV" > "$STAMP"
log "synced ${REV:0:7}"
