"""Locked, atomic CRM updates. No email delivery or outreach actions."""
import copy
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unicodedata


def norm(value):
    return ''.join(unicodedata.normalize('NFKC', str(value or '')).split()).casefold()


def phone(value):
    result = ''.join(c for c in str(value or '') if c.isdigit())
    return result[2:] if result.startswith('86') and len(result) == 13 else result


def atomic(file, update):
    file = Path(file)
    with open(str(file) + '.write-lock', 'a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = json.loads(file.read_text())
        result = update(copy.deepcopy(original))
        if result is None:
            return original
        with tempfile.NamedTemporaryFile('w', dir=file.parent, delete=False, encoding='utf8') as stream:
            temp = stream.name
            os.chmod(temp, 0o600)
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, file)
        return result


def save_merged(file, baseline, desired):
    """Only merge changed companies; a conflicting same-company write must retry."""
    def merge(current):
        old = {x['id']: x for x in baseline['companies']}
        new = {x['id']: x for x in desired['companies']}
        live = {x['id']: x for x in current['companies']}
        for key in old.keys() | new.keys():
            if old.get(key) == new.get(key):
                continue
            if live.get(key) not in (old.get(key), new.get(key)):
                raise RuntimeError('CRM concurrent company update; retry next run')
            if key not in new:
                live.pop(key, None)
            else:
                live[key] = new[key]
        current['companies'] = list(live.values())
        current.setdefault('meta', {}).update(desired.get('meta', {}))
        if 'stage_names' in desired:
            current['stage_names'] = desired['stage_names']
        return current
    return atomic(file, merge)


def upsert_trial(file, lead):
    if lead.get('source') != 'mcp-selfserve' or lead.get('email_verified') is not True:
        raise ValueError('Not a verified MCP trial')
    person = lead['profile']
    email = person['email'].strip().casefold()
    for field in ('name', 'company', 'phone'):
        if not person.get(field):
            raise ValueError('Missing required lead field')
    company_id = None
    def update(data):
        nonlocal company_id
        matches = []
        for item in data['companies']:
            same_name = norm(item['name']) == norm(person['company'])
            same_contact = any(str(c.get('email') or '').casefold() == email or (c.get('phone') and phone(c['phone']) == phone(person['phone'])) for c in item.get('contacts', []))
            if same_name or same_contact:
                matches.append(item)
        if len(matches) > 1:
            exact = [x for x in matches if norm(x['name']) == norm(person['company'])]
            if len(exact) != 1:
                raise RuntimeError('Ambiguous CRM match; pending manual review')
            matches = exact
        if matches:
            company = matches[0]
        else:
            company = {'id': 'mcp-inbound-' + hashlib.sha256(norm(person['company']).encode()).hexdigest()[:16],
                       'name': person['company'], 'domain': '', 'segment': 'mcp-inbound', 'stage': 4,
                       'hook': '', 'contacts': [], 'touches': [], 'followup_count': 0,
                       'last_touch': lead['issued_day'], 'next_followup_due': None,
                       'reply': None, 'notes': 'MCP自助免费试用；邮箱已验证，姓名/公司/电话为客户自填，电话未验证。',
                       'source': 'mcp-selfserve', 'automation_hold': True}
            data['companies'].append(company)
        company_id = company['id']
        trials = company.setdefault('mcp_trials', [])
        if any(x['id'] == lead['id'] for x in trials):
            return None
        existing = next((c for c in company['contacts'] if str(c.get('email') or '').casefold() == email or (c.get('phone') and phone(c['phone']) == phone(person['phone']))), None)
        if not existing:
            company['contacts'].append({'name': person['name'], 'email': email, 'phone': person['phone'],
                                       'role': '', 'kind': 'inbound-mcp', 'status': 'manual-only',
                                       'bounced': False, 'email_verified': True, 'phone_verified': False,
                                       'source': 'mcp-selfserve'})
        else:
            for k, v in [('phone', person['phone']), ('name', person['name'])]:
                if not existing.get(k):
                    existing[k] = v
        trials.append({k: lead[k] for k in ('id', 'plan', 'expires', 'issued_day', 'key_mask', 'source')})
        company['last_touch'] = max(company.get('last_touch') or '', lead['issued_day'])
        data.setdefault('meta', {})['updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return data
    atomic(file, update)
    return company_id
