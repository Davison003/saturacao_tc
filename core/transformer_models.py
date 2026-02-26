from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Type

import numpy as np

from .types import CTParams, SimulationParams, Waveforms


class BaseTransformer(ABC):
    """
    Abstract base class for all CT transformer models.
    """

    def __init__(self, params: CTParams):
        self.params = params
        self._last_waveforms: Waveforms | None = None

    @abstractmethod
    def calculate_saturation_voltage(self) -> float:
        """
        Compute the CT saturation voltage according to its parameters.
        """

    @abstractmethod
    def simulate_waveforms(self, sim_params: SimulationParams) -> Waveforms:
        """
        Run the time-domain simulation and return all relevant waveforms.
        Implementations should also cache the result in self._last_waveforms.
        """

    def _ensure_waveforms(self, sim_params: SimulationParams) -> Waveforms:
        if self._last_waveforms is None:
            self._last_waveforms = self.simulate_waveforms(sim_params)
        return self._last_waveforms

    def calculate_required_voltages(
        self, sim_params: SimulationParams
    ) -> tuple[float, float]:
        """
        Default implementation: derive required voltages from the real secondary
        current using RMS values of the final and worst-case cycles.
        Subclasses may override for more specific behavior.
        """
        waveforms = self._ensure_waveforms(sim_params)
        i_real = waveforms.i_real

        ct = self.params
        r_total = ct.r_ct + ct.r_b

        # Determine samples per cycle
        if sim_params.dt is None:
            raise ValueError("SimulationParams.dt must be resolved before simulation.")

        samples_per_cycle = int(round(1.0 / (sim_params.frequency_hz * sim_params.dt)))
        if samples_per_cycle <= 0:
            raise ValueError("Invalid samples_per_cycle computed from dt and frequency.")

        n = len(i_real)
        if n < samples_per_cycle:
            raise ValueError("Not enough samples to compute at least one full cycle RMS.")

        # Sliding RMS over one cycle
        rms_values = []
        for end in range(samples_per_cycle, n + 1):
            window = i_real[end - samples_per_cycle : end]
            rms_values.append(float(np.sqrt(np.mean(window**2))))

        rms_values = np.array(rms_values)

        # Permanent: use the last available cycle RMS (steady state approximation)
        rms_perm = float(rms_values[-1])
        # Transient: use the maximum RMS across all cycles
        rms_trans = float(np.max(rms_values))

        v_req_perm = r_total * rms_perm
        v_req_trans = r_total * rms_trans
        return v_req_perm, v_req_trans


class TPXTransformer(BaseTransformer):
    """
    TPX-type CT transformer model.
    This class is intentionally structured to keep CT-specific physics isolated.

    Note: the numerical/physical equations should be implemented by you where
    marked below. The current implementation provides a runnable scaffold that
    returns correctly-shaped arrays for the UI/plots.
    """

    def calculate_saturation_voltage(self) -> float:
        # If a direct Vsat is provided, use it
        if self.params.v_sat is not None:
            return float(self.params.v_sat)

        ct = self.params
        v_sat = ct.k_h * ct.k_ssc * ct.k_td * (ct.r_ct + ct.r_b) * ct.i_sn
        return float(v_sat)

    def _compute_i_ideal(self, t: np.ndarray, sim_params: SimulationParams) -> np.ndarray:
        """
        TODO (physics): replace with the exact equation you want to use for
        i_s,ideal(t) for the TPX case (e.g. per your Eq. 18 / IEC formulation).
        """
        omega = 2.0 * np.pi * sim_params.frequency_hz
        ip = sim_params.ip_fault
        tp = sim_params.t_const_primary
        r_tc = self.params.ct_ratio
        return (np.sqrt(2.0) * ip / r_tc) * (np.exp(-t / tp) - np.cos(omega * t))

    def _update_flux(
        self,
        lambda_prev: float,
        i_ideal_k: float,
        i_exc_prev: float,
        dt: float,
    ) -> float:
        """
        TODO (physics): replace this with your discrete-time flux update, e.g.
        per the incremental formulation in your methodology (Eq. 21 / related).
        """
        s = self.params.s
        a = self.params.a
        denom = 1.0 + s * a * (abs(lambda_prev) ** (s - 1.0) if s != 1.0 else 1.0)
        d_lambda = (self.params.ct_ratio * (i_ideal_k - i_exc_prev) / denom) * dt
        return lambda_prev + d_lambda

    def _compute_excitation_current(self, lambda_k: float) -> float:
        """
        TODO (physics): replace with your magnetization curve i_e(lambda),
        e.g. per Eq. 17 (non-linear) and any TPX-specific adjustments.
        """
        s = self.params.s
        a = self.params.a
        if lambda_k == 0.0:
            return 0.0
        return float(a * (abs(lambda_k) ** s) * np.sign(lambda_k))

    def simulate_waveforms(self, sim_params: SimulationParams) -> Waveforms:
        ct = self.params

        # Resolve time step: if none, target ~200 samples per cycle
        if sim_params.dt is None:
            dt = 1.0 / (sim_params.frequency_hz * 200.0)
        else:
            dt = sim_params.dt

        total_time = sim_params.n_cycles / sim_params.frequency_hz
        n_samples = int(np.ceil(total_time / dt))

        t = np.linspace(0.0, total_time, n_samples, endpoint=False)

        i_ideal = self._compute_i_ideal(t, sim_params)

        # Allocate arrays
        flux = np.zeros_like(t)
        i_exc = np.zeros_like(t)
        i_real = np.zeros_like(t)

        for k in range(1, n_samples):
            # Previous state
            lam_prev = flux[k - 1]
            i_exc_prev = i_exc[k - 1]

            lam = self._update_flux(lam_prev, float(i_ideal[k]), float(i_exc_prev), dt)
            i_exc_k = self._compute_excitation_current(lam)

            i_s_real = i_ideal[k] - i_exc_k

            flux[k] = lam
            i_exc[k] = i_exc_k
            i_real[k] = i_s_real

        # Instantaneous required voltage (ohmic approximation)
        r_total = ct.r_ct + ct.r_b
        v_req_instant = r_total * np.abs(i_real)

        waveforms = Waveforms(
            t=t,
            i_ideal=i_ideal,
            i_real=i_real,
            i_excitation=i_exc,
            flux=flux,
            v_req_instant=v_req_instant,
        )

        self._last_waveforms = waveforms
        return waveforms


class TransformerFactory:
    """
    Simple registry-based factory for transformer models.
    """

    _registry: Dict[str, Type[BaseTransformer]] = {
        "TPX": TPXTransformer,
    }

    @classmethod
    def create(cls, ct_type: str, params: CTParams) -> BaseTransformer:
        try:
            transformer_cls = cls._registry[ct_type.upper()]
        except KeyError:
            raise ValueError(f"Unsupported CT type: {ct_type!r}")
        return transformer_cls(params)
