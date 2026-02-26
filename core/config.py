from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Tuple

from .types import CTParams, SimulationParams


def _default_config_path() -> Path:
    # config.json at project root (one level above core/)
    return Path(__file__).resolve().parents[1] / "config.json"


def load_config(path: str | Path | None = None) -> Dict[str, Any]:
    cfg_path = Path(path) if path is not None else _default_config_path()
    if not cfg_path.exists():
        return {"presets": {}}
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def save_config(config: Dict[str, Any], path: str | Path | None = None) -> None:
    cfg_path = Path(path) if path is not None else _default_config_path()
    cfg_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def list_presets(path: str | Path | None = None) -> list[str]:
    cfg = load_config(path)
    presets = cfg.get("presets", {})
    names = sorted(presets.keys())
    return names if names else ["Default_TPX"]


def load_preset(name: str, path: str | Path | None = None) -> Tuple[CTParams, SimulationParams]:
    cfg = load_config(path)
    presets = cfg.get("presets", {})

    if name not in presets:
        # Fallback hardcoded default
        return (
            CTParams(ct_ratio=3000.0, r_ct=0.5, r_b=1.0, i_sn=1.0),
            SimulationParams(frequency_hz=60.0, n_cycles=5, ip_fault=10000.0, t_const_primary=0.05),
        )

    blob = presets[name]
    ct_blob = blob.get("ct_params", {})
    sim_blob = blob.get("sim_params", {})

    ct = CTParams(**ct_blob)
    sim = SimulationParams(**sim_blob)
    return ct, sim


def save_preset(
    name: str,
    ct_params: CTParams,
    sim_params: SimulationParams,
    path: str | Path | None = None,
) -> None:
    cfg = load_config(path)
    cfg.setdefault("presets", {})
    cfg["presets"][name] = {
        "ct_params": asdict(ct_params),
        "sim_params": asdict(sim_params),
    }
    save_config(cfg, path)

