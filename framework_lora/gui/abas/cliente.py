"""Aba Cliente: substitui Setup_Parametros_Cliente.py (limiar de luminosidade do nó)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSlider,
                               QVBoxLayout, QWidget)

from ...core import parametros as par
from ..comum import Contexto, Grafico, spin_int


class AbaCliente(QWidget):
    titulo = "Cliente (limiar de luminosidade)"

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        g = QGroupBox("Limiar de luminosidade do nó (ADC de 12 bits do ESP32)")
        lg = QVBoxLayout(g)
        lg.addWidget(QLabel(f"Limiar de ligar ({par.LIMIAR_MIN} a {par.LIMIAR_MAX}): abaixo deste valor o LED acende."))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(par.LIMIAR_MIN, par.LIMIAR_MAX)
        self.spin = spin_int(par.LIMIAR_MIN, par.LIMIAR_MAX, 2000)
        self.spin.setKeyboardTracking(True)
        linha = QHBoxLayout()
        linha.addWidget(self.slider, 1)
        linha.addWidget(self.spin)
        lg.addLayout(linha)
        self.lb_hist = QLabel()
        self.lb_hist.setStyleSheet("font-weight:bold;color:#b62324")
        lg.addWidget(self.lb_hist)
        bt = QPushButton("Salvar limiar")
        bt.setMinimumHeight(34)
        bt.clicked.connect(self.salvar)
        lg.addWidget(bt)
        self.lb_status = QLabel()
        self.lb_status.setStyleSheet("color:gray")
        lg.addWidget(self.lb_status)

        self.grafico = Grafico(barra=False, tamanho=(6, 1.6))
        self.grafico.setMinimumHeight(160)

        lay = QVBoxLayout(self)
        lay.addWidget(g)
        lay.addWidget(self.grafico)
        lay.addStretch(1)

        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.spin.valueChanged.connect(self._atualizar)
        self.carregar()
        ctx.raiz_alterada.connect(lambda _: self.carregar())

    def carregar(self):
        self.spin.setValue(par.ler_limiar_cliente(self.ctx.raiz))
        self._atualizar(self.spin.value())

    def _atualizar(self, v):
        desl = par.limiar_desligar(v)
        self.lb_hist.setText(f"Limiar de desligar (+{par.HISTERESE_CLIENTE}): {desl}")
        ax = self.grafico.limpar()
        ax.axvspan(par.LIMIAR_MIN, v, color="#f0b72f", alpha=0.35, label="LED liga")
        ax.axvspan(v, desl, color="#8b949e", alpha=0.35, label="histerese")
        ax.axvspan(desl, par.LIMIAR_MAX, color="#1f6feb", alpha=0.2, label="LED desliga")
        ax.set_xlim(par.LIMIAR_MIN, par.LIMIAR_MAX)
        ax.set_yticks([])
        ax.set_xlabel("Leitura do ADC")
        ax.legend(loc="upper center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, 1.35), frameon=False)
        self.grafico.desenhar()

    def salvar(self):
        try:
            v = par.validar_limiar(self.spin.value())
            caminho = par.gravar_limiar_cliente(self.ctx.raiz, v)
        except (par.ErroValidacao, OSError) as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        msg = f"Ligar: {v} | Desligar: {par.limiar_desligar(v)} salvo"
        self.lb_status.setText(f"{msg} em {caminho}")
        self.ctx.log(f"Cliente: {msg}", "ok")

    def estado(self):
        return {"limiar": self.spin.value()}

    def restaurar(self, e):
        if "limiar" in e:
            self.spin.setValue(int(e["limiar"]))
