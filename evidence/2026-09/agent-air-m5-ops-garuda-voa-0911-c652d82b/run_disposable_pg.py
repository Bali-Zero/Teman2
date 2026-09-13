"""Run the VOA D proof on an existing Pro venv and a throwaway PG17 cluster.

No production DSN or shared PostgreSQL server is used. The cluster is stopped
in finally, including on a failed test run. Run from apps/backend-rag.
"""

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile


def main():
    binaries = Path('/opt/homebrew/opt/postgresql@17/bin')
    with tempfile.TemporaryDirectory(prefix='voa-d-pg-0911-') as temporary:
        root = Path(temporary)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cluster = root / 'data'
        subprocess.run(
            [str(binaries / 'initdb'), '-D', str(cluster), '-U', 'voa_proof_admin',
             '--auth=trust', '--encoding=UTF8', '--no-locale'],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        (cluster / 'postgresql.conf').write_text(
            f"listen_addresses = '127.0.0.1'\nport = {port}\n"
            f"unix_socket_directories = '{root}'\nfsync = off\n"
        )
        control = [str(binaries / 'pg_ctl'), '-D', str(cluster)]
        started = False
        try:
            subprocess.run(control + ['-l', str(root / 'postgres.log'), '-w', 'start'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            started = True
            env = {key: value for key, value in os.environ.items()
                   if not any(word in key.upper() for word in ('TOKEN', 'SECRET', 'API_KEY', 'DSN', 'DATABASE_URL'))}
            dsn = f'postgresql://voa_proof_admin@127.0.0.1:{port}/postgres'
            env.update(TEST_DATABASE_URL=dsn, DATABASE_URL=dsn, INTAKE_TEST_DSN=dsn,
                       MIGRATION_DATABASE_URL='', ENVIRONMENT='test', PYTHONPATH='.',
                       API_KEYS='unit-test-only', JWT_SECRET_KEY='proof-only-key-with-at-least-thirty-two-characters',
                       TELEGRAM_BOT_TOKEN='123456:synthetic', TG_DRY_RUN='1',
                       OPENAI_API_KEY='synthetic-not-a-key', GOOGLE_API_KEY='synthetic-not-a-key')
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', '-o', 'addopts=', '-p', 'no:cacheprovider',
                 '--tb=short', '-q', *sys.argv[1:]], env=env,
            )
            return result.returncode
        finally:
            if started:
                subprocess.run(control + ['-m', 'immediate', '-w', 'stop'], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                print('DISPOSABLE_PG_STOPPED', flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
