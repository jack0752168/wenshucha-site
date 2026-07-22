#!/bin/bash
# Mac → 腾讯云 直推静态站。
# 服务器那边有 cron 每 5 分钟从 GitHub 拉一次做兜底,但国内拉 GitHub 会挂,
# 所以真正上线以这条 SSH 直推为准(改完立刻生效,不用等 5 分钟也不看 GitHub 脸色)。
set -euo pipefail
# 守门员:内链/锚点/robots/sitemap 有错就拒绝上线(146 处死锚点的教训)
python3 ~/wenshucha-site/linkcheck.py ~/wenshucha-site || { echo "✗ linkcheck 未过,中止部署"; exit 1; }
rsync -az --exclude='.git' --exclude='.github' --exclude='.gitignore' --exclude='.vercel' \
  ~/wenshucha-site/ root@114.132.74.235:/www/wwwroot/wenshucha.com/
ssh root@114.132.74.235 'chown -R www:www /www/wwwroot/wenshucha.com 2>/dev/null; git -C /opt/wenshucha-site-repo rev-parse HEAD > /opt/.wenshucha-site-deployed-rev 2>/dev/null; true'
echo "✓ 已直推上线"
