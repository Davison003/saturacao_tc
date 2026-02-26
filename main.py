import sys

from PySide6.QtWidgets import QApplication

from app_ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
