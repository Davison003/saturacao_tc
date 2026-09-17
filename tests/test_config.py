"""Configuration persistence and backward-compatibility tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.config import load_preset, save_preset
from core.types import CTParams, SimulationParams


class ConfigurationTests(unittest.TestCase):
    """Saved CT studies must round-trip without losing waveform inputs."""

    def test_round_trip_preserves_waveform_inputs(self) -> None:
        ct = CTParams(
            ct_ratio=600.0,
            r_ct=0.2,
            r_b=1.5,
            i_sn=5.0,
            fault_current_rms=18000.0,
            i_cc_max=22000.0,
            x_r=10.0,
            distance_to_fault=100.0,
            cable_section_area=4.0,
            rated_voltage_kv=138.0,
            burden_reactance=0.8,
            dc_offset=0.7,
            remanence_pu=0.2,
            v_sat=250.0,
            s=18.0,
        )
        simulation = SimulationParams(n_cycles=8, phase_mode="monophase")
        with patch("core.config.load_config", return_value={"presets": {}}), patch(
            "core.config.save_config"
        ) as save_config_mock:
            save_preset("saved-study", ct, simulation)

        saved_config = save_config_mock.call_args.args[0]
        saved_study = saved_config["presets"]["saved-study"]
        self.assertEqual(saved_study["ct_params"]["fault_current_rms"], 18000.0)
        self.assertEqual(saved_study["ct_params"]["burden_reactance"], 0.8)
        self.assertEqual(saved_study["ct_params"]["rated_voltage_kv"], 138.0)
        self.assertEqual(saved_study["sim_params"]["phase_mode"], "monophase")
        self.assertEqual(saved_study["ct_type"], "TPX")

    def test_legacy_i_p_is_migrated_to_fault_current(self) -> None:
        legacy = {
            "presets": {
                "legacy": {
                    "ct_params": {
                        "ct_ratio": 300.0,
                        "r_ct": 0.1,
                        "r_b": 1.0,
                        "i_sn": 5.0,
                        "i_p": 9000.0,
                    },
                    "sim_params": {"frequency_hz": 60.0, "n_cycles": 3},
                }
            }
        }
        with patch("core.config.load_config", return_value=legacy):
            ct, _, ct_type = load_preset("legacy")

        self.assertEqual(ct.fault_current_rms, 9000.0)
        self.assertEqual(ct.i_cc_max, 9000.0)
        self.assertEqual(ct_type, "TPX")
        self.assertEqual(ct.rated_voltage_kv, 0.0)
        self.assertEqual(ct.dc_offset, 1.0)
        self.assertEqual(ct.remanence_pu, 0.0)


if __name__ == "__main__":
    unittest.main()
