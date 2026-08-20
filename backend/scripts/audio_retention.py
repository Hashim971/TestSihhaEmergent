"""Hard-deletes consultation audio past its retention window, keeping the metadata row for audit.

Run from .emergent/cron (daily) or manually:
  cd /app/backend && python scripts/audio_retention.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server import purge_expired_audio  # noqa: E402

if __name__ == "__main__":
    print(asyncio.run(purge_expired_audio()))
