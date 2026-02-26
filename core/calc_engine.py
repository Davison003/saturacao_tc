from __future__ import annotations

from dataclasses import replace

import numpy as np

from .transformer_models import TransformerFactory
from .types import CTParams, SimulationParams, SimulationResult


def _resolve_dt(sim_params: SimulationParams) -> SimulationParams:
    if sim_params.dt is not None:
        return sim_params
    dt = 1.0 / (sim_params.frequency_hz * 200.0)
    return replace(sim_params, dt=dt)


def _compute_tsat(wave_t: np.ndarray, v_req_instant: np.ndarray, vsat: float) -> float:
    """
    Generic saturation time detector: first instant where Vreq exceeds Vsat.
    You can replace this with a different criterion later (e.g. based on
    i_ideal - i_real thresholds).
    """
    idx = np.where(v_req_instant > vsat)[0]
    if idx.size == 0:
        return float("inf")
    return float(wave_t[int(idx[0])])


def run_simulation(
    ct_params: CTParams,
    sim_params: SimulationParams,
    ct_type: str = "TPX",
) -> SimulationResult:
    sim_params = _resolve_dt(sim_params)

    transformer = TransformerFactory.create(ct_type, ct_params)

    vsat = transformer.calculate_saturation_voltage()
    waveforms = transformer.simulate_waveforms(sim_params)
    v_req_perm, v_req_trans = transformer.calculate_required_voltages(sim_params)

    saturated_perm = vsat < v_req_perm
    saturated_trans = vsat < v_req_trans

    tsat = (
        _compute_tsat(waveforms.t, waveforms.v_req_instant, vsat)
        if saturated_trans
        else float("inf")
    )

    return SimulationResult(
        ct_params=ct_params,
        sim_params=sim_params,
        waveforms=waveforms,
        vsat=float(vsat),
        v_req_perm=float(v_req_perm),
        v_req_trans=float(v_req_trans),
        tsat=float(tsat),
        saturated_perm=bool(saturated_perm),
        saturated_trans=bool(saturated_trans),
    )