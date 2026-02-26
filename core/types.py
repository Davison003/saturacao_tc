from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class CTParams:
    """
    Parameters that characterize a current transformer (CT).
    All units are in SI (A, V, Ω, s, Hz).
    """

    ct_ratio: float  # primary_nominal / secondary_nominal (e.g. 3000 for 3000/1 A)
    r_ct: float  # secondary winding resistance [Ω]
    r_b: float  # burden resistance [Ω]
    i_sn: float  # nominal secondary current [A] (typically 1 or 5 A)

    # IEC-based saturation factors
    k_h: float = 1.0
    k_ssc: float = 1.0
    k_td: float = 1.0

    # Optional direct saturation voltage [V]; if None it is computed from IEC formula
    v_sat: Optional[float] = None

    # Non-linear magnetization curve parameters (i_e ≈ A * |λ|^S * sign(λ))
    s: float = 2.0
    a: float = 1.0


@dataclass
class SimulationParams:
    """
    Numerical simulation settings and fault scenario data.
    """

    frequency_hz: float  # system frequency [Hz]
    n_cycles: int  # number of fundamental cycles to simulate
    ip_fault: float  # primary fault current amplitude [A]
    t_const_primary: float  # primary time constant T_p [s]

    # Time step [s]. If None, the engine can choose (e.g. 200 samples/cycle).
    dt: Optional[float] = None


@dataclass
class Waveforms:
    """
    Time-domain signals produced by the simulation.
    All arrays are NumPy arrays with the same length.
    """

    t: np.ndarray
    i_ideal: np.ndarray
    i_real: np.ndarray
    i_excitation: np.ndarray
    flux: np.ndarray
    v_req_instant: np.ndarray


@dataclass
class SimulationResult:
    """
    Aggregate result object returned by the calculation engine.
    It contains both time-series and scalar summary values.
    """

    ct_params: CTParams
    sim_params: SimulationParams
    waveforms: Waveforms

    vsat: float
    v_req_perm: float
    v_req_trans: float

    # Saturation information
    tsat: float  # time to saturation [s]; float('inf') if not saturated
    saturated_perm: bool
    saturated_trans: bool

