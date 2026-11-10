"""Ponto de entrada da interface gráfica."""
from __future__ import annotations

import sys


def main() -> int:
    import matplotlib
    matplotlib.use("QtAgg")
    from PySide6.QtWidgets import QApplication

    from .janela import JanelaPrincipal

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Framework LoRa")
    app.setOrganizationName("WissTek-IoT")
    app.setStyle("Fusion")
    janela = JanelaPrincipal()
    janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
