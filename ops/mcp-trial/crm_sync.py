"""Durable outbox consumer; writes only verified trial leads to existing CRM."""
import json
import os
from pathlib import Path
import sys
import urllib.request
from crm_store import upsert_trial

config = json.loads(Path(os.environ.get('WSC_TRIAL_CRM_CONFIG', str(Path.home()/'.config/wsc-mcp-trial/crm.json'))).read_text())


def api(path, body):
    request = urllib.request.Request(config['url'] + '/internal/crm/' + path,
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + config['token']}, method='POST')
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


try:
    for _ in range(50):
        lead = api('poll', {}).get('lead')
        if not lead:
            break
        company_id = upsert_trial(config.get('pipeline', str(Path.home()/'sinoverdict-crm/pipeline.json')), lead)
        api('ack', {'id': lead['id']})
        print(json.dumps({'event': 'crm_synced', 'trial_id': lead['id'], 'company_id': company_id}))
except Exception as error:
    print(json.dumps({'event': 'crm_pending', 'error_type': type(error).__name__}), file=sys.stderr)
    sys.exit(1)
