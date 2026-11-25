#!/bin/bash
set -euo pipefail
if [ "${RENEWED_LINEAGE:-}" = /etc/letsencrypt/live/www.datahouseful.com ]; then
    /www/server/nginx/sbin/nginx -t -c /www/server/nginx/conf/nginx.conf
    /etc/init.d/nginx reload
fi
