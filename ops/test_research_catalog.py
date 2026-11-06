#!/usr/bin/env python3
"""Bounded catalog drift controls on temporary copies, never the live page."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent))
import research_catalog as catalog


def main():
    site = Path(__file__).resolve().parents[1]
    data = catalog.catalog()
    baseline = catalog.render(site, data)
    results = []
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        (tmp / 'ops').mkdir()
        (tmp / 'case-research').mkdir()
        (tmp / 'ops/research-intro.tmpl').write_text((site / 'ops/research-intro.tmpl').read_text())
        page = tmp / 'case-research/index.html'
        page.write_text(baseline)
        assert not catalog.check_site(tmp, data)
        results.append({'case': 'valid_catalog', 'pass': True})
        mutants = {
            'visible_price': ('¥19.9', '¥29.9'),
            'visible_research_count': ('<td>10次</td>', '<td>11次</td>'),
            'visible_days': ('<td>90天</td>', '<td>91天</td>'),
            'visible_seats': ('<td>3人共用</td>', '<td>4人共用</td>'),
            'description': ('个人月包19.9元/10次', '个人月包19.9元/11次'),
            'faq': ('注册赠3次完整研究', '注册赠4次完整研究'),
            'offer_schema': ('"price": 19.9', '"price": 29.9'),
        }
        for name, (old, new) in mutants.items():
            assert old in baseline, name
            page.write_text(baseline.replace(old, new, 1))
            assert catalog.check_site(tmp, data), name
            results.append({'case': name, 'drift_rejected': True})
        fixture = tmp / 'catalog.json'
        fixture.write_text(json.dumps({'version': data['version'], 'currency': 'CNY',
            'plans': {k: v for k, v in data['plans'].items() if k != 'team'},
            'team': data['plans']['team']}))
        page.write_text(baseline.replace('¥19.9', '¥29.9', 1))
        rejected = subprocess.run([sys.executable, str(site / 'ops/research_catalog.py'), '--site', str(tmp), '--catalog-file', str(fixture)], capture_output=True, text=True)
        assert rejected.returncode == 1 and json.loads(rejected.stdout)['status'] == 'fail'
        results.append({'case': 'wrong_price_cli', 'exit_code': 1, 'drift_rejected': True})
        page.write_text(baseline)
        before = hashlib.sha256(page.read_bytes()).hexdigest()
        failed = subprocess.run([sys.executable, str(site / 'ops/research_catalog.py'), '--site', str(tmp), '--url', 'http://127.0.0.1:1/catalog', '--sync'], capture_output=True, text=True)
        assert failed.returncode == 2 and json.loads(failed.stdout)['status'] == 'unknown'
        assert hashlib.sha256(page.read_bytes()).hexdigest() == before
        results.append({'case': 'unavailable_catalog', 'exit_code': 2, 'page_unchanged': True})
        assert not catalog.check_site(tmp, data)
        results.append({'case': 'restored_valid_page', 'pass': True})
    print(json.dumps({'status': 'pass', 'cases': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
