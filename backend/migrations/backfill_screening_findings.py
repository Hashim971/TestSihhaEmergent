"""Backfill structured findings onto screening reports generated before the extraction agent existed.

Idempotent — only touches reports without `findings_extracted_at`.
Run:  cd /app/backend && python migrations/backfill_screening_findings.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import server
from server import db, extract_report_findings


async def main():
    reports = await db.health_reports.find(
        {"findings_extracted_at": {"$exists": False}}, {"_id": 0}
    ).sort("generated_at", -1).to_list(500)
    print(f"reports to structure: {len(reports)}")
    for r in reports:
        findings = await extract_report_findings(r, invoked_by="migration")
        state = f"{len(findings)} findings" if findings is not None else "FAILED"
        print(f"  {r['report_id']} ({r['generated_at'][:10]}): {state}")
    remaining = await db.health_reports.count_documents({"findings_extracted_at": {"$exists": False}})
    print(f"done — {remaining} still unstructured")


if __name__ == "__main__":
    asyncio.run(main())
