#!/usr/bin/env python3
"""Sync/check the public research introduction against the live public catalog.

Default check is network-backed and fails closed on unavailable/invalid evidence.
--catalog-file is for offline regression fixtures; deployment never supplies it.
No local research source or /Users path is needed on the server.
"""
import argparse
import html
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

URL = 'https://tob.wenshucha.com/research/api/plans'
IDS = ('trial', 'pass', 'monthly', 'annual', 'team')


class Unknown(Exception):
    pass


def normalize(raw):
    try:
        plans = dict(raw['plans'])
        plans['team'] = raw['team']
        assert raw['currency'] == 'CNY' and isinstance(raw['version'], str)
        assert set(plans) == set(IDS)
        for v in plans.values():
            assert isinstance(v['label'], str) and v['label']
            assert type(v['price']) in (int, float) and 0 <= v['price'] < 1000000
            for key in ('limit', 'days', 'seats'):
                assert type(v[key]) is int and 0 < v[key] < 1000000
        return {'version': raw['version'], 'plans': {k: {f: plans[k][f] for f in ('label', 'price', 'limit', 'days', 'seats')} for k in IDS}}
    except (KeyError, TypeError, AssertionError):
        raise Unknown('invalid public catalog; no page was changed')


def catalog(file=None, url=URL):
    try:
        if file:
            raw = json.loads(Path(file).read_text())
        else:
            with urllib.request.urlopen(url, timeout=15) as res:
                raw = json.load(res)
        return normalize(raw)
    except (OSError, ValueError) as e:
        raise Unknown('catalog unreadable: ' + type(e).__name__)


def render(site, data):
    plans = data['plans']
    t, p, a = (plans[x] for x in ('trial', 'pass', 'annual'))
    monthly = plans['monthly']
    money = lambda n: format(n, 'g')
    faq = [
        ('货款纠纷可以用文书查类案研究吗？', '首期支持买卖合同与货款结算。先确认检索方向，再比较所选历史文书的事实差异与正文引用，不承诺个案结论或胜率。'),
        ('不用申请 MCP Key，也能免费试用吗？', f'可以。新账号注册赠{t["limit"]}次完整研究、{t["days"]}天有效，不用先加微信或申请Key。无需登录可在应用点击“查看完整示例”，试用完成不隐藏关键结论。'),
        ('一次完整研究包含什么？', '最多选读8份实体裁判文书，提供事实对照、正文引用定位和可编辑Word，含3次限定于该批文书的续问。长文书可能采用选段分析，重要结论需律师复核。'),
        ('失败或取消会扣次数吗？', '未完成研究、无可用文书、取消待确认计划会退还占用的研究名额。这是名额回退，不是现金退款。'),
        ('和 MCP 套餐相同吗？', '不同。网页类案研究按完整研究计次；MCP按工具调用与正文额度计量，供开发者接入。两者方案和额度独立。'),
        ('如何付费，会自动续费吗？', '试用后选择方案，自行添加原客服微信，确认内测容量与服务安排，付款后人工开通。不自动扣款、不自动续费；续购保留有效旧次数，年包一次入账、可跨月使用。'),
    ]
    app = {'@type': 'SoftwareApplication', 'name': '文书查 · 类案研究', 'applicationCategory': 'BusinessApplication', 'operatingSystem': 'Web', 'url': 'https://www.wenshucha.com/case-research/', 'description': '买卖合同与货款结算：确认方向、比较事实、核对正文引用并导出Word，与MCP额度独立。', 'offers': [
        {'@type': 'Offer', 'name': v['label'], 'price': v['price'], 'priceCurrency': 'CNY', 'url': 'https://tob.wenshucha.com/research/#pricing', 'description': f'{v["limit"]}次完整研究，{v["days"]}天有效，{v["seats"]}席，无自动续费。'} for v in plans.values()]}
    schema = {'@context': 'https://schema.org', '@graph': [app, {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': answer}} for q, answer in faq]}]}
    values = {
        'DESCRIPTION': f'文书查类案研究聚焦买卖合同与货款结算：确认方向、比较最多8份文书、核对正文引用并导出Word。注册免费{t["limit"]}次/{t["days"]}天，个人月包{money(monthly["price"])}元/{monthly["limit"]}次/{monthly["days"]}天；与MCP额度独立。',
        'SCHEMA': json.dumps(schema, ensure_ascii=False),
        'TRIAL_LINE': f'新账号免费{t["limit"]}次，{t["days"]}天有效 · 不先加微信 · 不申请Key · 完成试用提供完整结果',
        'PLAN_GUIDANCE': f'个人月包是常用起点；低频可选{p["days"]}天体验包，全年按需可选年包。与 MCP 调用额度完全分开。',
        'ROWS': ''.join(f'<tr><th scope="row">{html.escape(v["label"])}</th><td>¥{money(v["price"])}</td><td>{v["limit"]}次</td><td>{v["days"]}天</td><td>{v["seats"]}人'+('共用' if k == 'team' else '')+'</td></tr>' for k, v in plans.items()),
        'ANNUAL_NOTE': f'报价目录版本：{html.escape(data["version"])}。年包{a["limit"]}次一次入账，{a["days"]}天内可跨月使用，不逐月发放；续购保留有效旧次数。',
        'FAQ': ''.join('<details><summary>'+html.escape(q)+'</summary><p>'+html.escape(answer)+'</p></details>' for q, answer in faq),
    }
    text = (site / 'ops/research-intro.tmpl').read_text()
    for key, value in values.items():
        token = '{{'+key+'}}'
        if text.count(token) != 1:
            raise Unknown('template token missing or duplicated: ' + key)
        text = text.replace(token, value)
    if '{{' in text:
        raise Unknown('unresolved template token')
    return text


def check_site(site, data=None):
    data = data or catalog()
    if (site / 'case-research/index.html').read_text() != render(site, data):
        return ['case-research: catalog/body/meta/FAQ/schema drift; run ops/research_catalog.py --sync, review and redeploy']
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--sync', action='store_true')
    ap.add_argument('--catalog-file')
    ap.add_argument('--url', default=URL)
    ap.add_argument('--local-module', type=Path, help='optional PLANS source cross-check; never required for cloud deployment')
    args = ap.parse_args()
    try:
        data = catalog(args.catalog_file, args.url)
        if args.local_module:
            code = 'const m=await import(process.argv[1]); console.log(JSON.stringify({version:m.CATALOG_VERSION,currency:"CNY",plans:Object.fromEntries(["trial",...m.PUBLIC_PLAN_IDS].map(k=>[k,m.PLANS[k]])),team:m.PLANS.team}));'
            raw = subprocess.check_output(['node', '--input-type=module', '-e', code, args.local_module.resolve().as_uri()], text=True)
            if normalize(json.loads(raw)) != data:
                print('FAIL: local PLANS and public catalog differ; no page changed')
                return 1
        if args.sync:
            target = args.site / 'case-research/index.html'
            generated = render(args.site, data)
            temp = target.with_suffix('.tmp')
            temp.write_text(generated)
            temp.replace(target)
        errors = check_site(args.site, data)
        print(json.dumps({'status': 'fail' if errors else 'pass', 'catalog_version': data['version'], 'errors': errors}, ensure_ascii=False))
        return int(bool(errors))
    except (Unknown, OSError, ValueError, subprocess.SubprocessError) as e:
        print(json.dumps({'status': 'unknown', 'error': str(e)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
