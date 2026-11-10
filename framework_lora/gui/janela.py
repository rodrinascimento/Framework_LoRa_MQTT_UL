"""Janela principal: navegação lateral por grupos, log de eventos e projetos."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                               QStackedWidget, QToolBar, QVBoxLayout, QWidget)

from .. import __version__
from .abas.caracterizacao import AbaCaracterizacao
from .abas.cliente import AbaCliente
from .abas.gerencia import AbaGerencia
from .abas.linkbudget import AbaLinkBudget
from .abas.survey import AbaSurvey
from .abas.toa import AbaToA
from .comum import Contexto, agora

GRUPOS = [
    ("OPERAÇÃO", [("gerencia", AbaGerencia), ("cliente", AbaCliente)]),
    ("PROJETO DO ENLACE", [("link_budget", AbaLinkBudget), ("time_on_air", AbaToA)]),
    ("CAMPO DE TESTE", [("site_survey", AbaSurvey), ("caracterizacao", AbaCaracterizacao)]),
]

ESTILO = """
QListWidget#nav { background:#0d1117; color:#c9d1d9; border:none; font-size:14px; outline:0; }
QListWidget#nav::item { padding:9px 14px; }
QListWidget#nav::item:selected { background:#1f6feb; color:white; border-radius:6px; }
QListWidget#nav::item:disabled { color:#8b949e; font-size:11px; font-weight:bold; padding-top:16px; }
QGroupBox { font-weight:bold; border:1px solid #d0d7de; border-radius:8px; margin-top:12px; padding-top:8px; }
QGroupBox::title { subcontrol-origin: margin; left:10px; padding:0 4px; }
QPlainTextEdit#log { background:#0d1117; color:#c9d1d9; font-family:Consolas, 'DejaVu Sans Mono', monospace; }
"""


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Framework LoRa — Campo de Testes  v{__version__}")
        self.resize(1360, 860)
        self.setStyleSheet(ESTILO)
        self.ctx = Contexto()
        self.settings = QSettings("WissTek-IoT", "FrameworkLoRa")
        raiz = self.settings.value("raiz")
        if raiz and Path(raiz).is_dir():
            self.ctx.raiz = Path(raiz)

        # ---------------- log de eventos (criado antes das abas para receber mensagens)
        self.txt_log = QPlainTextEdit(); self.txt_log.setObjectName("log"); self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(2000)
        self.ctx.mensagem.connect(self._log)
        dock = QDockWidget("Log de eventos", self)
        dock.setObjectName("dock_log")
        dock.setWidget(self.txt_log)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        # ---------------- navegação + páginas
        self.nav = QListWidget(); self.nav.setObjectName("nav"); self.nav.setFixedWidth(270)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.paginas = QStackedWidget()
        self.abas: dict[str, QWidget] = {}
        for grupo, itens in GRUPOS:
            cab = QListWidgetItem(grupo); cab.setFlags(Qt.NoItemFlags); self.nav.addItem(cab)
            for chave, cls in itens:
                w = cls(self.ctx)
                self.abas[chave] = w
                idx = self.paginas.addWidget(w)
                it = QListWidgetItem("   " + cls.titulo)
                it.setData(Qt.UserRole, idx)
                self.nav.addItem(it)
        self.nav.currentItemChanged.connect(
            lambda it, _: it and it.data(Qt.UserRole) is not None and self.paginas.setCurrentIndex(it.data(Qt.UserRole)))
        self.nav.setCurrentRow(1)

        central = QWidget()
        lc = QHBoxLayout(central); lc.setContentsMargins(0, 0, 0, 0); lc.setSpacing(0)
        lc.addWidget(self.nav)
        w_pag = QWidget(); lp = QVBoxLayout(w_pag); lp.addWidget(self.paginas)
        lc.addWidget(w_pag, 1)
        self.setCentralWidget(central)

        # ---------------- barra de ferramentas
        tb = QToolBar("Principal"); tb.setObjectName("tb"); tb.setMovable(False); tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)
        tb.addWidget(QLabel("  Pasta de trabalho: "))
        self.lb_raiz = QLabel(); self.lb_raiz.setStyleSheet("font-weight:bold")
        tb.addWidget(self.lb_raiz)
        bt = QPushButton("Alterar…"); bt.clicked.connect(self.escolher_raiz); tb.addWidget(bt)
        tb.addSeparator()
        for txt, atalho, fn in [("Abrir projeto…", QKeySequence.Open, self.abrir_projeto),
                                ("Salvar projeto…", QKeySequence.Save, self.salvar_projeto)]:
            a = QAction(txt, self); a.setShortcut(atalho); a.triggered.connect(fn); tb.addAction(a)
        tb.addSeparator()
        a = QAction("Sobre", self); a.triggered.connect(self.sobre); tb.addAction(a)

        self.lb_cmd = QLabel("Gateway: aguardando comando")
        self.lb_mon = QLabel("")
        self.statusBar().addWidget(self.lb_cmd)
        self.statusBar().addPermanentWidget(self.lb_mon)
        self.ctx.comando_enviado.connect(lambda c: self.lb_cmd.setText(
            f"Gateway: último comando {['PARAR', 'INICIAR', 'PAUSAR'][c]} às {agora()}"))
        self.ctx.monitor.atualizado.connect(lambda df, p: self.lb_mon.setText(f"Log: {p.name} ({len(df)} pacotes)"))
        self.ctx.raiz_alterada.connect(lambda r: self.lb_raiz.setText(str(r)))
        self.lb_raiz.setText(str(self.ctx.raiz))

        self._restaurar_sessao()
        geo = self.settings.value("geometria")
        if geo:
            self.restoreGeometry(geo)
        self.ctx.log(f"Framework LoRa iniciado. Parâmetros em {self.ctx.raiz / '4_N4_Armazenamento' / 'Parametros'}")

    # ------------------------------------------------------------ log
    def _log(self, nivel, texto):
        cor = {"info": "#c9d1d9", "ok": "#7ee787", "aviso": "#f0b72f", "erro": "#ff7b72"}.get(nivel, "#c9d1d9")
        self.txt_log.appendHtml(f'<span style="color:#8b949e">{agora()}</span> '
                                f'<span style="color:{cor}">{texto}</span>')

    # ------------------------------------------------------------ pasta e projetos
    def escolher_raiz(self):
        p = QFileDialog.getExistingDirectory(
            self, "Pasta de trabalho (onde fica 4_N4_Armazenamento, a mesma usada pelo gateway)", str(self.ctx.raiz))
        if p:
            self.ctx.definir_raiz(Path(p))
            self.settings.setValue("raiz", p)

    def estado(self) -> dict:
        return {"versao": __version__, "raiz": str(self.ctx.raiz),
                "abas": {k: w.estado() for k, w in self.abas.items()}}

    def restaurar(self, e: dict):
        for k, w in self.abas.items():
            if k in e.get("abas", {}):
                try:
                    w.restaurar(e["abas"][k])
                except Exception as ex:  # projeto de versão antiga ou editado à mão
                    self.ctx.log(f"Não foi possível restaurar '{k}': {ex}", "aviso")

    def salvar_projeto(self):
        p, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", str(self.ctx.raiz / "projeto_lora.json"),
                                           "Projeto (*.json)")
        if p:
            Path(p).write_text(json.dumps(self.estado(), indent=2, ensure_ascii=False), encoding="utf-8")
            self.ctx.log(f"Projeto salvo em {p}", "ok")

    def abrir_projeto(self):
        p, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", str(self.ctx.raiz), "Projeto (*.json)")
        if not p:
            return
        try:
            e = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError) as ex:
            QMessageBox.critical(self, "Erro", f"Projeto inválido: {ex}"); return
        if e.get("raiz") and Path(e["raiz"]).is_dir():
            self.ctx.definir_raiz(Path(e["raiz"]))
        self.restaurar(e)
        self.ctx.log(f"Projeto carregado de {p}", "ok")

    def _restaurar_sessao(self):
        txt = self.settings.value("ultima_sessao")
        if txt:
            try:
                self.restaurar(json.loads(txt))
            except ValueError:
                pass

    def sobre(self):
        QMessageBox.about(self, "Sobre", f"<b>Framework LoRa — Campo de Testes</b> v{__version__}<br>"
                          "WissTek-IoT · Framework Local DL-UL<br><br>Interface única para gerência do gateway, "
                          "parâmetros do cliente, link budget, time on air, site survey e caracterização de antenas.")

    # ------------------------------------------------------------ fechamento
    def closeEvent(self, ev):
        if QMessageBox.question(self, "Sair", "Deseja fechar o Framework LoRa?") != QMessageBox.Yes:
            ev.ignore(); return
        self.abas["gerencia"].parar_se_ativo()
        self.ctx.monitor.parar()
        self.settings.setValue("ultima_sessao", json.dumps(self.estado(), ensure_ascii=False))
        self.settings.setValue("geometria", self.saveGeometry())
        ev.accept()
