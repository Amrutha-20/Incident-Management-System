#!/usr/bin/env python3
"""
Seed script — simulates a realistic failure scenario:
  1. RDBMS outage (P0) — burst of 150 signals → 1 Work Item
  2. MCP Host failure (P0) — triggered 30s later
  3. Cache degradation (P2) — background noise

Usage:
  python scripts/seed_failure_scenario.py [--url http://localhost:8000]
"""

import asyncio
import httpx
import random
import argparse
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"

RDBMS_SIGNALS = [
    {
        "component_id": "POSTGRES_PRIMARY_01",
        "component_type": "RDBMS",
        "error_code": "CONN_REFUSED",
        "message": f"Connection refused on attempt {i}. Host unreachable.",
        "severity": "P0",
        "metadata": {"attempt": i, "host": "10.0.1.5", "port": 5432},
    }
    for i in range(1, 151)  # 150 signals → should produce 1 Work Item
]

MCP_SIGNALS = [
    {
        "component_id": "MCP_HOST_PRIMARY",
        "component_type": "MCP_HOST",
        "error_code": "AGENT_UNREACHABLE",
        "message": f"MCP host not responding. Agent {i} timed out.",
        "severity": "P0",
        "metadata": {"agent_id": f"agent-{i:03d}", "timeout_ms": 5000},
    }
    for i in range(1, 51)
]

CACHE_SIGNALS = [
    {
        "component_id": "CACHE_CLUSTER_01",
        "component_type": "CACHE",
        "error_code": "CACHE_MISS_STORM",
        "message": "Cache miss rate exceeding threshold. Falling back to DB.",
        "severity": "P2",
        "metadata": {"miss_rate_pct": random.uniform(60, 95)},
    }
    for _ in range(30)
]


async def send_batch(client: httpx.AsyncClient, signals: list[dict], label: str) -> None:
    print(f"\n[SEED] Sending {len(signals)} {label} signals...")
    # Send in batches of 50
    for i in range(0, len(signals), 50):
        batch = signals[i:i+50]
        resp = await client.post(
            f"{BASE_URL}/api/v1/signals/batch",
            json=batch,
            timeout=30.0,
        )
        print(f"  Batch {i//50 + 1}: {resp.status_code} → {resp.json()}")
        await asyncio.sleep(0.1)


async def create_work_item_rca(client: httpx.AsyncClient, work_item_id: str) -> None:
    """Walk a Work Item through full lifecycle with RCA."""
    now = datetime.now(timezone.utc)

    for new_status in ["INVESTIGATING", "RESOLVED"]:
        resp = await client.patch(
            f"{BASE_URL}/api/v1/incidents/{work_item_id}/status",
            json={"new_status": new_status},
            timeout=10.0,
        )
        print(f"  Transitioned to {new_status}: {resp.status_code}")
        await asyncio.sleep(0.5)

    # Close with RCA
    rca_payload = {
        "new_status": "CLOSED",
        "rca": {
            "incident_start": (now.replace(hour=now.hour - 1)).isoformat(),
            "incident_end": now.isoformat(),
            "root_cause_category": "INFRASTRUCTURE",
            "root_cause_description": (
                "Primary PostgreSQL node ran out of file descriptors due to "
                "connection pool misconfiguration after a deployment."
            ),
            "fix_applied": (
                "Increased ulimit for postgres process, restarted connection pool, "
                "rolled back misconfigured deployment."
            ),
            "prevention_steps": (
                "Add connection pool size monitoring alert at 80% threshold. "
                "Add pre-deploy config validation for connection pool settings. "
                "Update runbook with fd-exhaustion diagnosis steps."
            ),
        },
    }
    resp = await client.patch(
        f"{BASE_URL}/api/v1/incidents/{work_item_id}/status",
        json=rca_payload,
        timeout=10.0,
    )
    print(f"  Closed with RCA: {resp.status_code}")


async def main(base_url: str) -> None:
    print(f"[SEED] Target: {base_url}")
    print("[SEED] Starting failure scenario simulation...\n")

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Health check
        resp = await client.get("/health")
        print(f"[SEED] Health: {resp.status_code} → {resp.json().get('status')}")

        # Phase 1: RDBMS outage burst
        print("\n=== Phase 1: RDBMS Primary Outage (P0) ===")
        await send_batch(client, RDBMS_SIGNALS, "RDBMS")
        await asyncio.sleep(2)

        # Phase 2: MCP Host failure
        print("\n=== Phase 2: MCP Host Failure (P0) ===")
        await send_batch(client, MCP_SIGNALS, "MCP_HOST")
        await asyncio.sleep(1)

        # Phase 3: Cache degradation (background noise)
        print("\n=== Phase 3: Cache Degradation (P2) ===")
        await send_batch(client, CACHE_SIGNALS, "CACHE")
        await asyncio.sleep(2)

        # Fetch active incidents
        print("\n=== Active Incidents ===")
        resp = await client.get("/api/v1/incidents")
        incidents = resp.json()
        print(f"Found {len(incidents)} active work items:")
        for inc in incidents:
            print(f"  [{inc.get('priority')}] {inc.get('component_id')} — "
                  f"{inc.get('status')} — signals: {len(inc.get('signal_ids', []))}")

        # Walk the first RDBMS work item through lifecycle
        rdbms_wi = next(
            (i for i in incidents if i.get("component_type") == "RDBMS"), None
        )
        if rdbms_wi:
            print(f"\n=== Resolving RDBMS Work Item {rdbms_wi['work_item_id']} ===")
            await create_work_item_rca(client, rdbms_wi["work_item_id"])

        print("\n[SEED] Scenario complete. Check /docs for API explorer.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMS failure scenario seed script")
    parser.add_argument("--url", default=BASE_URL, help="Backend base URL")
    args = parser.parse_args()
    asyncio.run(main(args.url))