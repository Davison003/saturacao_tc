"""CT model implementations.

The TPX implementation follows the IEEE/PSRC ``CT SAT Calculator`` recurrence.
The model is deliberately isolated here so new CT types can implement the same
interface without changing the user interface or calculation orchestrator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Type

import numpy as np

from .types import CTParams, SimulationParams, Waveforms


FIXED_FREQUENCY_HZ = 60.0
SAMPLES_PER_CYCLE = 200
FIXED_DT = 1.0 / (FIXED_FREQUENCY_HZ * SAMPLES_PER_CYCLE)
# The legacy calculator intentionally stores these rounded constants in its
# visible formulas. Keeping them preserves reproducible spreadsheet comparisons.
CALCULATOR_SQRT2_CURRENT = 1.41421
CALCULATOR_SQRT2_FLUX = 1.41428


class BaseTransformer(ABC):
    """Common contract for all current-transformer models."""

    def __init__(self, params: CTParams):
        self.params = params
        self._last_waveforms: Waveforms | None = None

    @abstractmethod
    def calculate_saturation_voltage(self) -> float:
        """Return the measured or calculated saturation voltage in volts RMS."""

    @abstractmethod
    def simulate_waveforms(self, sim_params: SimulationParams) -> Waveforms:
        """Run the model and return its secondary-current and flux waveforms."""

    def calculate_required_voltages(
        self, sim_params: SimulationParams
    ) -> tuple[float, float]:
        """Calculate the existing IEC permanent and transient voltage checks.

        These checks intentionally remain separate from the IEEE/PSRC waveform
        model. They retain the previous cable and IED resistance treatment.
        """
        rho_copper = 0.017  # copper resistivity [ohm mm^2/m]
        ct = self.params
        r_cable_1f = rho_copper * 2.0 * ct.distance_to_fault / ct.cable_section_area
        r_cable_3f = rho_copper * ct.distance_to_fault / ct.cable_section_area
        r_cable = r_cable_1f if sim_params.phase_mode.lower().startswith("mono") else r_cable_3f
        r_total = ct.r_ct + ct.r_ied + r_cable

        v_req_perm = (ct.i_cc_max / ct.ct_ratio) * r_total
        v_req_trans = v_req_perm * (1.0 + ct.x_r)
        return float(v_req_perm), float(v_req_trans)


class TPXTransformer(BaseTransformer):
    """TPX saturation model based on the IEEE/PSRC calculator.

    The model assumes a through-hole primary, no core losses, and a non-linear
    excitation curve ``i_exc = A sign(lambda) |lambda|^S``. The secondary
    circuit is driven by its total resistance and burden inductance, rather than
    by the current-ratio-only approximation used in the earlier scaffold.
    """

    def calculate_saturation_voltage(self) -> float:
        """Use a measured knee voltage when supplied, otherwise the IEC value."""
        ct = self.params
        if ct.v_sat is not None:
            return float(ct.v_sat)
        return float(ct.k_h * ct.k_ssc * ct.k_td * (ct.r_ct + ct.r_b) * ct.i_sn)

    @staticmethod
    def _validate_simulation(sim_params: SimulationParams) -> float:
        """Enforce the fixed numerical convention used by the reference model."""
        if sim_params.n_cycles < 1:
            raise ValueError("n_cycles must be at least one.")
        if not np.isclose(sim_params.frequency_hz, FIXED_FREQUENCY_HZ):
            raise ValueError("The TPX reference model is fixed at 60 Hz.")
        if sim_params.dt is not None and not np.isclose(sim_params.dt, FIXED_DT):
            raise ValueError(
                f"The TPX reference model requires dt={FIXED_DT:.12g} s "
                "(200 samples per 60 Hz cycle)."
            )
        return FIXED_DT

    def _validate_ct_params(self) -> None:
        ct = self.params
        if ct.ct_ratio <= 0.0 or ct.fault_current_rms < 0.0:
            raise ValueError("CT ratio must be positive and fault current cannot be negative.")
        if ct.r_ct + ct.r_b < 0.0 or ct.burden_reactance < 0.0:
            raise ValueError("Secondary burden resistance and reactance cannot be negative.")
        if ct.x_r <= 0.0 or ct.s <= 0.0:
            raise ValueError("X/R and the excitation-curve exponent S must be positive.")
        if not -1.0 <= ct.dc_offset <= 1.0:
            raise ValueError("dc_offset must be between -1 and 1.")
        if not -1.0 <= ct.remanence_pu <= 1.0:
            raise ValueError("remanence_pu must be between -1 and 1.")
        if self.calculate_saturation_voltage() <= 0.0:
            raise ValueError("The saturation voltage must be positive.")

    def _primary_time_constant(self) -> float:
        """Return Tau1 = (X/R) / omega, as used by the spreadsheet."""
        return self.params.x_r / (2.0 * np.pi * FIXED_FREQUENCY_HZ)

    def _compute_i_ideal(self, t: np.ndarray) -> np.ndarray:
        """Compute ideal secondary current for an asymmetrical primary fault.

        Before t=0 the reference calculator holds primary current at zero. For
        t>=0 it applies the calculator's ``Off`` magnitude and corresponding
        phase angle, so fully offset and partially offset faults are supported.
        """
        ct = self.params
        omega = 2.0 * np.pi * FIXED_FREQUENCY_HZ
        tau1 = self._primary_time_constant()
        phase_angle = np.arccos(ct.dc_offset)
        result = np.zeros_like(t)
        after_fault = t >= 0.0
        fault_t = t[after_fault]
        result[after_fault] = (
            CALCULATOR_SQRT2_CURRENT
            * (ct.fault_current_rms / ct.ct_ratio)
            * (
                ct.dc_offset * np.exp(-fault_t / tau1)
                - np.cos(omega * fault_t - phase_angle)
            )
        )
        return result

    def _compute_di_ideal_dt(self, t: np.ndarray) -> np.ndarray:
        """Return the ideal-secondary-current derivative used in the flux step."""
        ct = self.params
        omega = 2.0 * np.pi * FIXED_FREQUENCY_HZ
        tau1 = self._primary_time_constant()
        phase_angle = np.arccos(ct.dc_offset)
        result = np.zeros_like(t)
        after_fault = t >= 0.0
        fault_t = t[after_fault]
        result[after_fault] = (
            CALCULATOR_SQRT2_CURRENT
            * (ct.fault_current_rms / ct.ct_ratio)
            * (
                -ct.dc_offset / tau1 * np.exp(-fault_t / tau1)
                + omega * np.sin(omega * fault_t - phase_angle)
            )
        )
        return result

    def _calculate_rp(self) -> float:
        """Calculate the RMS-to-peak ratio using the calculator's 200-point rule."""
        # The spreadsheet integrates sin(theta)^(2S) over the first quadrant
        # with a trapezoidal rule. Symmetry makes this equal to the full-cycle
        # RMS-to-peak ratio while avoiding a SciPy dependency.
        theta = np.arange(0, 101, dtype=float) * np.pi / SAMPLES_PER_CYCLE
        values = np.sin(theta) ** (2.0 * self.params.s)
        trapezoid_sum = values[0] / 2.0 + np.sum(values[1:-1]) + values[-1] / 2.0
        return float(np.sqrt(trapezoid_sum / 100.0))

    def _calculate_excitation_coefficient(self) -> float:
        """Calibrate A so Vsat corresponds to 10 A RMS excitation current."""
        omega = 2.0 * np.pi * FIXED_FREQUENCY_HZ
        vsat = self.calculate_saturation_voltage()
        rp = self._calculate_rp()
        return float(10.0 * omega**self.params.s / ((np.sqrt(2.0) * vsat) ** self.params.s * rp))

    def _saturation_flux(self) -> float:
        """Peak flux linkage corresponding to the RMS saturation voltage."""
        return float(CALCULATOR_SQRT2_FLUX * self.calculate_saturation_voltage() / (2.0 * np.pi * FIXED_FREQUENCY_HZ))

    def _compute_excitation_current(self, flux: float, coefficient_a: float) -> float:
        """Evaluate the signed non-linear excitation-current curve at one flux."""
        if flux == 0.0:
            return 0.0
        return float(coefficient_a * np.sign(flux) * abs(flux) ** self.params.s)

    def _flux_increment(
        self,
        flux: float,
        i_ideal: float,
        di_ideal_dt: float,
        i_excitation: float,
        coefficient_a: float,
        dt: float,
    ) -> float:
        """Calculate one explicit IEEE/PSRC flux-linkage increment.

        ``Rt*i_ideal + Lb*di/dt - Rt*i_excitation`` is the secondary-circuit
        voltage that drives flux. The denominator is the differential slope of
        the non-linear excitation curve.
        """
        ct = self.params
        omega = 2.0 * np.pi * FIXED_FREQUENCY_HZ
        rt = ct.r_ct + ct.r_b
        lb = ct.burden_reactance / omega
        denominator = 1.0 + lb * ct.s * coefficient_a * abs(flux) ** (ct.s - 1.0)
        numerator = rt * i_ideal + lb * di_ideal_dt - rt * i_excitation
        return float(numerator / denominator * dt)

    @staticmethod
    def _fundamental_rms(current: np.ndarray, t: np.ndarray) -> np.ndarray:
        """Return the spreadsheet's one-cycle DFT fundamental-current magnitude."""
        omega = 2.0 * np.pi * FIXED_FREQUENCY_HZ
        sine_channel = current * np.sin(omega * t)
        cosine_channel = current * np.cos(omega * t)
        sine_sum = np.concatenate(([0.0], np.cumsum(sine_channel)))
        cosine_sum = np.concatenate(([0.0], np.cumsum(cosine_channel)))
        magnitude = np.zeros_like(current)

        # At every post-fault sample, the calculator projects the latest 200
        # samples onto sine and cosine bases, then converts peak to RMS.
        for end in range(len(current)):
            if t[end] < 0.0:
                continue
            start = max(0, end - SAMPLES_PER_CYCLE + 1)
            sin_component = sine_sum[end + 1] - sine_sum[start]
            cos_component = cosine_sum[end + 1] - cosine_sum[start]
            value = np.hypot(sin_component, cos_component) / (100.0 * CALCULATOR_SQRT2_CURRENT)
            magnitude[end] = 0.0 if value < 0.001 else value
        return magnitude

    def simulate_waveforms(self, sim_params: SimulationParams) -> Waveforms:
        """Simulate one pre-fault cycle and the requested post-fault cycles."""
        self._validate_ct_params()
        dt = self._validate_simulation(sim_params)
        post_fault_samples = sim_params.n_cycles * SAMPLES_PER_CYCLE
        sample_numbers = np.arange(-SAMPLES_PER_CYCLE, post_fault_samples, dtype=float)
        t = sample_numbers * dt

        i_ideal = self._compute_i_ideal(t)
        di_ideal_dt = self._compute_di_ideal_dt(t)
        coefficient_a = self._calculate_excitation_coefficient()

        flux = np.zeros_like(t)
        i_excitation = np.zeros_like(t)
        i_real = np.zeros_like(t)
        flux_increment = np.zeros_like(t)

        # The reference calculator locks remanent flux during its pre-fault
        # history and adds a tiny seed to avoid an exact zero-power corner case.
        flux[0] = self._saturation_flux() * self.params.remanence_pu + 0.0001
        i_excitation[0] = self._compute_excitation_current(flux[0], coefficient_a)
        i_real[0] = i_ideal[0] - i_excitation[0]

        for index in range(1, len(t)):
            if t[index] < 0.0:
                flux[index] = flux[index - 1]
            else:
                # Use the preceding state and increment, exactly as D261=D260+F260.
                flux[index] = flux[index - 1] + flux_increment[index - 1]

            i_excitation[index] = self._compute_excitation_current(flux[index], coefficient_a)
            i_real[index] = i_ideal[index] - i_excitation[index]
            flux_increment[index] = self._flux_increment(
                flux[index],
                i_ideal[index],
                di_ideal_dt[index],
                i_excitation[index],
                coefficient_a,
                dt,
            )

        i_ideal_rms = self._fundamental_rms(i_ideal, t)
        i_real_rms = self._fundamental_rms(i_real, t)

        # This is a plotting aid only. The IEC permanent/transient voltages are
        # calculated separately in BaseTransformer.calculate_required_voltages.
        v_req_instant = (self.params.r_ct + self.params.r_b) * np.abs(i_real)
        waveforms = Waveforms(
            t=t,
            i_ideal=i_ideal,
            i_real=i_real,
            i_ideal_rms=i_ideal_rms,
            i_real_rms=i_real_rms,
            i_excitation=i_excitation,
            flux=flux,
            v_req_instant=v_req_instant,
        )
        self._last_waveforms = waveforms
        return waveforms

    def saturation_flux(self) -> float:
        """Expose the knee-flux level for waveform-based saturation detection."""
        return self._saturation_flux()


class TransformerFactory:
    """Registry-based factory used to add future CT models without UI rewrites."""

    _registry: Dict[str, Type[BaseTransformer]] = {"TPX": TPXTransformer}

    @classmethod
    def register(cls, ct_type: str, transformer_cls: Type[BaseTransformer]) -> None:
        """Register a new model class, for example ``TransformerFactory.register``."""
        if not ct_type.strip():
            raise ValueError("CT type cannot be empty.")
        cls._registry[ct_type.upper()] = transformer_cls

    @classmethod
    def available_types(cls) -> tuple[str, ...]:
        """Return registered model names for UI selectors and saved studies."""
        return tuple(sorted(cls._registry))

    @classmethod
    def create(cls, ct_type: str, params: CTParams) -> BaseTransformer:
        try:
            transformer_cls = cls._registry[ct_type.upper()]
        except KeyError as exc:
            available = ", ".join(sorted(cls._registry))
            raise ValueError(f"Unsupported CT type {ct_type!r}. Available types: {available}.") from exc
        return transformer_cls(params)
