#!/usr/bin/env python3
"""End-to-end shell transaction on isolated Git A, wrong HOME B and fake transport."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SITE = Path(__file__).resolve().parents[1]


def main():
    results = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        a, cloud, web, home, bin = (root / n for n in ('source-A', 'cloud', 'web', 'home-B', 'bin'))
        for p in (a, web, home / 'wenshucha-site', bin): p.mkdir(parents=True)
        (home / 'wenshucha-site/index.html').write_text('WRONG SOURCE B')
        (a / 'ops/nginx').mkdir(parents=True)
        for rel in ('deploy-to-server.sh', 'ops/publish-site.sh', 'ops/install-site-source.sh'):
            shutil.copy2(SITE / rel, a / rel)
        (a / 'gen_llms.py').write_text('pass\n')
        (a / 'linkcheck.py').write_text("import os,sys\nfrom pathlib import Path\np=Path(sys.argv[1])\nassert 'SOURCE A' in (p/'index.html').read_text()\nif str(p)==os.environ['QA_CLOUD']: raise SystemExit(int(os.environ.get('QA_CLOUD_GUARD_RC','0')))\n")
        (a / 'ops/research_catalog.py').write_text('# fixture\n')
        (a / 'ops/research-intro.tmpl').write_text('fixture')
        (a / 'ops/sync-wenshucha-site.sh').write_text('#!/bin/bash\n# fixture cron\n')
        (a / 'ops/nginx/html_wenshucha.com.conf').write_text('unchanged rewrite')
        (a / 'index.html').write_text('SOURCE A 粤ICP备2025437990号-2')
        def git(*args):
            return subprocess.check_output(['git','-C',str(a),'-c','user.name=QA','-c','user.email=qa@example.test',*args],text=True).strip()
        subprocess.run(['git','init','-q','-b','main',str(a)],check=True)
        git('add','.'); git('commit','-qm','base')
        old=git('rev-parse','HEAD')
        (a / 'revision').write_text('checked source A')
        git('add','.'); git('commit','-qm','checked A')
        rev=git('rev-parse','HEAD')
        subprocess.run(['git','clone','-q',str(a),str(cloud)],check=True)
        stamp, sync, rewrite, trace = (root / n for n in ('stamp','sync.sh','rewrite','trace'))
        sync.write_text('#!/bin/bash\n# old cron\n'); rewrite.write_text('unchanged rewrite')
        env={**os.environ,'HOME':str(home),'PATH':str(bin)+':'+os.environ['PATH'],
             'QA_REV':rev,'QA_CLOUD':str(cloud),'QA_STAGE':str(root/'stage'),'QA_TRACE':str(trace),
             'WSC_SYNC_REPO':str(cloud),'WSC_SYNC_WEB':str(web),'WSC_SYNC_STAMP':str(stamp),
             'WSC_SYNC_SCRIPT':str(sync),'WSC_SYNC_REWRITE':str(rewrite),'QA_LOCK':str(root/'lock')}
        def exe(name, body):
            p=bin/name;p.write_text('#!'+sys.executable+'\n'+body);p.chmod(0o700)
        exe('ssh', r'''
import fcntl,os,pathlib,shlex,subprocess,sys
command=sys.argv[-1]
if command.startswith('git -C /opt/wenshucha-site-repo'):
 print(os.environ['QA_REV']);sys.exit(0)
prefix='/tmp/wsc-site-deploy-'+os.environ['QA_REV']
command=command.replace(prefix,os.environ['QA_STAGE'])
if command.startswith('flock '):
 args=shlex.split(command);assert args[:4]==['flock','-w','45','/tmp/sync-wsc.lock']
 with open(os.environ['QA_LOCK'],'w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  probe='import fcntl,sys; f=open(sys.argv[1]);\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: sys.exit(23)\nsys.exit(99)'
  assert subprocess.run([sys.executable,'-c',probe,os.environ['QA_LOCK']]).returncode==23
  with open(os.environ['QA_TRACE'],'a') as f:f.write('cron_blocked_by_same_lock\n')
  sys.exit(subprocess.run(args[4:]).returncode)
sys.exit(subprocess.run(['bash','-c',command]).returncode)
''')
        exe('scp', r'''
import os,pathlib,shutil,sys
dest=sys.argv[-1].split(':',1)[1].replace('/tmp/wsc-site-deploy-'+os.environ['QA_REV'],os.environ['QA_STAGE'])
pathlib.Path(dest).mkdir(parents=True,exist_ok=True)
for source in sys.argv[1:-1]:shutil.copy2(source,pathlib.Path(dest)/pathlib.Path(source).name)
''')
        exe('rsync', r'''
import os,pathlib,shutil,sys
source,dest=map(pathlib.Path,sys.argv[-2:]);assert 'source-A' not in str(source) and str(source).startswith(os.environ['QA_STAGE'])
assert 'SOURCE A' in (source/'index.html').read_text()
assert 'WRONG SOURCE B' not in (source/'index.html').read_text()
for p in source.rglob('*'):
 rel=p.relative_to(source)
 if p.is_dir() or 'ops' in rel.parts or p.suffix in ('.py','.sh') or p.name.startswith('README'):continue
 target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
with open(os.environ['QA_TRACE'],'a') as f:f.write('rsync_checked_archive_A\n')
''')
        exe('curl', r'''
import os,pathlib,sys
args=sys.argv[1:];url=args[-1]
if '-I' in args:print('location: https://www.wenshucha.com/\r\n')
elif '-w' in args:print('301' if url.endswith('/index.html') else '200' if url.endswith('.com/') else '403',end='')
else:print((pathlib.Path(os.environ['WSC_SYNC_WEB'])/'index.html').read_text())
''')
        exe('sha256sum', r'''
import hashlib,os,pathlib,sys
if os.environ.get('QA_MANIFEST_FAIL')=='1':sys.exit(1)
for line in pathlib.Path(sys.argv[-1]).read_text().splitlines():
 expected,name=line.split('  ',1);assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==expected
''')
        exe('chown','pass\n')
        os.symlink(sys.executable,bin/'python3')
        for name, guard_rc, manifest_fail, expected_rc in [('success',0,0,0),('remote_catalog_unknown',2,0,2),('final_validation_failure',0,1,1)]:
            trace.write_text('');stamp.write_text(old);(web/'index.html').write_text('previous published bytes')
            process=subprocess.run(['bash',str(a/'deploy-to-server.sh')],env={**env,'QA_CLOUD_GUARD_RC':str(guard_rc),'QA_MANIFEST_FAIL':str(manifest_fail)},text=True,capture_output=True)
            assert process.returncode==expected_rc,(name,process.stdout,process.stderr)
            if expected_rc==0:
                assert stamp.read_text().strip()==rev and 'SOURCE A' in (web/'index.html').read_text()
                assert 'rsync_checked_archive_A' in trace.read_text()
            else:
                assert stamp.read_text()==old
                if guard_rc:assert (web/'index.html').read_text()=='previous published bytes' and 'rsync_' not in trace.read_text()
            assert 'cron_blocked_by_same_lock' in trace.read_text()
            results.append({'case':name,'exit_code':process.returncode,'source_A_not_HOME_B':True,'lock_contends_with_cron':True,'success_stamp_only_after_validation':True})
    print(json.dumps({'status':'pass','cases':results},indent=2))


if __name__=='__main__':main()
