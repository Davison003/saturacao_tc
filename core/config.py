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


def load_preset(
    name: str, path: str | Path | None = None
) -> Tuple[CTParams, SimulationParams, str]:
    cfg = load_config(path)
    presets = cfg.get("presets", {})

    if name not in presets:
        # Fallback mirrors the public TPX case used by the application.
        return (
            CTParams(
                ct_ratio=3000.0,
                r_ct=13.85,
                r_b=5.0,
                i_sn=1.0,
                fault_current_rms=28100.0,
                i_cc_max=28100.0,
                x_r=11.77,
                distance_to_fault=200.0,
                cable_section_area=6.0,
                burden_reactance=0.0,
            ),
            SimulationParams(n_cycles=5),
            "TPX",
        )

    blob = presets[name]
    ct_blob = dict(blob.get("ct_params", {}))
    sim_blob = dict(blob.get("sim_params", {}))

    # Version-1 configurations named the waveform fault current ``i_p``.
    # Accept them on load, but save only the unambiguous newer field.
    if "fault_current_rms" not in ct_blob:
        ct_blob["fault_current_rms"] = ct_blob.pop(
            "i_p", ct_blob.get("i_cc_max", 0.0)
        )

    # Fill fields absent from early presets so old saved studies still open.
    ct_blob.setdefault("i_cc_max", ct_blob["fault_current_rms"])
    ct_blob.setdefault("x_r", 1.0)
    ct_blob.setdefault("distance_to_fault", 1.0)
    ct_blob.setdefault("cable_section_area", 1.0)
    ct_blob.setdefault("rated_voltage_kv", 0.0)
    ct_blob.setdefault("burden_reactance", 0.0)
    # The simplified application deliberately fixes these source-calculator
    # assumptions. Old presets may contain editable values, but loading them
    # must not quietly create a different fault case from the visible UI.
    ct_blob["dc_offset"] = 1.0
    ct_blob["remanence_pu"] = 0.0
    sim_blob.pop("t_const_primary", None)
    sim_blob.pop("ip_fault", None)

    ct = CTParams(**ct_blob)
    sim = SimulationParams(**sim_blob)
    ct_type = str(blob.get("ct_type", "TPX")).upper()
    return ct, sim, ct_type


def save_preset(
    name: str,
    ct_params: CTParams,
    sim_params: SimulationParams,
    ct_type: str = "TPX",
    path: str | Path | None = None,
) -> None:
    cfg = load_config(path)
    cfg.setdefault("presets", {})
    cfg["presets"][name] = {
        "ct_type": ct_type.upper(),
        "ct_params": asdict(ct_params),
        "sim_params": asdict(sim_params),
    }
    save_config(cfg, path)

