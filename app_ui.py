from __future__ import annotations

from typing import Optional

from qt_compat import QtCore, QtWidgets

from core.calc_engine import run_simulation
from core.config import list_presets, load_preset
from core.types import CTParams, SimulationParams
from graph import PlotWidget


def _float_box(
    *,
    min_value: float = 0.0,
    max_value: float = 1e9,
    decimals: int = 6,
    step: float = 0.1,
) -> QtWidgets.QDoubleSpinBox:
    box = QtWidgets.QDoubleSpinBox()
    box.setRange(min_value, max_value)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setKeyboardTracking(False)
    return box


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CT Saturation Simulator")

        self._plot = PlotWidget()

        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        left_panel.setLayout(left_layout)

        self._preset_combo = QtWidgets.QComboBox()
        self._preset_combo.addItems(list_presets())
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)

        preset_row = QtWidgets.QHBoxLayout()
        preset_row.addWidget(QtWidgets.QLabel("Preset"))
        preset_row.addWidget(self._preset_combo, 1)
        left_layout.addLayout(preset_row)

        self._ct_type = QtWidgets.QComboBox()
        self._ct_type.addItems(["TPX"])
        ct_type_row = QtWidgets.QHBoxLayout()
        ct_type_row.addWidget(QtWidgets.QLabel("CT type"))
        ct_type_row.addWidget(self._ct_type, 1)
        left_layout.addLayout(ct_type_row)

        self._ct_group = self._build_ct_group()
        self._sim_group = self._build_sim_group()
        left_layout.addWidget(self._ct_group)
        left_layout.addWidget(self._sim_group)

        buttons_row = QtWidgets.QHBoxLayout()
        self._btn_run = QtWidgets.QPushButton("Run simulation")
        self._btn_run.clicked.connect(self._run_clicked)
        self._btn_reset = QtWidgets.QPushButton("Reset")
        self._btn_reset.clicked.connect(self._reset_clicked)
        buttons_row.addWidget(self._btn_run)
        buttons_row.addWidget(self._btn_reset)
        left_layout.addLayout(buttons_row)

        self._out_vsat = QtWidgets.QLabel("-")
        self._out_vreq_perm = QtWidgets.QLabel("-")
        self._out_vreq_trans = QtWidgets.QLabel("-")
        self._out_tsat = QtWidgets.QLabel("-")
        self._out_sat_perm = QtWidgets.QLabel("-")
        self._out_sat_trans = QtWidgets.QLabel("-")

        out_group = QtWidgets.QGroupBox("Results")
        out_form = QtWidgets.QFormLayout()
        out_form.addRow("V_sat [V]", self._out_vsat)
        out_form.addRow("V_req_perm [V]", self._out_vreq_perm)
        out_form.addRow("V_req_trans [V]", self._out_vreq_trans)
        out_form.addRow("t_sat [s]", self._out_tsat)
        out_form.addRow("Saturates (perm)", self._out_sat_perm)
        out_form.addRow("Saturates (trans)", self._out_sat_trans)
        out_group.setLayout(out_form)
        left_layout.addWidget(out_group)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left_panel)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(scroll)
        splitter.addWidget(self._plot)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout()
        container_layout.addWidget(splitter)
        container.setLayout(container_layout)
        self.setCentralWidget(container)

        self._load_preset(self._preset_combo.currentText())

    def _build_ct_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("CT parameters")
        form = QtWidgets.QFormLayout()

        self._ct_ratio = _float_box(min_value=0.0001, step=1.0, decimals=6)
        self._r_ct = _float_box(min_value=0.0, step=0.01, decimals=6)
        self._r_b = _float_box(min_value=0.0, step=0.01, decimals=6)
        self._i_sn = _float_box(min_value=0.0001, step=0.1, decimals=6)

        self._k_h = _float_box(min_value=0.0, step=0.01, decimals=6)
        self._k_ssc = _float_box(min_value=0.0, step=0.01, decimals=6)
        self._k_td = _float_box(min_value=0.0, step=0.01, decimals=6)

        self._v_sat = _float_box(min_value=0.0, step=0.1, decimals=6)
        self._v_sat.setSpecialValueText("auto")
        self._v_sat.setValue(0.0)

        self._s = _float_box(min_value=0.1, step=0.1, decimals=6)
        self._a = _float_box(min_value=0.0, step=0.01, decimals=6)

        form.addRow("CT ratio (Np/Ns)", self._ct_ratio)
        form.addRow("R_ct [Ω]", self._r_ct)
        form.addRow("R_b [Ω]", self._r_b)
        form.addRow("I_sn [A]", self._i_sn)
        form.addRow("K_h [-]", self._k_h)
        form.addRow("K_ssc [-]", self._k_ssc)
        form.addRow("K_td [-]", self._k_td)
        form.addRow("V_sat [V] (0=auto)", self._v_sat)
        form.addRow("S [-]", self._s)
        form.addRow("A [-]", self._a)

        group.setLayout(form)
        return group

    def _build_sim_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Simulation parameters")
        form = QtWidgets.QFormLayout()

        self._freq = _float_box(min_value=1.0, step=1.0, decimals=3)
        self._n_cycles = QtWidgets.QSpinBox()
        self._n_cycles.setRange(1, 200)
        self._n_cycles.setSingleStep(1)

        self._ip_fault = _float_box(min_value=0.0, step=100.0, decimals=3)
        self._tp = _float_box(min_value=0.000001, step=0.001, decimals=6)

        self._dt = _float_box(min_value=0.0, step=1e-5, decimals=9)
        self._dt.setSpecialValueText("auto")
        self._dt.setValue(0.0)

        form.addRow("Frequency [Hz]", self._freq)
        form.addRow("Cycles [-]", self._n_cycles)
        form.addRow("I_p fault [A]", self._ip_fault)
        form.addRow("T_p [s]", self._tp)
        form.addRow("dt [s] (0=auto)", self._dt)

        group.setLayout(form)
        return group

    def _current_ct_params(self) -> CTParams:
        v_sat_value = float(self._v_sat.value())
        v_sat = None if v_sat_value == 0.0 else v_sat_value
        return CTParams(
            ct_ratio=float(self._ct_ratio.value()),
            r_ct=float(self._r_ct.value()),
            r_b=float(self._r_b.value()),
            i_sn=float(self._i_sn.value()),
            k_h=float(self._k_h.value()),
            k_ssc=float(self._k_ssc.value()),
            k_td=float(self._k_td.value()),
            v_sat=v_sat,
            s=float(self._s.value()),
            a=float(self._a.value()),
        )

    def _current_sim_params(self) -> SimulationParams:
        dt_value = float(self._dt.value())
        dt = None if dt_value == 0.0 else dt_value
        return SimulationParams(
            frequency_hz=float(self._freq.value()),
            n_cycles=int(self._n_cycles.value()),
            ip_fault=float(self._ip_fault.value()),
            t_const_primary=float(self._tp.value()),
            dt=dt,
        )

    def _run_clicked(self) -> None:
        try:
            ct_params = self._current_ct_params()
            sim_params = self._current_sim_params()
            ct_type = self._ct_type.currentText()

            result = run_simulation(ct_params, sim_params, ct_type=ct_type)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            QtWidgets.QMessageBox.critical(self, "Simulation error", str(exc))
            return

        self._out_vsat.setText(f"{result.vsat:.6g}")
        self._out_vreq_perm.setText(f"{result.v_req_perm:.6g}")
        self._out_vreq_trans.setText(f"{result.v_req_trans:.6g}")
        self._out_tsat.setText("inf" if result.tsat == float("inf") else f"{result.tsat:.6g}")
        self._out_sat_perm.setText("YES" if result.saturated_perm else "NO")
        self._out_sat_trans.setText("YES" if result.saturated_trans else "NO")

        self._plot.plot_waveforms(result)

    def _reset_clicked(self) -> None:
        self._load_preset(self._preset_combo.currentText())
        self._plot.clear()
        self._out_vsat.setText("-")
        self._out_vreq_perm.setText("-")
        self._out_vreq_trans.setText("-")
        self._out_tsat.setText("-")
        self._out_sat_perm.setText("-")
        self._out_sat_trans.setText("-")

    def _on_preset_changed(self, preset_name: str) -> None:
        self._load_preset(preset_name)

    def _load_preset(self, preset_name: str) -> None:
        ct_params, sim_params = load_preset(preset_name)

        self._ct_ratio.setValue(float(ct_params.ct_ratio))
        self._r_ct.setValue(float(ct_params.r_ct))
        self._r_b.setValue(float(ct_params.r_b))
        self._i_sn.setValue(float(ct_params.i_sn))
        self._k_h.setValue(float(ct_params.k_h))
        self._k_ssc.setValue(float(ct_params.k_ssc))
        self._k_td.setValue(float(ct_params.k_td))
        self._v_sat.setValue(0.0 if ct_params.v_sat is None else float(ct_params.v_sat))
        self._s.setValue(float(ct_params.s))
        self._a.setValue(float(ct_params.a))

        self._freq.setValue(float(sim_params.frequency_hz))
        self._n_cycles.setValue(int(sim_params.n_cycles))
        self._ip_fault.setValue(float(sim_params.ip_fault))
        self._tp.setValue(float(sim_params.t_const_primary))
        self._dt.setValue(0.0 if sim_params.dt is None else float(sim_params.dt))
