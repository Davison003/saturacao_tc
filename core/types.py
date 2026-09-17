"""Typed data exchanged by the CT simulator layers.

Keeping inputs, waveforms, and results in small data objects makes individual CT
models independent from the Qt interface. A future TPY/TPZ implementation can
reuse these objects and add a model-specific parameter object when needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class CTParams:
    """Electrical and magnetic data for a protection current transformer.

    ``r_b`` and ``burden_reactance`` are the resistance and reactance seen at
    the CT secondary by the *waveform* model. They correspond to ``Rb`` and
    ``Xb`` in the IEEE/PSRC CT saturation calculator. Cable and IED fields are
    retained for the existing IEC voltage checks, which use a separate burden
    calculation.
    """

    ct_ratio: float  # primary-to-secondary turns/current ratio N [A/A]
    r_ct: float  # secondary winding resistance Rw [ohm]
    r_b: float  # secondary burden resistance Rb [ohm]
    i_sn: float  # nominal secondary current [A], normally 1 A or 5 A

    # Fault values. Waveforms use fault_current_rms; IEC voltage checks retain
    # i_cc_max because it can represent a different maximum fault study value.
    fault_current_rms: float  # symmetrical primary fault current Ip [A rms]
    i_cc_max: float  # maximum primary short-circuit current [A rms]
    x_r: float  # primary-system X/R ratio [-]

    # Installation values used by the unchanged IEC voltage calculations.
    distance_to_fault: float  # one-way secondary cable distance [m]
    cable_section_area: float  # secondary cable cross-sectional area [mm^2]
    # Nameplate system voltage. It identifies the installation but deliberately
    # does not affect either saturation calculation.
    rated_voltage_kv: float = 0.0
    r_ied: float = 0.01  # relay input-channel resistance [ohm]

    # IEEE/PSRC waveform-model inputs.
    burden_reactance: float = 0.0  # secondary burden reactance Xb [ohm]
    dc_offset: float = 1.0  # per-unit asymmetrical-fault offset, -1 <= Off <= 1
    remanence_pu: float = 0.0  # residual flux / saturation flux at fault inception

    # IEC saturation-voltage inputs. A measured direct value overrides these.
    k_h: float = 1.0
    k_ssc: float = 1.0
    k_td: float = 1.0
    v_sat: Optional[float] = None  # measured knee/saturation voltage [V rms]

    # Exponent S in i_exc = A * sign(lambda) * |lambda|^S. It is called the
    # inverse saturation-curve slope in the original IEEE calculator.
    s: float = 2.0


@dataclass
class SimulationParams:
    """Fixed numerical convention and selected fault configuration.

    The reference calculator uses 60 Hz and 12,000 samples/s, i.e. 200 samples
    per fundamental cycle. ``dt`` is kept only to make saved configurations
    explicit; the engine validates that it has this fixed value.
    """

    n_cycles: int = 5  # post-fault cycles to simulate
    frequency_hz: float = 60.0
    phase_mode: str = "triphase"
    dt: Optional[float] = None


@dataclass
class Waveforms:
    """Time-domain outputs of a CT model, all sampled on the same time grid."""

    t: np.ndarray
    i_ideal: np.ndarray
    i_real: np.ndarray
    # One-cycle DFT magnitudes: fundamental-frequency RMS currents, not total
    # waveform RMS. This exactly matches the reference calculator display.
    i_ideal_rms: np.ndarray
    i_real_rms: np.ndarray
    i_excitation: np.ndarray
    flux: np.ndarray
    v_req_instant: np.ndarray


@dataclass
class SimulationResult:
    """A complete simulation result plus voltage- and waveform-based summaries."""

    ct_params: CTParams
    sim_params: SimulationParams
    waveforms: Waveforms

    vsat: float
    v_req_perm: float
    v_req_trans: float

    # First post-fault time where the real secondary current materially differs
    # from the ideal current. Infinity means no waveform distortion occurred.
    tsat: float
    saturated_perm: bool
    saturated_trans: bool
    saturated_waveform: bool
