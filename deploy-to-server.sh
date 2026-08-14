#!/bin/bash
# Mac → 腾讯云 直推静态站。
# 服务器那边有 cron 每 5 分钟从 GitHub 拉一次做兜底,但国内拉 GitHub 会挂,
# 所以真正上线以这条 SSH 直推为准(改完立刻生效,不用等 5 分钟也不看 GitHub 脸色)。
set -euo pipefail
# 守门员:内链/锚点/robots/sitemap 有错就拒绝上线(146 处死锚点的教训)
python3 ~/wenshucha-site/gen_llms.py >/dev/null || echo '⚠️ llms 生成失败,继续'
python3 ~/wenshucha-site/linkcheck.py ~/wenshucha-site || { echo "✗ linkcheck 未过,中止部署"; exit 1; }

# nginx rewrite 也版本化:宝塔若覆盖规则,部署时自动恢复；语法失败则回滚旧配置。
scp ~/wenshucha-site/ops/nginx/html_wenshucha.com.conf \
  root@114.132.74.235:/tmp/html_wenshucha.com.conf.codex
ssh root@114.132.74.235 '
  target=/www/server/panel/vhost/rewrite/html_wenshucha.com.conf
  incoming=/tmp/html_wenshucha.com.conf.codex
  backup=/www/server/panel/vhost/rewrite/html_wenshucha.com.conf.bak_before_codex_deploy
  if ! cmp -s "$incoming" "$target"; then
    cp "$target" "$backup"
    cp "$incoming" "$target"
    if /www/server/nginx/sbin/nginx -t -c /www/server/nginx/conf/nginx.conf; then
      /etc/init.d/nginx reload
    else
      cp "$backup" "$target"
      /www/server/nginx/sbin/nginx -t -c /www/server/nginx/conf/nginx.conf
      exit 1
    fi
  fi
  rm -f "$incoming"
'
rsync -az --exclude='.git' --exclude='.github' --exclude='.gitignore' --exclude='.vercel' \
  --exclude='ops' --exclude='*.py' --exclude='*.sh' --exclude='README*' --exclude='.DS_Store' \
  ~/wenshucha-site/ root@114.132.74.235:/www/wwwroot/wenshucha.com/
ssh root@114.132.74.235 'chown -R www:www /www/wwwroot/wenshucha.com 2>/dev/null; git -C /opt/wenshucha-site-repo rev-parse HEAD > /opt/.wenshucha-site-deployed-rev 2>/dev/null; true'
# 線上守門員:寶塔重寫規則若被覆蓋,會讓 /index.html 再次成為第二個首頁。
index_code="$(curl -sS --retry 3 --retry-all-errors --retry-delay 2 -o /dev/null -w '%{http_code}' --max-time 15 https://www.wenshucha.com/index.html)"
index_location="$(curl -sSI --retry 3 --retry-all-errors --retry-delay 2 --max-time 15 https://www.wenshucha.com/index.html | awk 'BEGIN{IGNORECASE=1} /^location:/{gsub(/\r/,""); print $2; exit}')"
if [ "$index_code" != "301" ] || [ "$index_location" != "https://www.wenshucha.com/" ]; then
  echo "✗ 線上 canonical 失效:/index.html 應 301 到首頁,實際 HTTP $index_code → ${index_location:-無 Location}"
  exit 1
fi
home_icp="$(curl -sS --retry 3 --retry-all-errors --retry-delay 2 --max-time 15 https://www.wenshucha.com/ | grep -o '粤ICP备2025437990号-2' | head -1 || true)"
if [ "$home_icp" != "粤ICP备2025437990号-2" ]; then
  echo "✗ 線上首頁缺少完整備案號,中止報綠"
  exit 1
fi
for hidden_path in deploy-to-server.sh gen_llms.py linkcheck.py _wscdl/probe.py files/执行.xlsx; do
  hidden_code="$(curl -sS --retry 3 --retry-all-errors --retry-delay 2 -o /dev/null -w '%{http_code}' --max-time 15 "https://www.wenshucha.com/$hidden_path")"
  if [ "$hidden_code" = "200" ]; then
    echo "✗ 非網站檔案仍可公開下載:/$hidden_path"
    exit 1
  fi
done
echo "✓ 已直推上线"
