"""Componentes compartilhados da interface: contexto, gráficos, tabelas e monitor de logs."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHeaderView,
                               QLabel, QMessageBox, QSpinBox, QTableView, QVBoxLayout, QWidget)

from ..core import survey


def raiz_padrao() -> Path:
    """Pasta de trabalho inicial: a do .exe quando empacotado, senão a pasta atual."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


# ---------------------------------------------------------------- monitor de log do gateway
class MonitorLog(QObject):
    """Acompanha o log mais recente do gateway (ou um arquivo fixo) e emite os dados novos."""

    atualizado = Signal(object, object)   # (DataFrame, Path)
    erro = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pasta: Path | None = None
        self.arquivo_fixo: Path | None = None
        self.padrao = "log"
        self.caminho: Path | None = None
        self.df: pd.DataFrame = pd.DataFrame(columns=survey.COLUNAS)
        self._assinatura = None
        self._ultimo_erro = None
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.verificar)

    @property
    def ativo(self) -> bool:
        return self.timer.isActive()

    def configurar(self, pasta: Path | None = None, arquivo: Path | None = None, padrao: str | None = None):
        self.pasta = Path(pasta) if pasta else None
        self.arquivo_fixo = Path(arquivo) if arquivo else None
        if padrao is not None:
            self.padrao = padrao
        self._assinatura = None

    def iniciar(self):
        self.timer.start()
        self.verificar()

    def parar(self):
        self.timer.stop()

    def alvo(self) -> Path | None:
        if self.arquivo_fixo:
            return self.arquivo_fixo if self.arquivo_fixo.exists() else None
        if self.pasta:
            return survey.log_mais_recente(self.pasta, self.padrao)
        return None

    def verificar(self, forcar: bool = False):
        caminho = self.alvo()
        if caminho is None:
            return
        try:
            st = caminho.stat()
        except OSError:
            return
        assinatura = (str(caminho), st.st_size, st.st_mtime_ns)
        if assinatura == self._assinatura and not forcar:
            return
        try:
            df = survey.ler_log(caminho)
        except Exception as e:  # arquivo sendo escrito, vazio ou formato desconhecido
            msg = f"Não foi possível ler {caminho.name}: {e}"
            if msg != self._ultimo_erro:
                self._ultimo_erro = msg
                self.erro.emit(msg)
            self._assinatura = assinatura
            return
        self._ultimo_erro = None
        self._assinatura = assinatura
        self.caminho, self.df = caminho, df
        self.atualizado.emit(df, caminho)

    def estado_atual(self) -> tuple[Path | None, int]:
        """(arquivo, nº de linhas) no instante atual, lendo o arquivo se necessário."""
        self.verificar()
        return self.caminho, len(self.df)


# ---------------------------------------------------------------- contexto global
class Contexto(QObject):
    raiz_alterada = Signal(object)
    mensagem = Signal(str, str)          # (nível, texto)
    comando_enviado = Signal(int)

    def __init__(self):
        super().__init__()
        self.raiz: Path = raiz_padrao()
        self.monitor = MonitorLog(self)
        self.gerencia = None             # AbaGerencia, registrada pela janela principal
        self.ultimo_comando: int | None = None

    def definir_raiz(self, raiz: Path):
        self.raiz = Path(raiz)
        self.raiz_alterada.emit(self.raiz)
        self.log(f"Pasta de trabalho: {self.raiz}")

    def log(self, texto: str, nivel: str = "info"):
        self.mensagem.emit(nivel, texto)


# ---------------------------------------------------------------- gráficos
class Grafico(QWidget):
    def __init__(self, parent=None, polar: bool = False, barra: bool = True, tamanho=(6, 4)):
        super().__init__(parent)
        self.fig = Figure(figsize=tamanho, layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.fig)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        if barra:
            lay.addWidget(NavigationToolbar2QT(self.canvas, self))
        lay.addWidget(self.canvas)
        self.polar = polar

    def limpar(self, linhas=1, colunas=1, **kw):
        self.fig.clear()
        if self.polar:
            kw.setdefault("subplot_kw", {"projection": "polar"})
        axs = self.fig.subplots(linhas, colunas, squeeze=False, **kw)
        return axs.ravel().tolist() if linhas * colunas > 1 else axs[0][0]

    def desenhar(self):
        self.canvas.draw_idle()


# ---------------------------------------------------------------- tabelas
class ModeloDataFrame(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame | None = None, casas: int = 3):
        super().__init__()
        self.df = df if df is not None else pd.DataFrame()
        self.casas = casas

    def definir(self, df: pd.DataFrame):
        self.beginResetModel()
        self.df = df.reset_index(drop=True)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.df)

    def columnCount(self, parent=QModelIndex()):
        return self.df.shape[1]

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        v = self.df.iat[idx.row(), idx.column()]
        if role == Qt.DisplayRole:
            if isinstance(v, (float, np.floating)):
                return "" if np.isnan(v) else f"{v:.{self.casas}f}"
            return "" if v is None else str(v)
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter) if isinstance(v, (int, float, np.number)) \
                else int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def headerData(self, s, orient, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        return str(self.df.columns[s]) if orient == Qt.Horizontal else str(s + 1)


class TabelaDataFrame(QTableView):
    def __init__(self, parent=None, casas: int = 3):
        super().__init__(parent)
        self.modelo = ModeloDataFrame(casas=casas)
        self.setModel(self.modelo)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setDefaultSectionSize(22)

    def definir(self, df: pd.DataFrame):
        self.modelo.definir(df)


# ---------------------------------------------------------------- campos
def spin_float(minimo, maximo, valor, casas=2, passo=1.0, sufixo="") -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(minimo, maximo)
    s.setDecimals(casas)
    s.setSingleStep(passo)
    s.setValue(valor)
    if sufixo:
        s.setSuffix(f" {sufixo}")
    s.setKeyboardTracking(False)
    return s


def spin_int(minimo, maximo, valor, sufixo="") -> QSpinBox:
    s = QSpinBox()
    s.setRange(minimo, maximo)
    s.setValue(valor)
    if sufixo:
        s.setSuffix(f" {sufixo}")
    s.setKeyboardTracking(False)
    return s


def grupo_form(titulo: str, campos: list[tuple[str, QWidget]]) -> QGroupBox:
    g = QGroupBox(titulo)
    f = QFormLayout(g)
    for rotulo, w in campos:
        f.addRow(rotulo, w)
    return g


def rotulo_valor(texto="—") -> QLabel:
    l = QLabel(texto)
    l.setTextInteractionFlags(Qt.TextSelectableByMouse)
    l.setStyleSheet("font-weight: 600;")
    return l


def erro(parent, texto: str):
    QMessageBox.critical(parent, "Erro", texto)


def info_exportacao(parent, ctx: Contexto, pasta: Path):
    ctx.log(f"Exportado para {pasta}", "ok")
    r = QMessageBox.information(parent, "Exportação concluída",
                                f"Arquivos salvos em:\n{pasta}\n\nAbrir a pasta?",
                                QMessageBox.Open | QMessageBox.Close)
    if r == QMessageBox.Open:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(pasta)))


def escolher_arquivo(parent, titulo, filtro, pasta=None) -> Path | None:
    caminho, _ = QFileDialog.getOpenFileName(parent, titulo, str(pasta or ""), filtro)
    return Path(caminho) if caminho else None


def agora() -> str:
    return datetime.now().strftime("%H:%M:%S")


COR_NIVEL = {"info": QColor("#c8d1dc"), "ok": QColor("#7ee787"), "aviso": QColor("#f0b72f"),
             "erro": QColor("#ff7b72")}
