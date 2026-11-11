"""Create a private collaboration password verifier using masked local input."""
import argparse
import getpass
import hashlib
import os
from pathlib import Path
import secrets
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('File already exists. Choose a new path to rotate the verifier.')
    if not sys.stdin.isatty():
        raise SystemExit('Run in an interactive terminal for masked password input.')
    password = getpass.getpass('Editing password: ')
    if not password or len(password) > 256 or password != getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords must match and contain 1–256 characters.')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    verifier = f'pbkdf2:100000:{salt.hex()}:{digest.hex()}\n'
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        stream.write(verifier)
    print('Private verifier created. No password is stored; restart the collaboration service to apply it.')


if __name__ == '__main__':
    main()
