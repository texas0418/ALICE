#!/usr/bin/env python3
"""One place for secrets, on any platform.

Every tool used to shell out to macOS `security` directly. This module keeps the
same contract — a secret is looked up by (account, service), read at runtime, and
never written to a file in the repo — and picks the store for the OS:

  macOS   Keychain via `security`                       (what the reference build uses)
  Linux   libsecret via `secret-tool` (GNOME Keyring / KWallet)
  any     environment variable fallback: JARVIS_<SERVICE> with - and . -> _
          e.g. JARVIS_ANTHROPIC_KEY, JARVIS_MAPBOX_TOKEN, JARVIS_MAIL_you_example_com

`get` returns None when nothing is stored; callers decide whether that is fatal.
`put` stores (used by tools that rotate tokens, e.g. OAuth refresh tokens).
`hint(account, service)` returns the exact command a user should run to store it —
so error messages stay copy-pasteable on both platforms.

CLI:  vault.py get <account> <service>
      vault.py put <account> <service>      (prompts, hidden)
"""
import getpass, os, platform, shutil, subprocess, sys

DEFAULT_ACCOUNT = 'jarvis-mirror'
IS_MAC = platform.system() == 'Darwin'


def _env_name(account, service):
    tag = service if account == DEFAULT_ACCOUNT else f'{service}_{account}'
    return 'JARVIS_' + ''.join(c if c.isalnum() else '_' for c in tag).upper()


def get(account, service):
    env = os.environ.get(_env_name(account, service))
    if env:
        return env.strip()
    if IS_MAC:
        r = subprocess.run(['security', 'find-generic-password', '-a', account,
                            '-s', service, '-w'], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    if shutil.which('secret-tool'):
        r = subprocess.run(['secret-tool', 'lookup', 'account', account,
                            'service', service], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    return None


def put(account, service, value):
    """Store or replace. Value is passed via stdin/argv of the OS tool, never a file."""
    if IS_MAC:
        subprocess.run(['security', 'add-generic-password', '-U', '-a', account,
                        '-s', service, '-w', value], capture_output=True)
        return True
    if shutil.which('secret-tool'):
        subprocess.run(['secret-tool', 'store', '--label', f'{service} ({account})',
                        'account', account, 'service', service],
                       input=value, text=True, capture_output=True)
        return True
    return False


def hint(account, service):
    if IS_MAC:
        return f'security add-generic-password -U -a {account} -s {service} -w'
    if shutil.which('secret-tool'):
        return (f"secret-tool store --label '{service}' account {account} "
                f'service {service}')
    return f'export {_env_name(account, service)}=...   (or install libsecret-tools)'


def backend():
    if IS_MAC:
        return 'macOS Keychain'
    if shutil.which('secret-tool'):
        return 'libsecret (secret-tool)'
    return 'environment variables only'


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == 'get':
        v = get(sys.argv[2], sys.argv[3])
        print('(set)' if v else '(missing)')
    elif len(sys.argv) >= 4 and sys.argv[1] == 'put':
        v = getpass.getpass('secret: ')
        print('stored' if put(sys.argv[2], sys.argv[3], v) else 'no secret store available')
    else:
        print(f'backend: {backend()}\n{__doc__}')
