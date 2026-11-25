"""Your PSN Account ID (base64) for registering chiaki-ng with a PS5, without chiaki-ng's PSN login page.

Sign in at https://www.playstation.com in your browser, then open https://ca.account.sony.com/api/v1/ssocookie:
it shows {"npsso":"..."}. Run this and paste that npsso value when asked (it isn't shown or saved):

  uv pip install --python .venv psnawp
  .venv/bin/python scripts/psn_account_id.py

The npsso works like a password to your PSN account for a while: don't share it, and sign out of playstation.com
afterwards if you want it to stop working.
"""
from __future__ import annotations

import base64
import getpass
import sys


def to_chiaki(account_id: int) -> str:
    """chiaki-ng's format: the account number as 8 little-endian bytes, base64."""
    return base64.b64encode(account_id.to_bytes(8, "little")).decode()


def main() -> int:
    try:
        from psnawp_api import PSNAWP
    except ImportError:
        print("Install it first: uv pip install --python .venv psnawp", file=sys.stderr)
        return 1
    npsso = getpass.getpass("npsso (from ca.account.sony.com/api/v1/ssocookie, not shown): ").strip().strip('"')
    if not npsso:
        return 1
    me = PSNAWP(npsso).me()
    account_id = int(me.account_id)
    print(f"\nPSN name: {me.online_id}")
    print(f"PSN Account ID for chiaki-ng: {to_chiaki(account_id)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
