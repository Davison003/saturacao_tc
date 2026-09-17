"""Regression tests against the default IEEE/PSRC CT SAT Calculator case.

The expected values below are cached values from the supplied calculator with
S=22, Vs=400 V, N=240, Rw=0 ohm, Rb=4 ohm, Xb=2 ohm, X/R=12,
Off=1, zero remanence, and Ip=12 kA RMS.
"""

from __future__ import annotations

import unittest

import numpy as np

from core.calc_engine import run_simulation
from core.transformer_models import FIXED_DT, TPXTransformer
from core.types import CTParams, SimulationParams


def reference_params() -> CTParams:
    """Return the spreadsheet's visible default input set."""
    return CTParams(
        ct_ratio=240.0,
        r_ct=0.0,
        r_b=4.0,
        i_sn=5.0,
        fault_current_rms=12000.0,
        i_cc_max=12000.0,
        x_r=12.0,
        distance_to_fault=1.0,
        cable_section_area=1.0,
        burden_reactance=2.0,
        dc_offset=1.0,
        remanence_pu=0.0,
        v_sat=400.0,
        s=22.0,
    )


class TPXReferenceModelTests(unittest.TestCase):
    """Ensure the discrete TPX implementation stays aligned to its source."""

    def test_reference_waveform_samples(self) -> None:
        waveforms = TPXTransformer(reference_params()).simulate_waveforms(
            SimulationParams(n_cycles=3)
        )

        # The first 200 samples are the spreadsheet's locked pre-fault history.
        index_at_3_333_ms = 200 + 40
        self.assertAlmostEqual(waveforms.t[index_at_3_333_ms], 0.003333333333333333, places=12)
        self.assertAlmostEqual(waveforms.i_ideal[index_at_3_333_ms], 41.8294945346, places=4)
        self.assertAlmostEqual(waveforms.i_real[index_at_3_333_ms], 41.8294945346, places=4)

        index_at_11_667_ms = 200 + 140
        self.assertAlmostEqual(waveforms.i_ideal[index_at_11_667_ms], 70.8632249186, places=4)
        self.assertAlmostEqual(waveforms.flux[index_at_11_667_ms], 1.5648937609, places=4)
        self.assertAlmostEqual(waveforms.i_real[index_at_11_667_ms], -1.9866102052, places=4)
        self.assertAlmostEqual(waveforms.i_ideal_rms[index_at_11_667_ms], 47.9270608880, places=4)
        self.assertAlmostEqual(waveforms.i_real_rms[index_at_11_667_ms], 26.0835167571, places=4)

    def test_fixed_grid_and_waveform_saturation_time(self) -> None:
        result = run_simulation(reference_params(), SimulationParams(n_cycles=3))
        self.assertEqual(len(result.waveforms.t), 800)
        self.assertAlmostEqual(result.waveforms.t[0], -1.0 / 60.0, places=12)
        self.assertTrue(np.isclose(result.sim_params.dt, FIXED_DT))
        self.assertTrue(result.saturated_waveform)
        # t_sat is the first current distortion larger than 0.5 A,
        # not the former flux-knee crossing criterion.
        self.assertAlmostEqual(result.tsat, 0.005583333333333333, places=8)

    def test_rejects_a_non_reference_time_step(self) -> None:
        with self.assertRaises(ValueError):
            TPXTransformer(reference_params()).simulate_waveforms(
                SimulationParams(n_cycles=1, dt=FIXED_DT / 2.0)
            )


if __name__ == "__main__":
    unittest.main()
