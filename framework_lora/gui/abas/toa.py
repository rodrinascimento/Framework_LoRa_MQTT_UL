"""Aba Time on Air: planilha 'LoRa Time on Air DataRate'."""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QSplitter, QVBoxLayout, QWidget)

from ...core import exportar as exp
from ...core import toa
from ..comum import Contexto, Grafico, TabelaDataFrame, erro, grupo_form, info_exportacao, rotulo_valor, spin_float, spin_int


class AbaToA(QWidget):
    titulo = "Time on Air"

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        self.payload = spin_int(0, 255, 20, "bytes")
        self.sf = QComboBox(); self.sf.addItems([str(s) for s in toa.SFS]); self.sf.setCurrentText("7")
        self.bw = QComboBox(); self.bw.addItems([str(b) for b in toa.BWS_KHZ]); self.bw.setCurrentText("125")
        self.cr = QComboBox(); self.cr.addItems([f"4/{4 + c}" for c in toa.CRS])
        self.pre = spin_int(6, 65535, 8, "símbolos")
        self.crc = QCheckBox("CRC habilitado"); self.crc.setChecked(True)
        self.ih = QCheckBox("Header implícito")
        self.ldro = QComboBox(); self.ldro.addItems(["Automático (Ts > 16 ms)", "Forçar ligado", "Forçar desligado"])
        self.duty = spin_float(0.01, 100, 1.0, casas=2, passo=0.1, sufixo="%")
        entrada = grupo_form("Configuração do rádio", [
            ("Payload:", self.payload), ("Spreading factor:", self.sf), ("Largura de banda [kHz]:", self.bw),
            ("Coding rate:", self.cr), ("Preâmbulo:", self.pre), ("", self.crc), ("", self.ih),
            ("Low data rate optimization:", self.ldro), ("Duty cycle:", self.duty)])

        g_res = QGroupBox("Resultado")
        gr = QGridLayout(g_res)
        self.res = {}
        for i, (k, t) in enumerate([("toa", "Time on Air"), ("ts", "Tempo de símbolo"), ("tpre", "Preâmbulo"),
                                    ("npay", "Símbolos de payload"), ("tpay", "Tempo de payload"),
                                    ("rb", "Bit rate nominal"), ("ref", "Taxa efetiva"), ("de", "LDRO"),
                                    ("int", "Intervalo mínimo p/ duty cycle"), ("ant", "ToA na planilha antiga")]):
            gr.addWidget(QLabel(t + ":"), i, 0)
            self.res[k] = rotulo_valor()
            gr.addWidget(self.res[k], i, 1)
        self.res["toa"].setStyleSheet("font-weight:700;font-size:18px;color:#1f6feb")

        nota = QLabel("Fórmula da Semtech (SX127x). A planilha antiga usava preâmbulo 8 + 4,5, CRC = 2 e "
                      "arredondava depois de multiplicar por (CR + 4); a última linha mostra esse valor só "
                      "para comparação.")
        nota.setWordWrap(True); nota.setStyleSheet("color:gray")

        esq = QVBoxLayout(); esq.addWidget(entrada); esq.addWidget(g_res); esq.addWidget(nota); esq.addStretch(1)
        w_esq = QWidget(); w_esq.setLayout(esq); w_esq.setMaximumWidth(430)

        self.graf = Grafico()
        self.tabela = TabelaDataFrame(casas=2)
        bt_exp = QPushButton("Exportar tabela completa…"); bt_exp.clicked.connect(self.exportar)
        dir_ = QSplitter(Qt.Vertical)
        dir_.addWidget(self.graf)
        w_tab = QWidget(); lt = QVBoxLayout(w_tab); lt.setContentsMargins(0, 0, 0, 0)
        lt.addWidget(QLabel("Todas as combinações SF × BW × CR para o payload e configurações acima:"))
        lt.addWidget(self.tabela); lt.addWidget(bt_exp, alignment=Qt.AlignRight)
        dir_.addWidget(w_tab)

        lay = QHBoxLayout(self)
        lay.addWidget(w_esq); lay.addWidget(dir_, 1)

        for w in (self.payload, self.pre, self.duty):
            w.valueChanged.connect(self.calcular)
        for w in (self.sf, self.bw, self.cr, self.ldro):
            w.currentIndexChanged.connect(self.calcular)
        for w in (self.crc, self.ih):
            w.toggled.connect(self.calcular)
        self.calcular()

    def _kw(self):
        de = {0: None, 1: 1, 2: 0}[self.ldro.currentIndex()]
        return dict(n_preambulo=self.pre.value(), crc=int(self.crc.isChecked()),
                    header_implicito=int(self.ih.isChecked()), de=de)

    def tabela_df(self) -> pd.DataFrame:
        linhas = []
        for r in toa.tabela_toa(self.payload.value(), **self._kw()):
            linhas.append({"SF": r.sf, "BW [kHz]": r.bw_khz, "CR": r.cr_texto, "LDRO": r.de,
                           "Ts [ms]": r.t_simbolo_ms, "ToA [ms]": r.toa_ms,
                           "Rb nominal [bps]": r.bitrate_nominal_bps, "Taxa efetiva [bps]": r.taxa_efetiva_bps,
                           "Intervalo mín. [s]": toa.tempo_minimo_entre_pacotes(r.toa_ms, self.duty.value() / 100),
                           "ToA planilha antiga [ms]": toa.toa_planilha_original(self.payload.value(), r.sf,
                                                                                  r.bw_khz, r.cr, r.de)})
        return pd.DataFrame(linhas)

    def calcular(self):
        try:
            r = toa.calcular_toa(self.payload.value(), int(self.sf.currentText()), float(self.bw.currentText()),
                                 self.cr.currentIndex() + 1, **self._kw())
        except ValueError as e:
            self.ctx.log(str(e), "erro"); return
        self.res["toa"].setText(f"{r.toa_ms:.3f} ms")
        self.res["ts"].setText(f"{r.t_simbolo_ms:.3f} ms")
        self.res["tpre"].setText(f"{r.t_preambulo_ms:.3f} ms")
        self.res["npay"].setText(str(r.n_simbolos_payload))
        self.res["tpay"].setText(f"{r.t_payload_ms:.3f} ms")
        self.res["rb"].setText(f"{r.bitrate_nominal_bps:.1f} bps")
        self.res["ref"].setText(f"{r.taxa_efetiva_bps:.1f} bps")
        self.res["de"].setText("ligado" if r.de else "desligado")
        self.res["int"].setText(f"{toa.tempo_minimo_entre_pacotes(r.toa_ms, self.duty.value() / 100):.2f} s")
        self.res["ant"].setText(f"{toa.toa_planilha_original(r.payload_bytes, r.sf, r.bw_khz, r.cr, r.de):.3f} ms")

        df = self.tabela_df()
        self.tabela.definir(df)
        ax = self.graf.limpar()
        cr_sel = self.cr.currentText()
        for bw in toa.BWS_KHZ:
            d = df[(df["BW [kHz]"] == bw) & (df["CR"] == cr_sel)]
            ax.semilogy(d["SF"], d["ToA [ms]"], "o-", label=f"BW {bw} kHz")
        ax.plot([r.sf], [r.toa_ms], "o", ms=14, mfc="none", mec="#da3633", mew=2, label="seleção")
        ax.set_xlabel("Spreading factor"); ax.set_ylabel("Time on Air [ms]")
        ax.set_title(f"ToA × SF — payload {self.payload.value()} B, CR {cr_sel}")
        ax.grid(True, which="both", alpha=0.3); ax.legend()
        self.graf.desenhar()

    def exportar(self):
        try:
            pasta = exp.exportar(self.ctx.raiz, "time_on_air", {
                "ToA - todas combinações": self.tabela_df(),
                "Parâmetros": exp.parametros_para_df(self.estado()),
            }, figuras={"toa_x_sf": self.graf.fig}, nome=f"{self.payload.value()}B")
        except OSError as e:
            erro(self, f"Falha ao exportar: {e}"); return
        info_exportacao(self, self.ctx, pasta)

    def estado(self):
        return {"payload": self.payload.value(), "sf": self.sf.currentText(), "bw": self.bw.currentText(),
                "cr": self.cr.currentText(), "preambulo": self.pre.value(), "crc": self.crc.isChecked(),
                "header_implicito": self.ih.isChecked(), "ldro": self.ldro.currentIndex(),
                "duty_cycle_pct": self.duty.value()}

    def restaurar(self, e):
        self.payload.setValue(e.get("payload", 20)); self.sf.setCurrentText(str(e.get("sf", "7")))
        self.bw.setCurrentText(str(e.get("bw", "125"))); self.cr.setCurrentText(e.get("cr", "4/5"))
        self.pre.setValue(e.get("preambulo", 8)); self.crc.setChecked(e.get("crc", True))
        self.ih.setChecked(e.get("header_implicito", False)); self.ldro.setCurrentIndex(e.get("ldro", 0))
        self.duty.setValue(e.get("duty_cycle_pct", 1.0))
