#!/usr/bin/env python3
"""Isolated shell entry-point guards; no production paths or remote writes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SITE = Path(__file__).resolve().parents[1]


def executable(path, text):
    path.write_text(text)
    path.chmod(0o700)


def run(command, **kwargs):
    return subprocess.run(command, text=True, capture_output=True, **kwargs)


def main():
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        bin = root / 'bin'
        bin.mkdir()
        trace = root / 'trace'
        executable(bin / 'git', '''#!/bin/bash
echo "git $*" >> "$QA_TRACE"
case "$1" in
fetch) exit "${QA_FETCH_RC:-0}";;
rev-parse) echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;;
merge-base) exit "${QA_ANCESTOR_RC:-0}";;
esac
''')
        executable(bin / 'timeout', '#!/bin/bash\nshift\nexec "$@"\n')
        for name in ('ssh', 'scp', 'rsync'):
            executable(bin / name, '#!/bin/bash\necho FORBIDDEN_'+name+' >> "$QA_TRACE"\nexit 99\n')
        os.symlink(sys.executable, bin / 'python3')
        repo, web, stamp = root / 'repo', root / 'web', root / 'stamp'
        (repo / '.git').mkdir(parents=True)
        (repo / 'ops').mkdir()
        web.mkdir()
        sentinel = web / 'index.html'
        env = {**os.environ, 'PATH': str(bin)+':'+os.environ['PATH'], 'QA_TRACE': str(trace),
               'WSC_SYNC_REPO': str(repo), 'WSC_SYNC_WEB': str(web), 'WSC_SYNC_STAMP': str(stamp),
               'WSC_SYNC_CHECK_LOG': str(root / 'check.log')}
        for name, fetch_rc, guard_rc, missing, ancestor_rc in [
                ('git_fetch_unavailable', 1, 0, False, 0),
                ('old_checkout_missing_guard', 0, 0, True, 0),
                ('catalog_unavailable', 0, 2, False, 0),
                ('catalog_drift', 0, 1, False, 0),
                ('cannot_prove_revision_ancestry', 0, 0, False, 1)]:
            trace.write_text('')
            sentinel.write_text('published-bytes')
            stamp.write_text(('b' if ancestor_rc else 'a')*40)
            before = stamp.read_bytes()
            (repo / 'linkcheck.py').write_text('print("UNKNOWN" if '+str(guard_rc)+' == 2 else "CHECK")\nraise SystemExit('+str(guard_rc)+')\n')
            for file in ('research_catalog.py', 'research-intro.tmpl'):
                p = repo / 'ops' / file
                if missing:
                    if p.exists(): p.unlink()
                else:
                    p.write_text('fixture')
            process = run(['bash', str(SITE / 'ops/sync-wenshucha-site.sh')], env={**env, 'QA_FETCH_RC': str(fetch_rc), 'QA_ANCESTOR_RC': str(ancestor_rc)})
            assert process.returncode != 0, (name, process.stdout, process.stderr)
            assert stamp.read_bytes() == before and sentinel.read_text() == 'published-bytes'
            assert 'FORBIDDEN' not in trace.read_text(), name
            results.append({'case': name, 'exit_code': process.returncode, 'webroot_and_stamp_unchanged': True})
        # Direct deployment must stop before its first SSH/SCP/rsync on a failed gate.
        direct = root / 'direct'
        direct.mkdir()
        shutil.copy2(SITE / 'deploy-to-server.sh', direct / 'deploy-to-server.sh')
        (direct / 'gen_llms.py').write_text('pass\n')
        for code in (1, 2):
            trace.write_text('')
            (direct / 'linkcheck.py').write_text('raise SystemExit('+str(code)+')\n')
            process = run(['bash', str(direct / 'deploy-to-server.sh')], env=env)
            assert process.returncode == code, (process.stdout, process.stderr)
            assert 'FORBIDDEN' not in trace.read_text()
            results.append({'case': 'direct_guard_'+str(code), 'exit_code': code, 'no_remote_writes': True})
        # Real Git exercises the SSH bundle installer without a network service.
        real = root / 'source'
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(real)], check=True)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(real), '-c', 'user.name=QA', '-c', 'user.email=qa@example.test', *args], text=True).strip()
        (real / 'keep').write_text('old')
        git('add', '.'); git('commit', '-qm', 'old')
        old = git('rev-parse', 'HEAD')
        git('bundle', 'create', str(root / 'old.bundle'), 'HEAD')
        cloud = root / 'cloud'
        subprocess.run(['git', 'clone', '-q', str(real), str(cloud)], check=True)
        for rel in ('linkcheck.py', 'ops/research_catalog.py', 'ops/research-intro.tmpl', 'ops/sync-wenshucha-site.sh', 'ops/publish-site.sh', 'ops/install-site-source.sh'):
            path = real / rel; path.parent.mkdir(exist_ok=True); path.write_text('new guard fixture')
        git('add', '.'); git('commit', '-qm', 'new guard')
        new = git('rev-parse', 'HEAD')
        git('bundle', 'create', str(root / 'new.bundle'), 'HEAD', '^'+old)
        (cloud / 'untracked-note').write_text('preserve')
        installer = str(SITE / 'ops/install-site-source.sh')
        process = run(['bash', installer, str(root / 'new.bundle'), new, str(cloud)])
        assert process.returncode == 0, (process.stdout, process.stderr)
        assert subprocess.check_output(['git', '-C', str(cloud), 'rev-parse', 'HEAD'], text=True).strip() == new
        assert (cloud / 'untracked-note').read_text() == 'preserve'
        results.append({'case': 'real_git_bundle_updates_source', 'pass': True, 'untracked_preserved': True})
        (cloud / 'keep').write_text('other work')
        process = run(['bash', installer, str(root / 'new.bundle'), new, str(cloud)])
        assert process.returncode == 2 and (cloud / 'keep').read_text() == 'other work'
        results.append({'case': 'tracked_dirty_checkout', 'exit_code': 2, 'other_work_preserved': True})
        (cloud / 'keep').write_text('old')
        process = run(['bash', installer, str(root / 'old.bundle'), old, str(cloud)])
        assert process.returncode == 2
        assert subprocess.check_output(['git', '-C', str(cloud), 'rev-parse', 'HEAD'], text=True).strip() == new
        results.append({'case': 'bundle_with_old_unguarded_source', 'exit_code': 2, 'source_not_rolled_back': True})
        # A different child of the old base is not an authorized successor.
        git('checkout', '-q', '-b', 'divergent', old)
        for rel in ('linkcheck.py', 'ops/research_catalog.py', 'ops/research-intro.tmpl', 'ops/sync-wenshucha-site.sh', 'ops/publish-site.sh', 'ops/install-site-source.sh'):
            path = real / rel; path.parent.mkdir(exist_ok=True); path.write_text('fork fixture')
        (real / 'fork').write_text('unrelated change')
        git('add', '.'); git('commit', '-qm', 'divergent source')
        divergent = git('rev-parse', 'HEAD')
        git('bundle', 'create', str(root / 'divergent.bundle'), 'HEAD', '^'+old)
        process = run(['bash', installer, str(root / 'divergent.bundle'), divergent, str(cloud)])
        assert process.returncode == 2 and 'divergent' in process.stdout
        assert subprocess.check_output(['git', '-C', str(cloud), 'rev-parse', 'HEAD'], text=True).strip() == new
        results.append({'case': 'divergent_bundle', 'exit_code': 2, 'source_not_rolled_back': True})
    print(json.dumps({'status': 'pass', 'cases': results}, indent=2))


if __name__ == '__main__':
    main()
