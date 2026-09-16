"""Qt user interface for the CT saturation study.

The window keeps source-model constants out of the editable controls: the
study always uses a fully offset fault (Off = 1) with zero remanence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from qt_compat import QtCore, QtGui, QtWidgets

from core.calc_engine import run_simulation
from core.config import list_presets, load_preset, save_preset
from core.transformer_models import TransformerFactory
from core.types import CTParams, SimulationParams
from graph import PlotWidget


def _validator_state(name: str):
    """Return a Qt validator state with PySide and PyQt compatibility."""
    state_enum = getattr(QtGui.QValidator, "State", QtGui.QValidator)
    return getattr(state_enum, name)


class FlexibleDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """A two-decimal field accepting either ``12.5`` or ``12,5``."""

    def validate(self, text: str, pos: int):  # type: ignore[override]
        stripped = text.strip()
        if stripped in {"", "-", "+", ".", ",", "-.", "-,", "+.", "+,"}:
            return _validator_state("Intermediate"), text, pos
        try:
            float(stripped.replace(",", "."))
        except ValueError:
            return _validator_state("Invalid"), text, pos
        return _validator_state("Acceptable"), text, pos

    def valueFromText(self, text: str) -> float:  # type: ignore[override]
        try:
            return float(text.strip().replace(",", "."))
        except ValueError:
            return self.value()


def _float_box(*, min_value: float = 0.0, max_value: float = 1e9, step: float = 0.1) -> FlexibleDoubleSpinBox:
    """Create a consistently formatted numeric input."""
    box = FlexibleDoubleSpinBox()
    box.setRange(min_value, max_value)
    box.setDecimals(2)
    box.setSingleStep(step)
    box.setKeyboardTracking(False)
    box.setMinimumWidth(132)
    return box


def _result_number(value: float) -> str:
    """Format outputs without implying more precision than the input allows."""
    return f"{value:,.2f}"


class MainWindow(QtWidgets.QMainWindow):
    """Main window and adapter between the visual controls and CT model."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CT Saturation Simulator")
        self.resize(1320, 820)
        self._apply_style()
        self._plot = PlotWidget()

        left_panel = QtWidgets.QWidget()
        left_panel.setObjectName("leftPanel")
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        left_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        title = QtWidgets.QLabel("Current transformer saturation")
        title.setObjectName("pageTitle")
        subtitle = QtWidgets.QLabel("IEEE/PSRC TPX waveform model · 60 Hz · 83.33 µs time step")
        subtitle.setObjectName("subtitle")
        title_column = QtWidgets.QVBoxLayout()
        title_column.setSpacing(2)
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        header = QtWidgets.QHBoxLayout()
        header.addLayout(title_column, 1)
        logo = QtWidgets.QLabel()
        logo.setObjectName("appLogo")
        logo_path = Path(__file__).resolve().parent / "assets" / "logo.png"
        pixmap = QtGui.QPixmap(str(logo_path))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToHeight(54, QtCore.Qt.TransformationMode.SmoothTransformation))
        logo.setToolTip("CT Saturation Simulator")
        header.addWidget(logo)
        left_layout.addLayout(header)
        left_layout.addWidget(self._build_study_group())
        left_layout.addWidget(self._build_ct_inputs())
        left_layout.addWidget(self._build_sim_group())
        left_layout.addLayout(self._build_buttons())
        left_layout.addWidget(self._build_results_group())
        left_layout.addStretch(1)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        # The form is sized to the splitter; never introduce a second
        # horizontal scrollbar just because a translated label is wide.
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(left_panel)
        scroll.setMinimumWidth(390)
        splitter = QtWidgets.QSplitter()
        splitter.addWidget(scroll)
        splitter.addWidget(self._plot)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 890])
        self.setCentralWidget(splitter)
        self._load_preset(self._preset_combo.currentText())

    def _apply_style(self) -> None:
        """Use a calm, high-contrast layout to separate inputs from results."""
        self.setStyleSheet("""
            QMainWindow { background: #f4f7fb; color: #1f2937; }
            #leftPanel { background: #ffffff; }
            QLabel#pageTitle { font-size: 20px; font-weight: 700; color: #143b63; }
            QLabel#subtitle { color: #64748b; padding-bottom: 4px; }
            QGroupBox { border: 1px solid #d8e0eb; border-radius: 8px; margin-top: 10px;
                        padding: 9px 8px 7px 8px; font-weight: 600; color: #264b70; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QDoubleSpinBox, QSpinBox, QComboBox { min-height: 26px; border: 1px solid #cbd5e1;
                        border-radius: 5px; padding: 0 7px; background: #ffffff; }
            QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus { border: 2px solid #4f8ac9; }
            QPushButton { min-height: 30px; border: 0; border-radius: 6px; padding: 0 10px;
                        background: #e6edf5; color: #173b61; font-weight: 600; }
            QPushButton#runButton { background: #1769aa; color: white; }
            QPushButton:hover { background: #d4e2f0; }
            QPushButton#runButton:hover { background: #0d568f; }
            QGroupBox#resultsGroup QLabel { font-size: 15px; }
            QLabel#voltageStatus { border-radius: 7px; padding: 10px; font-weight: 700; font-size: 16px; }
        """)

    def _build_study_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Study")
        form = QtWidgets.QFormLayout(group)
        self._preset_combo = QtWidgets.QComboBox()
        self._preset_combo.addItems(list_presets())
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self._ct_type = QtWidgets.QComboBox()
        self._ct_type.addItems(TransformerFactory.available_types())
        form.addRow("Configuration", self._preset_combo)
        form.addRow("CT model", self._ct_type)
        return group

    def _build_ct_inputs(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("CT and fault inputs")
        form = QtWidgets.QFormLayout(group)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self._rated_voltage_kv = _float_box(step=1.0)
        self._ct_ratio = _float_box(min_value=0.01, step=1.0)
        self._i_sn = _float_box(min_value=0.01, step=1.0)
        self._r_ct = _float_box(step=0.01)
        self._r_b = _float_box(step=0.01)
        self._burden_reactance = _float_box(step=0.01)
        self._i_p_fault = _float_box(min_value=0.01, step=100.0)
        self._i_cc_max = _float_box(min_value=0.01, step=100.0)
        self._x_r = _float_box(min_value=0.01, step=0.1)
        self._v_sat = _float_box(step=1.0)
        self._v_sat.setSpecialValueText("Automatic")
        self._s = _float_box(min_value=0.1, step=1.0)
        self._distance_fault = _float_box(min_value=0.1, step=10.0)
        self._cable_section_area = _float_box(min_value=0.1, step=1.0)
        self._k_h = _float_box(step=0.01)
        self._k_ssc = _float_box(step=0.01)
        self._k_td = _float_box(step=0.01)
        form.addRow("Rated system voltage [kV]", self._rated_voltage_kv)
        form.addRow("CT ratio Np/Ns [A/A]", self._ct_ratio)
        form.addRow("Nominal secondary current [A]", self._i_sn)
        form.addRow("CT winding resistance Rct [Ω]", self._r_ct)
        form.addRow("Burden resistance Rb [Ω]", self._r_b)
        form.addRow("Burden reactance Xb [Ω]", self._burden_reactance)
        form.addRow("Fault current Ifault,rms [A]", self._i_p_fault)
        form.addRow("Maximum fault current Icc,max [A]", self._i_cc_max)
        form.addRow("System X/R [-]", self._x_r)
        form.addRow("Saturation voltage Vsat [V]", self._v_sat)
        form.addRow("Excitation exponent S [-]", self._s)
        form.addRow("Cable length, one way [m]", self._distance_fault)
        form.addRow("Cable cross-section [mm²]", self._cable_section_area)
        form.addRow("Height factor Kh [-]", self._k_h)
        form.addRow("Short-circuit factor Kssc [-]", self._k_ssc)
        form.addRow("Transient factor Ktd [-]", self._k_td)
        return group

    def _build_sim_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Simulation")
        form = QtWidgets.QFormLayout(group)
        self._n_cycles = QtWidgets.QSpinBox()
        self._n_cycles.setRange(1, 200)
        self._n_cycles.setValue(5)
        self._phase_combo = QtWidgets.QComboBox()
        self._phase_combo.addItems(["Three-phase fault", "Single-phase fault"])
        form.addRow("Reference frequency", QtWidgets.QLabel("60 Hz (fixed)"))
        form.addRow("Time step", QtWidgets.QLabel("83.33 µs (fixed)"))
        form.addRow("Post-fault cycles", self._n_cycles)
        form.addRow("Fault type", self._phase_combo)
        return group

    def _build_buttons(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        self._btn_run = QtWidgets.QPushButton("Run simulation")
        self._btn_run.setObjectName("runButton")
        self._btn_run.clicked.connect(self._run_clicked)
        self._btn_reset = QtWidgets.QPushButton("Reset")
        self._btn_reset.clicked.connect(self._reset_clicked)
        self._btn_save = QtWidgets.QPushButton("Save configuration")
        self._btn_save.clicked.connect(self._save_clicked)
        row.addWidget(self._btn_run, 2)
        row.addWidget(self._btn_reset)
        row.addWidget(self._btn_save)
        return row

    def _build_results_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Results")
        group.setObjectName("resultsGroup")
        layout = QtWidgets.QVBoxLayout(group)
        self._out_voltage_status = QtWidgets.QLabel("Run a simulation to check voltage saturation")
        self._out_voltage_status.setObjectName("voltageStatus")
        self._out_voltage_status.setWordWrap(True)
        layout.addWidget(self._out_voltage_status)
        form = QtWidgets.QFormLayout()
        self._out_vsat = QtWidgets.QLabel("–")
        self._out_vreq_perm = QtWidgets.QLabel("–")
        self._out_vreq_trans = QtWidgets.QLabel("–")
        self._out_tsat = QtWidgets.QLabel("–")
        self._out_waveform_status = QtWidgets.QLabel("–")
        form.addRow("CT saturation voltage", self._out_vsat)
        form.addRow("Required permanent voltage", self._out_vreq_perm)
        form.addRow("Required transient voltage", self._out_vreq_trans)
        form.addRow("Time to Saturation", self._out_tsat)
        form.addRow("CT current differs from ideal", self._out_waveform_status)
        layout.addLayout(form)
        return group

    def _current_ct_params(self) -> CTParams:
        """Create model data while enforcing the fixed visible assumptions."""
        v_sat_value = float(self._v_sat.value())
        return CTParams(ct_ratio=float(self._ct_ratio.value()), r_ct=float(self._r_ct.value()),
            r_b=float(self._r_b.value()), i_sn=float(self._i_sn.value()),
            fault_current_rms=float(self._i_p_fault.value()), i_cc_max=float(self._i_cc_max.value()),
            x_r=float(self._x_r.value()), distance_to_fault=float(self._distance_fault.value()),
            cable_section_area=float(self._cable_section_area.value()), rated_voltage_kv=float(self._rated_voltage_kv.value()),
            burden_reactance=float(self._burden_reactance.value()), dc_offset=1.0, remanence_pu=0.0,
            k_h=float(self._k_h.value()), k_ssc=float(self._k_ssc.value()), k_td=float(self._k_td.value()),
            v_sat=None if v_sat_value == 0.0 else v_sat_value, s=float(self._s.value()))

    def _current_sim_params(self) -> SimulationParams:
        phase_mode = "triphase" if self._phase_combo.currentIndex() == 0 else "monophase"
        return SimulationParams(n_cycles=int(self._n_cycles.value()), phase_mode=phase_mode)

    def _run_clicked(self) -> None:
        try:
            result = run_simulation(self._current_ct_params(), self._current_sim_params(), self._ct_type.currentText())
        except Exception as exc:  # pylint: disable=broad-exception-caught
            QtWidgets.QMessageBox.critical(self, "Simulation error", str(exc))
            return
        self._out_vsat.setText(f"{_result_number(result.vsat)} V")
        self._out_vreq_perm.setText(f"{_result_number(result.v_req_perm)} V")
        self._out_vreq_trans.setText(f"{_result_number(result.v_req_trans)} V")
        self._out_tsat.setText("No saturation detected" if result.tsat == float("inf") else f"{result.tsat * 1000:.2f} ms")
        self._out_waveform_status.setText("Yes" if result.saturated_waveform else "No")
        # A voltage saturation warning is positive if either IEC check fails.
        # The individual permanent and transient requirements remain visible
        # below, so the compact status never hides the governing comparison.
        if result.saturated_perm or result.saturated_trans:
            flags = []
            if result.saturated_perm:
                flags.append(f"permanent {_result_number(result.v_req_perm)} V")
            if result.saturated_trans:
                flags.append(f"transient {_result_number(result.v_req_trans)} V")
            self._out_voltage_status.setText(
                "VOLTAGE SATURATION: YES (" + "; ".join(flags) + ")"
            )
            self._out_voltage_status.setStyleSheet("background: #fee2e2; color: #a11d2e;")
        else:
            self._out_voltage_status.setText("VOLTAGE SATURATION: NO")
            self._out_voltage_status.setStyleSheet("background: #dcfce7; color: #166534;")
        self._plot.plot_waveforms(result)

    def _clear_results(self) -> None:
        for widget in (self._out_vsat, self._out_vreq_perm, self._out_vreq_trans, self._out_tsat, self._out_waveform_status):
            widget.setText("–")
        self._out_voltage_status.setText("Run a simulation to check voltage saturation")
        self._out_voltage_status.setStyleSheet("background: #eaf0f6; color: #475569;")

    def _reset_clicked(self) -> None:
        self._load_preset(self._preset_combo.currentText())
        self._plot.clear()
        self._clear_results()

    def _save_clicked(self) -> None:
        name, accepted = QtWidgets.QInputDialog.getText(self, "Save configuration", "Configuration name:")
        name = name.strip()
        if not accepted or not name:
            return
        try:
            save_preset(name, self._current_ct_params(), self._current_sim_params(), self._ct_type.currentText())
        except Exception as exc:  # pylint: disable=broad-exception-caught
            QtWidgets.QMessageBox.critical(self, "Save error", str(exc))
            return
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItems(list_presets())
        self._preset_combo.setCurrentText(name)
        self._preset_combo.blockSignals(False)

    def _on_preset_changed(self, preset_name: str) -> None:
        self._load_preset(preset_name)

    def _load_preset(self, preset_name: str) -> None:
        ct, sim, ct_type = load_preset(preset_name)
        if self._ct_type.findText(ct_type) >= 0:
            self._ct_type.setCurrentText(ct_type)
        self._rated_voltage_kv.setValue(float(ct.rated_voltage_kv))
        self._ct_ratio.setValue(float(ct.ct_ratio)); self._r_ct.setValue(float(ct.r_ct)); self._r_b.setValue(float(ct.r_b))
        self._burden_reactance.setValue(float(ct.burden_reactance)); self._i_sn.setValue(float(ct.i_sn))
        self._i_p_fault.setValue(float(ct.fault_current_rms)); self._i_cc_max.setValue(float(ct.i_cc_max)); self._x_r.setValue(float(ct.x_r))
        self._k_h.setValue(float(ct.k_h)); self._k_ssc.setValue(float(ct.k_ssc)); self._k_td.setValue(float(ct.k_td))
        self._v_sat.setValue(0.0 if ct.v_sat is None else float(ct.v_sat)); self._s.setValue(float(ct.s))
        self._distance_fault.setValue(float(ct.distance_to_fault)); self._cable_section_area.setValue(float(ct.cable_section_area))
        self._n_cycles.setValue(int(sim.n_cycles))
        self._phase_combo.setCurrentIndex(1 if sim.phase_mode.lower().startswith("mono") else 0)
