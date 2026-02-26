from __future__ import annotations

"""Compatibility layer for Qt bindings (PySide6/PyQt6/PyQt5)."""

from typing import Literal, Tuple


BindingName = Literal["PySide6", "PyQt6", "PyQt5"]


def _import_qt() -> Tuple[BindingName, object, object, object]:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

        return "PySide6", QtCore, QtGui, QtWidgets
    except ImportError:
        pass

    try:
        from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore

        return "PyQt6", QtCore, QtGui, QtWidgets
    except ImportError:
        pass

    try:
        from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore

        return "PyQt5", QtCore, QtGui, QtWidgets
    except ImportError:
        pass

    raise ModuleNotFoundError(
        "No Qt binding found. Install one of: PySide6, PyQt6, PyQt5."
    )


QT_BINDING, QtCore, QtGui, QtWidgets = _import_qt()

__all__ = ["QT_BINDING", "QtCore", "QtGui", "QtWidgets"]

