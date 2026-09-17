"""High-level simulation orchestration and result summaries."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from .transformer_models import FIXED_DT, TPXTransformer, TransformerFactory
from .types import CTParams, SimulationParams, SimulationResult


# Small numerical residues are not useful as a protection result. The selected
# half-ampere threshold makes ``Time to Saturation`` represent visible current
# distortion in the plotted waveform.
CURRENT_DIVERGENCE_TOLERANCE_A = 0.5


def _resolve_dt(sim_params: SimulationParams) -> SimulationParams:
    """Persist the fixed reference-calculator time step in returned results."""
    return replace(sim_params, dt=FIXED_DT)


def _compute_waveform_tsat(
    time: np.ndarray, ideal_current: np.ndarray, real_current: np.ndarray
) -> float:
    """Return the first post-fault instant where CT current is distorted.

    Saturation is presented as a waveform event: the first sample where the
    simulated secondary current materially differs from the ideal secondary
    current. The 0.5 A tolerance prevents insignificant early numerical
    residue from producing a misleading saturation time.
    """
    saturated = np.flatnonzero(
        (time >= 0.0)
        & (np.abs(ideal_current - real_current) > CURRENT_DIVERGENCE_TOLERANCE_A)
    )
    if saturated.size == 0:
        return float("inf")
    return float(time[int(saturated[0])])


def run_simulation(
    ct_params: CTParams,
    sim_params: SimulationParams,
    ct_type: str = "TPX",
) -> SimulationResult:
    """Run one CT model and assemble voltage and waveform summaries."""
    sim_params = _resolve_dt(sim_params)
    transformer = TransformerFactory.create(ct_type, ct_params)

    vsat = transformer.calculate_saturation_voltage()
    waveforms = transformer.simulate_waveforms(sim_params)
    v_req_perm, v_req_trans = transformer.calculate_required_voltages(sim_params)
    saturated_perm = vsat < v_req_perm
    saturated_trans = vsat < v_req_trans

    # A non-TPX class can later expose its own waveform-distortion criterion.
    if isinstance(transformer, TPXTransformer):
        tsat = _compute_waveform_tsat(waveforms.t, waveforms.i_ideal, waveforms.i_real)
    else:
        tsat = float("inf")

    return SimulationResult(
        ct_params=ct_params,
        sim_params=sim_params,
        waveforms=waveforms,
        vsat=float(vsat),
        v_req_perm=float(v_req_perm),
        v_req_trans=float(v_req_trans),
        tsat=tsat,
        saturated_perm=bool(saturated_perm),
        saturated_trans=bool(saturated_trans),
        saturated_waveform=bool(np.isfinite(tsat)),
    )
