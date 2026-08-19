"""
Attack Scenario Profiles for FL-NIDS.

Predefined attack scenarios for quick experiment switching.
Each scenario defines attack ratios per client, attack types,
timing patterns, and intensity levels.

Usage:
    from simulation.scenario_profiles import get_scenario, list_scenarios

    scenario = get_scenario("full_siege")
    for client_id, params in scenario["clients"].items():
        simulate_attack(client_id, attack_ratio=params["attack_ratio"])

Scenarios:
    gentle_probe    — Low-rate recon (5% attack ratio, all clients)
    targeted_strike — Single country targeted (50% on Country A only)
    full_siege      — All clients hammered simultaneously (40%)
    apt_campaign    — Multi-phase escalation over rounds
    insider_threat  — One compromised client sending poisoned updates
    zero_day        — Novel attack patterns not in training data
"""

import copy

# ─── Scenario Definitions ──────────────────────────────────────────

SCENARIOS = {
    "gentle_probe": {
        "name": "Gentle Probe",
        "description": "Low-rate reconnaissance across all clients. Tests baseline detection at low volume.",
        "difficulty": "easy",
        "attack_types": ["port_scan", "slow_probe"],
        "global_attack_ratio": 0.05,
        "duration_rounds": 1,
        "clients": {
            "Client_01": {"attack_ratio": 0.05, "attack_type": "port_scan"},
            "Client_02": {"attack_ratio": 0.03, "attack_type": "slow_probe"},
            "Client_03": {"attack_ratio": 0.05, "attack_type": "port_scan"},
            "Client_04": {"attack_ratio": 0.04, "attack_type": "slow_probe"},
            "Client_05": {"attack_ratio": 0.05, "attack_type": "port_scan"},
            "Client_06": {"attack_ratio": 0.03, "attack_type": "slow_probe"},
            "Client_07": {"attack_ratio": 0.05, "attack_type": "port_scan"},
            "Client_08": {"attack_ratio": 0.04, "attack_type": "slow_probe"},
            "Client_09": {"attack_ratio": 0.05, "attack_type": "port_scan"},
        },
    },

    "targeted_strike": {
        "name": "Targeted Strike",
        "description": "Heavy attack on Country A only. Tests if regional models can handle concentrated assault.",
        "difficulty": "medium",
        "attack_types": ["ddos_udp_flood", "brute_force"],
        "global_attack_ratio": 0.17,
        "duration_rounds": 1,
        "clients": {
            "Client_01": {"attack_ratio": 0.50, "attack_type": "ddos_udp_flood"},
            "Client_02": {"attack_ratio": 0.50, "attack_type": "brute_force"},
            "Client_03": {"attack_ratio": 0.50, "attack_type": "ddos_udp_flood"},
            "Client_04": {"attack_ratio": 0.0, "attack_type": None},
            "Client_05": {"attack_ratio": 0.0, "attack_type": None},
            "Client_06": {"attack_ratio": 0.0, "attack_type": None},
            "Client_07": {"attack_ratio": 0.0, "attack_type": None},
            "Client_08": {"attack_ratio": 0.0, "attack_type": None},
            "Client_09": {"attack_ratio": 0.0, "attack_type": None},
        },
    },

    "full_siege": {
        "name": "Full Siege",
        "description": "All clients hammered simultaneously with mixed attack types at max intensity.",
        "difficulty": "hard",
        "attack_types": ["ddos_udp_flood", "brute_force", "exfiltration", "ransomware"],
        "global_attack_ratio": 0.40,
        "duration_rounds": 1,
        "clients": {
            "Client_01": {"attack_ratio": 0.40, "attack_type": "ddos_udp_flood"},
            "Client_02": {"attack_ratio": 0.35, "attack_type": "brute_force"},
            "Client_03": {"attack_ratio": 0.45, "attack_type": "exfiltration"},
            "Client_04": {"attack_ratio": 0.40, "attack_type": "ransomware"},
            "Client_05": {"attack_ratio": 0.35, "attack_type": "ddos_udp_flood"},
            "Client_06": {"attack_ratio": 0.45, "attack_type": "brute_force"},
            "Client_07": {"attack_ratio": 0.40, "attack_type": "exfiltration"},
            "Client_08": {"attack_ratio": 0.35, "attack_type": "ransomware"},
            "Client_09": {"attack_ratio": 0.40, "attack_type": "ddos_udp_flood"},
        },
    },

    "apt_campaign": {
        "name": "APT Campaign",
        "description": "Multi-phase Advanced Persistent Threat. Escalates from recon → exploit → exfil over rounds.",
        "difficulty": "expert",
        "attack_types": ["recon", "exploit", "lateral_movement", "exfiltration"],
        "global_attack_ratio": 0.25,
        "duration_rounds": 5,
        "phases": [
            {
                "name": "Phase 1: Reconnaissance",
                "rounds": [1],
                "clients": {
                    "Client_01": {"attack_ratio": 0.05, "attack_type": "recon"},
                    "Client_02": {"attack_ratio": 0.03, "attack_type": "recon"},
                },
            },
            {
                "name": "Phase 2: Initial Exploit",
                "rounds": [2],
                "clients": {
                    "Client_01": {"attack_ratio": 0.15, "attack_type": "exploit"},
                    "Client_02": {"attack_ratio": 0.10, "attack_type": "exploit"},
                    "Client_03": {"attack_ratio": 0.08, "attack_type": "recon"},
                },
            },
            {
                "name": "Phase 3: Lateral Movement",
                "rounds": [3],
                "clients": {
                    "Client_01": {"attack_ratio": 0.20, "attack_type": "lateral_movement"},
                    "Client_02": {"attack_ratio": 0.20, "attack_type": "lateral_movement"},
                    "Client_03": {"attack_ratio": 0.15, "attack_type": "exploit"},
                    "Client_04": {"attack_ratio": 0.10, "attack_type": "recon"},
                },
            },
            {
                "name": "Phase 4: Escalation",
                "rounds": [4],
                "clients": {
                    "Client_01": {"attack_ratio": 0.35, "attack_type": "exfiltration"},
                    "Client_02": {"attack_ratio": 0.30, "attack_type": "exfiltration"},
                    "Client_03": {"attack_ratio": 0.25, "attack_type": "lateral_movement"},
                    "Client_04": {"attack_ratio": 0.20, "attack_type": "exploit"},
                    "Client_05": {"attack_ratio": 0.10, "attack_type": "recon"},
                },
            },
            {
                "name": "Phase 5: Full Exfiltration",
                "rounds": [5],
                "clients": {
                    "Client_01": {"attack_ratio": 0.50, "attack_type": "exfiltration"},
                    "Client_02": {"attack_ratio": 0.45, "attack_type": "exfiltration"},
                    "Client_03": {"attack_ratio": 0.40, "attack_type": "exfiltration"},
                    "Client_04": {"attack_ratio": 0.30, "attack_type": "lateral_movement"},
                    "Client_05": {"attack_ratio": 0.20, "attack_type": "exploit"},
                    "Client_06": {"attack_ratio": 0.10, "attack_type": "recon"},
                },
            },
        ],
    },

    "insider_threat": {
        "name": "Insider Threat",
        "description": "One compromised client (Client_05) sends subtly poisoned model updates. "
                       "Tests Byzantine fault tolerance of aggregation strategies.",
        "difficulty": "hard",
        "attack_types": ["model_poisoning"],
        "global_attack_ratio": 0.0,
        "duration_rounds": 1,
        "clients": {
            "Client_05": {"attack_ratio": 0.0, "attack_type": "model_poisoning", "poisoned": True},
        },
        "notes": "This scenario doesn't inject data attacks — it marks Client_05 as a Byzantine "
                 "client whose model weights should be manipulated by the defense testing framework.",
    },

    "zero_day": {
        "name": "Zero-Day Attack",
        "description": "Novel attack patterns not represented in any training data. "
                       "Tests generalization of the NIDS model.",
        "difficulty": "expert",
        "attack_types": ["unknown_exploit", "novel_c2"],
        "global_attack_ratio": 0.20,
        "duration_rounds": 1,
        "clients": {
            "Client_03": {"attack_ratio": 0.25, "attack_type": "unknown_exploit"},
            "Client_06": {"attack_ratio": 0.20, "attack_type": "novel_c2"},
            "Client_09": {"attack_ratio": 0.15, "attack_type": "unknown_exploit"},
        },
    },
}


# ─── Public API ─────────────────────────────────────────────────────

def list_scenarios():
    """List all available scenario profiles.

    Returns:
        List of dicts with scenario metadata
    """
    result = []
    for key, scenario in SCENARIOS.items():
        result.append({
            "id": key,
            "name": scenario["name"],
            "description": scenario["description"],
            "difficulty": scenario["difficulty"],
            "attack_types": scenario["attack_types"],
            "global_attack_ratio": scenario.get("global_attack_ratio", 0),
        })
    return result


def get_scenario(scenario_id):
    """Get a specific scenario profile by ID.

    Args:
        scenario_id: Scenario key (e.g. 'full_siege')

    Returns:
        Deep copy of the scenario dict

    Raises:
        ValueError: If scenario_id is not found
    """
    if scenario_id not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(f"Unknown scenario '{scenario_id}'. Available: {available}")
    return copy.deepcopy(SCENARIOS[scenario_id])


def get_apt_phase(round_num):
    """Get the APT campaign phase for a given round number.

    Args:
        round_num: Current FL round number

    Returns:
        Dict with phase info and per-client attack params, or None
    """
    apt = SCENARIOS["apt_campaign"]
    for phase in apt["phases"]:
        if round_num in phase["rounds"]:
            return copy.deepcopy(phase)
    return None


def create_custom_scenario(name, description, clients_config, difficulty="custom"):
    """Create a custom attack scenario at runtime.

    Args:
        name: Scenario name
        description: Description string
        clients_config: Dict of client_id -> {attack_ratio, attack_type}
        difficulty: Difficulty rating

    Returns:
        Scenario dict (not registered globally)
    """
    total_ratio = sum(c.get("attack_ratio", 0) for c in clients_config.values())
    avg_ratio = total_ratio / max(1, len(clients_config))
    attack_types = list(set(
        c["attack_type"] for c in clients_config.values()
        if c.get("attack_type")
    ))

    return {
        "name": name,
        "description": description,
        "difficulty": difficulty,
        "attack_types": attack_types,
        "global_attack_ratio": round(avg_ratio, 3),
        "duration_rounds": 1,
        "clients": copy.deepcopy(clients_config),
    }


def print_scenarios():
    """Pretty-print all available scenarios."""
    print("\n" + "=" * 70)
    print("ATTACK SCENARIOS")
    print("=" * 70)
    for key, s in SCENARIOS.items():
        n_targets = sum(1 for c in s.get("clients", {}).values()
                        if c.get("attack_ratio", 0) > 0)
        phases = len(s.get("phases", []))
        phase_info = f"  ({phases} phases)" if phases else ""
        print(f"\n  [{key}] {s['name']} ({s['difficulty']}){phase_info}")
        print(f"    {s['description']}")
        print(f"    Avg ratio: {s.get('global_attack_ratio', 0):.0%}  |  "
              f"Targets: {n_targets} clients  |  Types: {', '.join(s['attack_types'])}")
    print("=" * 70)


if __name__ == "__main__":
    print_scenarios()
