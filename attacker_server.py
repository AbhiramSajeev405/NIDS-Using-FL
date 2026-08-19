"""
FL-NIDS Physical Testbed — Attacker Server (Country-Side Receiver)
===================================================================
Lightweight FastAPI service running on each country laptop. Receives
attack-injected CSV data from the attacker node and merges it into
the client's training data directory.

This server auto-starts alongside the country node runner.

Endpoints:
    POST /inject     — Receive attack CSV for a specific client
    GET  /status     — Report injection status
    GET  /health     — Health check

Usage:
    python attacker_server.py --port 9090
"""

import os
import sys
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="FL-NIDS Attack Receiver", version="1.0.0")

PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data" / "processed"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"

# API key for authenticating inject/restore requests.
# Set FL_NIDS_API_KEY environment variable on both the attacker and country laptops.
# If not set, authentication is disabled (for backward compatibility with local testing).
API_KEY = os.environ.get("FL_NIDS_API_KEY", None)

# Track injections
injection_log: list[dict] = []

logger = logging.getLogger("attack_receiver")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] INJECT %(message)s", "%H:%M:%S"))
    logger.addHandler(ch)


def _verify_api_key(x_api_key: str = Header(None)):
    """Verify API key if FL_NIDS_API_KEY is set. Allows requests if not configured (for local testing)."""
    if API_KEY is not None and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.post("/inject")
async def inject_attack(payload: dict, x_api_key: str = Header(None)):
    """Receive and apply attack data for a specific client."""
    _verify_api_key(x_api_key)
    client_id = payload.get("client_id")
    attack_type = payload.get("attack_type", "unknown")
    csv_data = payload.get("csv_data")

    if not client_id or not csv_data:
        return JSONResponse(
            status_code=400,
            content={"error": "client_id and csv_data required"}
        )

    target_file = DATA_DIR / f"{client_id}.csv"
    if not target_file.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"{client_id}.csv not found on this node"}
        )

    # Backup original data (only once)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_file = BACKUP_DIR / f"{client_id}_original.csv"
    if not backup_file.exists():
        shutil.copy2(str(target_file), str(backup_file))
        logger.info(f"Backed up original {client_id}.csv")

    # Write the attack-injected data
    with open(target_file, "w", newline="", encoding="utf-8") as f:
        f.write(csv_data)

    entry = {
        "client_id": client_id,
        "attack_type": attack_type,
        "timestamp": datetime.now().isoformat(),
        "bytes_written": len(csv_data),
    }
    injection_log.append(entry)
    logger.info(f"Injected {attack_type} into {client_id} ({len(csv_data)} bytes)")

    return JSONResponse(content={"status": "injected", **entry})


@app.post("/restore")
async def restore_original(payload: dict = None, x_api_key: str = Header(None)):
    """Restore original (clean) data for a client or all clients."""
    _verify_api_key(x_api_key)
    """Restore original (clean) data for a client or all clients."""
    if payload is None:
        payload = {}
    client_id = payload.get("client_id")

    restored = []
    if client_id:
        backup = BACKUP_DIR / f"{client_id}_original.csv"
        target = DATA_DIR / f"{client_id}.csv"
        if backup.exists():
            shutil.copy2(str(backup), str(target))
            restored.append(client_id)
    else:
        # Restore all
        if BACKUP_DIR.exists():
            for backup in BACKUP_DIR.glob("*_original.csv"):
                cid = backup.name.replace("_original.csv", "")
                target = DATA_DIR / f"{cid}.csv"
                shutil.copy2(str(backup), str(target))
                restored.append(cid)

    logger.info(f"Restored original data for: {restored}")
    return JSONResponse(content={"restored": restored})


@app.get("/status")
async def get_status():
    """Report injection status."""
    return JSONResponse(content={
        "injections": len(injection_log),
        "log": injection_log[-20:],
    })


@app.get("/health")
async def health():
    """Health check."""
    return JSONResponse(content={"status": "ok", "role": "attack_receiver"})


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Attack Receiver Server")
    parser.add_argument("--port", type=int, default=9090)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
