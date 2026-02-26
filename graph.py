from __future__ import annotations

from typing import Optional

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget

from core.types import SimulationResult


class PlotWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._figure = Figure(constrained_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._toolbar = NavigationToolbar(self._canvas, self)

        layout = QVBoxLayout()
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        self.setLayout(layout)

        self._axes = self._figure.subplots(2, 2)

    def clear(self) -> None:
        self._figure.clear()
        self._axes = self._figure.subplots(2, 2)
        self._canvas.draw_idle()

    def plot_waveforms(self, result: SimulationResult) -> None:
        wf = result.waveforms
        t = wf.t

        ax00, ax01 = self._axes[0]
        ax10, ax11 = self._axes[1]

        ax00.clear()
        ax00.plot(t, wf.i_ideal, label="i_ideal")
        ax00.plot(t, wf.i_real, label="i_real")
        if result.tsat != float("inf"):
            ax00.axvline(result.tsat, linestyle="--", label="t_sat")
        ax00.set_title("Secondary current")
        ax00.set_xlabel("t [s]")
        ax00.set_ylabel("I [A]")
        ax00.grid(True, alpha=0.3)
        ax00.legend()

        ax01.clear()
        ax01.plot(t, wf.i_excitation, label="i_exc")
        ax01.set_title("Excitation current")
        ax01.set_xlabel("t [s]")
        ax01.set_ylabel("I [A]")
        ax01.grid(True, alpha=0.3)
        ax01.legend()

        ax10.clear()
        ax10.plot(t, wf.flux, label="lambda")
        ax10.set_title("Flux")
        ax10.set_xlabel("t [s]")
        ax10.set_ylabel("λ [Wb-turns?]")
        ax10.grid(True, alpha=0.3)
        ax10.legend()

        ax11.clear()
        ax11.plot(t, wf.v_req_instant, label="V_req(t)")
        ax11.axhline(result.vsat, linestyle="--", label="V_sat")
        ax11.set_title("Required voltage")
        ax11.set_xlabel("t [s]")
        ax11.set_ylabel("V [V]")
        ax11.grid(True, alpha=0.3)
        ax11.legend()

        self._canvas.draw_idle()
