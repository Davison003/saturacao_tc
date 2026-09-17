"""Current comparison chart and its interactive numerical readout."""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from core.types import SimulationResult
from qt_compat import QtWidgets


class PlotWidget(QtWidgets.QWidget):
    """Show current waveforms and report all plotted values under the cursor."""

    def __init__(self, parent: Optional["QtWidgets.QWidget"] = None) -> None:
        super().__init__(parent)
        self._figure = Figure(constrained_layout=True, facecolor="#f4f7fb")
        self._canvas = FigureCanvas(self._figure)
        self._toolbar = NavigationToolbar(self._canvas, self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        self._axes = self._figure.subplots()
        self._time: Optional[np.ndarray] = None
        self._series: dict[str, np.ndarray] = {}
        self._annotation = None
        self._canvas.mpl_connect("motion_notify_event", self._on_hover)
        self._configure_axes()

    def _configure_axes(self) -> None:
        """Apply the shared visual treatment after an axes clear or rebuild."""
        self._axes.set_facecolor("#ffffff")
        self._axes.grid(True, color="#dbe4ee", alpha=0.9)
        for spine in self._axes.spines.values():
            spine.set_color("#cbd5e1")

    def _add_hover_annotation(self) -> None:
        """Create a compact tooltip updated to the sample nearest the cursor."""
        self._annotation = self._axes.annotate(
            "",
            xy=(0.0, 0.0),
            xytext=(12, 12),
            textcoords="offset points",
            fontsize=9,
            color="#ffffff",
            bbox={"boxstyle": "round,pad=0.4", "fc": "#173b61", "ec": "none", "alpha": 0.94},
        )
        self._annotation.set_visible(False)

    def _on_hover(self, event) -> None:
        """Show x and y values for every current trace at the nearest sample."""
        if event.inaxes is not self._axes or event.xdata is None or event.ydata is None or self._time is None:
            if self._annotation is not None and self._annotation.get_visible():
                self._annotation.set_visible(False)
                self._canvas.draw_idle()
            return

        index = int(np.clip(np.searchsorted(self._time, event.xdata), 0, len(self._time) - 1))
        if index > 0 and abs(self._time[index - 1] - event.xdata) < abs(self._time[index] - event.xdata):
            index -= 1
        values = "\n".join(f"{label}: {data[index]:.3f} A" for label, data in self._series.items())
        # Keep the tooltip inside the axes. A fixed offset on every edge can
        # move the mouse over/out of the canvas and cause a redraw flicker.
        bounds = self._axes.bbox
        x_offset = -220 if event.x > bounds.x1 - 220 else 12
        y_offset = -118 if event.y > bounds.y1 - 118 else 12
        self._annotation.set_position((x_offset, y_offset))
        self._annotation.xy = (float(self._time[index]), float(event.ydata))
        self._annotation.set_text(f"t: {self._time[index] * 1000:.3f} ms\n{values}")
        self._annotation.set_visible(True)
        self._canvas.draw_idle()

    def clear(self) -> None:
        self._figure.clear()
        self._axes = self._figure.subplots()
        self._time = None
        self._series = {}
        self._configure_axes()
        self._axes.set_title("Secondary current", loc="left", fontweight="bold", color="#143b63")
        self._axes.set_xlabel("Time [s]")
        self._axes.set_ylabel("Secondary current [A]")
        self._canvas.draw_idle()

    def plot_waveforms(self, result: SimulationResult) -> None:
        """Plot instantaneous and one-cycle DFT RMS secondary currents."""
        wf = result.waveforms
        self._axes.clear()
        self._configure_axes()
        self._time = wf.t
        self._series = {
            "Ideal current": wf.i_ideal,
            "CT current": wf.i_real,
            "Ideal DFT RMS": wf.i_ideal_rms,
            "CT DFT RMS": wf.i_real_rms,
        }
        self._axes.plot(wf.t, wf.i_ideal, color="#1769aa", linewidth=1.8, label="Ideal current")
        self._axes.plot(wf.t, wf.i_real, color="#d04a3a", linewidth=1.5, label="CT current")
        self._axes.plot(wf.t, wf.i_ideal_rms, color="#1769aa", linestyle="--", alpha=0.8,
                        linewidth=1.4, label="Ideal DFT RMS")
        self._axes.plot(wf.t, wf.i_real_rms, color="#d04a3a", linestyle="--", alpha=0.8,
                        linewidth=1.4, label="CT DFT RMS")
        self._axes.set_title("Secondary current", loc="left", fontweight="bold", color="#143b63")
        self._axes.set_xlabel("Time [s]")
        self._axes.set_ylabel("Secondary current [A]")
        self._axes.legend(loc="upper right", frameon=True)
        self._add_hover_annotation()
        self._canvas.draw_idle()
