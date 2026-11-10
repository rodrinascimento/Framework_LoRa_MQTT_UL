"""Aba Site survey: logs do gateway ao vivo, estatísticas e exportação organizada.

Reproduz as abas 'MedidasSensor*' das planilhas e mostra os dados enquanto chegam.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)

from ...core import exportar as exp
from ...core import parametros as par
from ...core import survey
from ..comum import Contexto, Grafico, TabelaDataFrame, erro, info_exportacao, spin_int


class AbaSurvey(QWidget):
    titulo = "Site survey (logs)"

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        self.res: survey.ResultadoSurvey | None = None
        self.caminho: Path | None = None

        # ---------------- origem
        g = QGroupBox("Origem dos dados")
        lg = QVBoxLayout(g)
        self.rb_pasta = QRadioButton("Acompanhar o log mais recente da pasta")
        self.rb_arq = QRadioButton("Arquivo específico (log do gateway .csv/.txt/.log ou planilha .xlsx)")
        self.rb_pasta.setChecked(True)
        grp = QButtonGroup(self); grp.addButton(self.rb_pasta); grp.addButton(self.rb_arq)
        self.ed_pasta = QLineEdit(); self.ed_pasta.setReadOnly(True)
        bt_pasta = QPushButton("Pasta…"); bt_pasta.clicked.connect(self._escolher_pasta)
        self.ed_padrao = QLineEdit("log"); self.ed_padrao.setMaximumWidth(120)
        self.ed_padrao.setToolTip("Só arquivos cujo nome contém este texto (ex.: LOG_gerencia)")
        self.ed_arq = QLineEdit(); self.ed_arq.setReadOnly(True)
        bt_arq = QPushButton("Arquivo…"); bt_arq.clicked.connect(self._escolher_arquivo)
        l1 = QHBoxLayout(); l1.addWidget(self.rb_pasta); l1.addWidget(self.ed_pasta, 1); l1.addWidget(bt_pasta)
        l1.addWidget(QLabel("nome contém:")); l1.addWidget(self.ed_padrao)
        l2 = QHBoxLayout(); l2.addWidget(self.rb_arq); l2.addWidget(self.ed_arq, 1); l2.addWidget(bt_arq)
        self.ck_vivo = QCheckBox("Ao vivo (atualiza a cada 1 s)")
        self.ck_vivo.setChecked(True)
        self.janela = spin_int(1, 1000, 10, "amostras")
        bt_rec = QPushButton("Recarregar"); bt_rec.clicked.connect(lambda: self._aplicar_origem(forcar=True))
        bt_exp = QPushButton("Exportar análise…"); bt_exp.clicked.connect(self.exportar)
        bt_exp.setStyleSheet("font-weight:bold")
        l3 = QHBoxLayout(); l3.addWidget(self.ck_vivo); l3.addSpacing(20)
        l3.addWidget(QLabel("Janela da média móvel:")); l3.addWidget(self.janela)
        l3.addStretch(1); l3.addWidget(bt_rec); l3.addWidget(bt_exp)
        lg.addLayout(l1); lg.addLayout(l2); lg.addLayout(l3)
        self.lb_info = QLabel("Nenhum log carregado.")
        self.lb_info.setStyleSheet("color:gray")
        lg.addWidget(self.lb_info)

        # ---------------- resultados
        self.tab_resumo = TabelaDataFrame()
        self.graf_rssi = Grafico()
        self.graf_snr = Grafico()
        self.graf_hist = Grafico()
        self.tab_dados = TabelaDataFrame(casas=2)
        abas = QTabWidget()
        abas.addTab(self.graf_rssi, "RSSI × tempo")
        abas.addTab(self.graf_snr, "SNR × tempo")
        abas.addTab(self.graf_hist, "Distribuição")
        abas.addTab(self.tab_dados, "Dados")
        split = QSplitter(Qt.Horizontal)
        w_res = QWidget(); lr = QVBoxLayout(w_res); lr.setContentsMargins(0, 0, 0, 0)
        lr.addWidget(QLabel("Resumo")); lr.addWidget(self.tab_resumo)
        split.addWidget(w_res); split.addWidget(abas)
        split.setSizes([560, 800])

        lay = QVBoxLayout(self)
        lay.addWidget(g)
        lay.addWidget(split, 1)

        self.rb_pasta.toggled.connect(lambda _: self._aplicar_origem())
        self.ck_vivo.toggled.connect(lambda _: self._aplicar_origem())
        self.ed_padrao.editingFinished.connect(self._aplicar_origem)
        self.janela.valueChanged.connect(lambda _: self._recalcular())
        ctx.monitor.atualizado.connect(self._dados_novos)
        ctx.monitor.erro.connect(lambda m: ctx.log(m, "aviso"))
        ctx.raiz_alterada.connect(self._raiz_alterada)
        self._raiz_alterada(ctx.raiz)

    # ------------------------------------------------------------ origem
    def _raiz_alterada(self, raiz):
        self.ed_pasta.setText(str(par.pasta_armazenamento(raiz)))
        self._aplicar_origem()

    def _escolher_pasta(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta dos logs do gateway", self.ed_pasta.text())
        if p:
            self.ed_pasta.setText(p)
            self.rb_pasta.setChecked(True)
            self._aplicar_origem()

    def _escolher_arquivo(self):
        p, _ = QFileDialog.getOpenFileName(self, "Log do gateway", self.ed_pasta.text(),
                                           "Logs (*.csv *.txt *.log *.tsv *.xlsx *.xlsm);;Todos (*)")
        if p:
            self.ed_arq.setText(p)
            self.rb_arq.setChecked(True)
            self._aplicar_origem(forcar=True)

    def _aplicar_origem(self, forcar: bool = False):
        m = self.ctx.monitor
        if self.rb_pasta.isChecked():
            m.configurar(pasta=Path(self.ed_pasta.text()), padrao=self.ed_padrao.text().strip())
        else:
            arq = self.ed_arq.text().strip()
            m.configurar(arquivo=Path(arq) if arq else None)
        if self.ck_vivo.isChecked():
            m.iniciar()
        else:
            m.parar()
        m.verificar(forcar=True)

    # ------------------------------------------------------------ dados
    def _dados_novos(self, df, caminho):
        self.caminho = caminho
        self.df = df
        self._recalcular()

    def _recalcular(self):
        if getattr(self, "df", None) is None or self.df.empty:
            return
        self.res = survey.analisar(self.df, self.janela.value())
        r = self.res
        per = f" | PER {100 * r.per:.1f}%" if r.per is not None else ""
        self.lb_info.setText(f"{self.caminho.name}: {len(self.df)} pacotes{per} — {self.caminho.parent}")
        self.tab_resumo.definir(r.tabela_resumo())
        self.tab_dados.definir(survey.dados_para_exportar(r).iloc[::-1])
        self._plotar()

    def _plotar(self):
        d = self.res.dados
        x = d["contador"].to_numpy() if d["contador"].notna().all() else np.arange(1, len(d) + 1)
        ax1, ax2 = self.graf_rssi.limpar(2, 1, sharex=True)
        for ax, lado, cor in ((ax1, "dl", "C0"), (ax2, "ul", "C1")):
            ax.plot(x, d[f"rssi_{lado}"], ".", ms=3, color=cor, alpha=0.5, label=f"RSSI {lado.upper()}")
            ax.plot(x, d[f"mm_{lado}"], "-", color="k", lw=1.2, label=f"Média móvel ({self.res.janela})")
            est = getattr(self.res, lado)
            if est:
                ax.axhline(est.rssi_media_mm_dbm, color=cor, ls="--", lw=1,
                           label=f"Média {est.rssi_media_mm_dbm:.1f} dBm  σ {est.desvio_padrao:.2f} dB")
            ax.set_ylabel("dBm"); ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="lower left")
        ax1.set_title("RSSI downlink (acima) e uplink (abaixo)")
        ax2.set_xlabel("Contador de pacotes")
        self.graf_rssi.desenhar()

        ax = self.graf_snr.limpar()
        ax.plot(x, d["snr_dl"], ".-", ms=3, lw=0.6, label="SNR DL")
        ax.plot(x, d["snr_ul"], ".-", ms=3, lw=0.6, label="SNR UL")
        ax.set_xlabel("Contador de pacotes"); ax.set_ylabel("dB"); ax.grid(alpha=0.3); ax.legend()
        self.graf_snr.desenhar()

        ax = self.graf_hist.limpar()
        for lado in ("dl", "ul"):
            v = d[f"rssi_{lado}"].dropna()
            if len(v):
                bins = np.arange(np.floor(v.min()) - 0.5, np.ceil(v.max()) + 1.5, 1)
                ax.hist(v, bins=bins, alpha=0.6, label=f"RSSI {lado.upper()}")
        ax.set_xlabel("RSSI [dBm]"); ax.set_ylabel("Pacotes"); ax.grid(alpha=0.3); ax.legend()
        self.graf_hist.desenhar()

    # ------------------------------------------------------------ exportação
    def exportar(self):
        if self.res is None:
            erro(self, "Carregue um log antes de exportar."); return
        try:
            pasta = exp.exportar(self.ctx.raiz, "site_survey", {
                "Resumo": self.res.tabela_resumo(),
                "Dados": survey.dados_para_exportar(self.res),
                "Origem": exp.parametros_para_df({"Arquivo": str(self.caminho), "Pacotes": len(self.res.dados),
                                                  "Janela da média móvel": self.res.janela}),
            }, figuras={"rssi_tempo": self.graf_rssi.fig, "snr_tempo": self.graf_snr.fig,
                        "distribuicao_rssi": self.graf_hist.fig}, nome=self.caminho.stem if self.caminho else None)
        except OSError as e:
            erro(self, f"Falha ao exportar: {e}"); return
        info_exportacao(self, self.ctx, pasta)

    def estado(self):
        return {"modo": "pasta" if self.rb_pasta.isChecked() else "arquivo", "pasta": self.ed_pasta.text(),
                "arquivo": self.ed_arq.text(), "padrao": self.ed_padrao.text(), "janela": self.janela.value(),
                "ao_vivo": self.ck_vivo.isChecked()}

    def restaurar(self, e):
        if e.get("pasta"): self.ed_pasta.setText(e["pasta"])
        self.ed_arq.setText(e.get("arquivo", ""))
        self.ed_padrao.setText(e.get("padrao", "log"))
        self.janela.setValue(e.get("janela", 10))
        self.ck_vivo.setChecked(e.get("ao_vivo", True))
        (self.rb_arq if e.get("modo") == "arquivo" and e.get("arquivo") else self.rb_pasta).setChecked(True)
        self._aplicar_origem(forcar=True)
