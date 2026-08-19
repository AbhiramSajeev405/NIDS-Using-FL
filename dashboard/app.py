"""
FL-NIDS Real-Time Live Dashboard FastAPI Backend.

Serves the dashboard HTML/CSS/JS and provides WebSocket endpoints
for real-time data streaming from live_state.json.

Start:
cd d:\\PhysicalTestBedFiles
python -m uvicorn dashboard.app:app --host 127.0.0.1 --port 456

Or:
python dashboard/app.py
"""

import os
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# We do not initialize RealTimeLogger here to ensure the Global Server
# remains the single absolute owner of the live_state.json file.

app = FastAPI(title="FL-NIDS Live Dashboard", version="2.0.0")

# Allow cross-origin access from other laptops on the LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
STATE_FILE = Path(__file__).parent / "live_state.json"

# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard page."""
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/state")
async def get_state():
    """Get the current live state as JSON."""
    return JSONResponse(content=_load_state())


@app.get("/api/history")
async def get_history():
    """Get full convergence history."""
    state = _load_state()
    return JSONResponse(content=state.get("convergence_history", []))


@app.get("/api/experiments")
async def list_experiments():
    """List past experiment result directories."""
    results_dir = Path(__file__).parent.parent / "results"
    experiments = []
    if results_dir.exists():
        for d in sorted(results_dir.iterdir()):
            if d.is_dir():
                experiments.append({
                    "id": d.name,
                    "path": str(d),
                    "created": datetime.fromtimestamp(d.stat().st_ctime).isoformat(),
                })
    return JSONResponse(content=experiments)


@app.get("/api/scenarios")
async def list_scenarios():
    """List available attack scenarios."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from simulation.scenario_profiles import list_scenarios as _list
        return JSONResponse(content=_list())
    except ImportError:
        return JSONResponse(content=[])


@app.get("/api/anomaly/scores")
async def get_anomaly_scores():
    """Get latest anomaly score data."""
    state = _load_state()
    return JSONResponse(content=state.get("anomaly", {}))


@app.get("/api/timeline")
async def get_timeline():
    """Get training timeline data."""
    state = _load_state()
    return JSONResponse(content=state.get("timeline", []))


@app.get("/api/divergence")
async def get_divergence():
    """Get per-client weight divergence data."""
    state = _load_state()
    return JSONResponse(content=state.get("weight_divergence", {}))


@app.post("/api/incident")
async def log_incident(request: Request):
    """Receive an incident manually injected from the attacker node."""
    try:
        payload = await request.json()
        client_id = payload.get("client_id", "Unknown")
        attack_type = payload.get("attack_type", payload.get("type", "Unknown Attack"))
        action = payload.get("action", "Escalated")
        status = payload.get("status", "Investigating")

        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            data.setdefault("incidents", []).append({
                "timestamp": datetime.now().isoformat(),
                "client_id": client_id,
                "type": "attack",
                "attack_type": attack_type,
                "action": action,
                "status": status,
                "severity": "high"
            })

            # Keep max incidents bounded
            if len(data["incidents"]) > 100:
                data["incidents"] = data["incidents"][-100:]

            tmp_file = str(STATE_FILE) + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_file, STATE_FILE)

            return JSONResponse(content={"status": "incident_logged"})
        else:
            return JSONResponse(status_code=500, content={"error": "Live state file does not exist."})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


import re

@app.get("/api/config")
async def get_config():
    """Get the current configuration from physical_config.yaml"""
    config_path = Path(__file__).parent.parent / "config" / "physical_config.yaml"
    if not config_path.exists():
        return JSONResponse(status_code=404, content={"error": "Config file not found"})
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            conf = yaml.safe_load(f)
        return JSONResponse(content={
            "model": conf.get("model_type", "mlp"),
            "strategy": conf.get("federated", {}).get("strategy", "fedavg"),
            "scenario": conf.get("attacker_scenario", "none"),
            "rounds": conf.get("federated", {}).get("num_rounds_global", 80)
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/config/save")
async def save_config_endpoint(payload: dict):
    """Save configuration to physical_config.yaml, using regex to preserve comments."""
    config_path = Path(__file__).parent.parent / "config" / "physical_config.yaml"
    if not config_path.exists():
        return JSONResponse(status_code=404, content={"error": "Config file not found"})
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Safely replace values if they exist, to preserve all existing YAML comments
        if "model" in payload:
            content = re.sub(r'model_type:\s*".*?"', f'model_type: "{payload["model"]}"', content)
        if "strategy" in payload:
            content = re.sub(r'strategy:\s*".*?"', f'strategy: "{payload["strategy"]}"', content)
        if "scenario" in payload:
            # Matches 'scenario: "..."' inside the attacker block
            content = re.sub(r'scenario:\s*".*?"', f'scenario: "{payload["scenario"]}"', content)
        if "rounds" in payload:
            content = re.sub(r'num_rounds_global:\s*\d+', f'num_rounds_global: {payload["rounds"]}', content)

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)

        return JSONResponse(content={"status": "success", "message": "Configuration saved on disk."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/scenario/activate")
async def activate_scenario(payload: dict = {}):
    """Set the active scenario profile."""
    scenario_id = payload.get("scenario_id", "none")
    return JSONResponse(content={"status": "activated", "scenario": scenario_id})


# CONTROL ENDPOINTS

SHUTDOWN_TRIGGER = Path(__file__).parent.parent / "shutdown.trigger"
RELOAD_TRIGGER = Path(__file__).parent.parent / "reload.trigger"

@app.post("/api/shutdown")
async def trigger_shutdown():
    """Trigger system shutdown by creating a trigger file."""
    try:
        SHUTDOWN_TRIGGER.touch()
        return JSONResponse(content={"status": "success", "message": "Shutdown triggered"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/reload")
async def trigger_reload():
    """Trigger configuration reload by touching the config file."""
    try:
        config_path = Path(__file__).parent.parent / "config" / "physical_config.yaml"
        if config_path.exists():
            config_path.touch()
        return JSONResponse(content={"status": "success", "message": "Configuration reload triggered"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# WebSocket

class ConnectionManager:
    """Manage active WebSocket connections."""

    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """WebSocket endpoint for live dashboard updates.

    Pushes the current state every 1 second to all connected clients.
    """
    await manager.connect(ws)
    try:
        while True:
            state = _load_state()
            await ws.send_json(state)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# Helpers

def _load_state():
    """Load the current state from the JSON file. No fallback to demo data."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Compatibility mapping: telemetry engine writes 'training', frontend expects 'training_status'
            if "training" in data and "training_status" not in data:
                data["training_status"] = data["training"]

            if "training_status" in data and "meta" in data:
                # Add metadata parameters into training_status to populate the dashboard header
                m = data["meta"]
                ts = data["training_status"]
                ts["model_type"] = m.get("model_type", "-")
                ts["strategy"] = m.get("strategy", "-")
                ts["architecture"] = m.get("architecture", "-")
                ts["scenario"] = data.get("scenario", "-")  # attacker scenario if present

                # Convert ISO start_time to epoch seconds for the frontend elapsed time clock
                try:
                    ts["start_time"] = int(datetime.fromisoformat(m["start_time"]).timestamp())
                except:
                    ts["start_time"] = int(time.time())

            # Add compatibility aliases for global_metrics
            if "global_metrics" in data:
                gm = data["global_metrics"]
                # Map false_positive_rate to fpr for dashboard compatibility
                if "fpr" not in gm and "false_positive_rate" in gm:
                    gm["fpr"] = gm["false_positive_rate"]
                # Map true_negative_rate to specificity for dashboard compatibility
                if "specificity" not in gm and "true_negative_rate" in gm:
                    gm["specificity"] = gm["true_negative_rate"]

            if "training_status" in data:
                # Add a 'timestamp' to track data freshness on the client-side
                data["_server_time"] = time.time()
            return data
        except (json.JSONDecodeError, IOError):
            pass

    # Return an empty/idle state instead of generating fake math data
    return {
        "training_status": {
            "status": "idle",
            "current_round": 0,
            "total_rounds": 0,
            "model_type": "-",
            "strategy": "-",
            "architecture": "-",
            "scenario": "-",
            "start_time": 0,
        },
        "defenses": {},
        "global_metrics": {},
        "clients": {},
        "countries": {},
        "convergence_history": [],
        "communication_history": [],
        "anomaly": {"history": [], "current_mean": 0, "above_threshold": 0},
        "weight_divergence": {},
        "timeline": [],
        "incidents": [],
        "poison_detection": {},
        "drift": {},
        "fairness": {},
        "_server_time": time.time()
    }


# Direct run

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=456)
