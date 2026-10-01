"""Run the existing suite against the compiled artifact in an isolated tree."""
from pathlib import Path
import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('artifact', type=Path)
args = parser.parse_args()
artifact = args.artifact.resolve()
expected = {'main.py'} | {p + '/__main__.py' for p in (
    'core/lunel_core', 'console/api/lunel_console', 'worker/lunel_worker')}
actual = {str(p.relative_to(artifact)) for p in artifact.rglob('*.py')}
if actual != expected:
    raise SystemExit(f'Unexpected Python sources: {actual ^ expected}')
if any(artifact.rglob('*.c')) or any(artifact.rglob('*.map')):
    raise SystemExit('Generated source or source maps leaked into artifact')
with tempfile.TemporaryDirectory(prefix='lunel-check-') as temporary:
    check = Path(temporary)
    shutil.copytree(artifact, check, dirs_exist_ok=True)
    shutil.copytree(ROOT / 'tests', check / 'tests',
                    ignore=shutil.ignore_patterns('__pycache__'))
    # Confirm tests cannot silently import the original checkout.
    subprocess.run([sys.executable, '-c',
        'import sys; from pathlib import Path; '
        'sys.path[:0]=["core","console/api","worker"]; '
        'import lunel_core.state, lunel_console.config, lunel_worker.driver; '
        'assert all(Path(m.__file__).suffix == ".so" for m in '
        '(lunel_core.state,lunel_console.config,lunel_worker.driver))'],
        cwd=check, check=True)
    subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q'],
                   cwd=check, check=True)
    subprocess.run([sys.executable, '-c',
        'import sys; from pathlib import Path; sys.path.insert(0,"console/api"); '
        'from lunel_console.panel import PAGE; '
        'from lunel_console.services.subscription import render_subscription; '
        'Path("panel.html").write_text(PAGE); '
        'Path("subscription.html").write_text(render_subscription("Test", [], '
        '"example.test", "/i/token/sub"))'], cwd=check, check=True)
    subprocess.run(['node', str(Path(__file__).with_name('browser-check.mjs')),
                    str(check / 'panel.html'), str(check / 'subscription.html')],
                   check=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env.update(PORT=str(port), LUNEL_DATABASE_URL=f'sqlite:///{check / "check.db"}',
               LUNEL_SECRET_KEY='verification-' * 4,
               LUNEL_WORKER_DATA=str(check / 'instances'))
    with (check / 'boot.log').open('w+') as log:
        service = subprocess.Popen([sys.executable, 'main.py'], cwd=check,
                                   env=env, stdout=log, stderr=log)
        try:
            for attempt in range(100):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if service.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read())
                    time.sleep(0.1)
            else:
                raise RuntimeError('Compiled unified service did not become healthy')
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
                assert b'<script>' in response.read()
            print('Unified service startup and HTTP checks passed')
        finally:
            service.terminate()
            try:
                service.wait(timeout=10)
            except subprocess.TimeoutExpired:
                service.kill()
                service.wait()
