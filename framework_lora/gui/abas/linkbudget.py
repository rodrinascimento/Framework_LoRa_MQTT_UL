"""Aba Link budget: planilha 'Tópico 3.2 - Linkbudget' (espaço livre, log-distance e projeto)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)
from PySide6.QtCore import Qt

from ...core import exportar as exp
from ...core import linkbudget as lb
from ..comum import (Contexto, Grafico, TabelaDataFrame, erro, grupo_form, info_exportacao,
                     rotulo_valor, spin_float, spin_int)

COLS_NOS = [("Nó sensor", "nome", str), ("Distância [m]", "distancia_m", float), ("d0 [m]", "d0_m", float),
            ("n (path loss)", "n", float), ("Ganho NS [dBi]", "ganho_dbi", float), ("Paredes", "paredes", float),
            ("Armários", "armarios", float), ("Máquinas", "maquinas", float),
            ("Aten. altura [dB]", "atenuacao_altura_db", float), ("Prx medida [dBm] (opcional)", "prx_medida_dbm", float)]
NOS_PADRAO = [["Sensor LRC", 33, 1, 3.0, 2, 2, 1, 0, 0, ""], ["Sensor SRC", 40, 1, 3.2, 2, 3, 0, 0, 0, ""]]


class AbaLinkBudget(QWidget):
    titulo = "Link budget"

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        # ---------------- enlace único
        self.f = spin_float(1, 10000, 915, casas=3, sufixo="MHz")
        self.ptx = spin_float(-30, 40, 17, sufixo="dBm")
        self.g_gw = spin_float(-20, 40, 12, sufixo="dBi")
        self.g_ns = spin_float(-20, 40, 2, sufixo="dBi")
        self.d = spin_float(0.1, 1e6, 1000, casas=1, passo=10, sufixo="m")
        self.d0 = spin_float(0.01, 1000, 1, sufixo="m")
        self.n = spin_float(1, 8, 4, casas=2, passo=0.1)
        self.sens = spin_float(-150, 0, -137, sufixo="dBm")
        self.zona = spin_int(1, 20, 1)
        entrada = grupo_form("Enlace", [
            ("Frequência:", self.f), ("Potência TX:", self.ptx), ("Ganho antena gateway:", self.g_gw),
            ("Ganho antena nó sensor:", self.g_ns), ("Distância:", self.d), ("Distância de referência d0:", self.d0),
            ("Coeficiente de path loss n:", self.n), ("Sensibilidade do receptor:", self.sens),
            ("Zona de Fresnel:", self.zona)])

        g_res = QGroupBox("Resultados")
        gr = QGridLayout(g_res)
        self.res = {}
        itens = [("lam", "Comprimento de onda"), ("lel", "Atenuação espaço livre"), ("prx_el", "Prx espaço livre"),
                 ("lld", "Atenuação log-distance"), ("prx_ld", "Prx log-distance"),
                 ("margem", "Margem (log-distance − sensib.)"), ("fresnel", "Raio da zona de Fresnel (meio)")]
        for i, (k, t) in enumerate(itens):
            gr.addWidget(QLabel(t + ":"), i, 0)
            self.res[k] = rotulo_valor()
            gr.addWidget(self.res[k], i, 1)

        self.graf = Grafico()
        esq = QVBoxLayout(); esq.addWidget(entrada); esq.addWidget(g_res); esq.addStretch(1)
        topo = QHBoxLayout(); w_esq = QWidget(); w_esq.setLayout(esq); w_esq.setMaximumWidth(420)
        topo.addWidget(w_esq); topo.addWidget(self.graf, 1)
        w_topo = QWidget(); w_topo.setLayout(topo)

        # ---------------- projeto com vários nós
        self.f_proj = spin_float(1, 10000, 903, casas=3, sufixo="MHz")
        self.ptx_proj = spin_float(-30, 40, 17, sufixo="dBm")
        self.g_gw_proj = spin_float(-20, 40, 2, sufixo="dBi")
        self.a_par = spin_float(0, 100, 16, sufixo="dB")
        self.a_arm = spin_float(0, 100, 3, sufixo="dB")
        self.a_maq = spin_float(0, 100, 5, sufixo="dB")
        self.mf = spin_float(0, 100, 20, sufixo="dB")
        amb = QGroupBox("Projeto: parâmetros comuns e atenuações do ambiente")
        la = QGridLayout(amb)
        for i, (t, w) in enumerate([("Frequência", self.f_proj), ("Ptx", self.ptx_proj), ("Ganho gateway", self.g_gw_proj),
                                    ("Por parede", self.a_par), ("Por armário", self.a_arm),
                                    ("Por máquina", self.a_maq), ("Margem de fading", self.mf)]):
            la.addWidget(QLabel(t), 0, i)
            la.addWidget(w, 1, i)

        self.tab_nos = QTableWidget(0, len(COLS_NOS))
        self.tab_nos.setHorizontalHeaderLabels([c[0] for c in COLS_NOS])
        self.tab_nos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        for linha in NOS_PADRAO:
            self._add_no(linha)
        bt_add = QPushButton("+ Nó"); bt_add.clicked.connect(lambda: self._add_no(["Novo nó", 50, 1, 3, 2, 0, 0, 0, 0, ""]))
        bt_rem = QPushButton("− Remover selecionado"); bt_rem.clicked.connect(self._rem_no)
        bt_calc = QPushButton("Calcular projeto"); bt_calc.clicked.connect(self.calcular_projeto)
        bt_exp = QPushButton("Exportar link budget…"); bt_exp.clicked.connect(self.exportar)
        lbt = QHBoxLayout()
        for b in (bt_add, bt_rem, bt_calc): lbt.addWidget(b)
        lbt.addStretch(1); lbt.addWidget(bt_exp)
        self.tab_res = TabelaDataFrame()
        nota = QLabel("Ltot = L_EL(d0) + 10·n·log10(d/d0) + paredes·A + armários·A + máquinas·A + altura + margem. "
                      "Com Prx medida (média do site survey), calcula a perda medida, o ajuste necessário e o n "
                      "que reproduziria a medida.")
        nota.setWordWrap(True); nota.setStyleSheet("color:gray")

        baixo = QVBoxLayout()
        baixo.addWidget(amb); baixo.addWidget(self.tab_nos); baixo.addLayout(lbt)
        baixo.addWidget(self.tab_res); baixo.addWidget(nota)
        w_baixo = QWidget(); w_baixo.setLayout(baixo)

        abas = QTabWidget()
        abas.addTab(w_topo, "Enlace único (espaço livre × log-distance)")
        abas.addTab(w_baixo, "Projeto com vários nós sensores")
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(abas)

        for w in (self.f, self.ptx, self.g_gw, self.g_ns, self.d, self.d0, self.n, self.sens, self.zona):
            w.valueChanged.connect(self.calcular)
        self.calcular()
        self.calcular_projeto()

    # ------------------------------------------------------------ enlace
    def calcular(self):
        try:
            f = self.f.value() * 1e6
            lel = lb.perda_espaco_livre(self.d.value(), f)
            lld = lb.perda_log_distance(self.d.value(), f, self.n.value(), self.d0.value())
        except ValueError as e:
            self.ctx.log(str(e), "erro")
            return
        ganho = self.ptx.value() + self.g_gw.value() + self.g_ns.value()
        r = {"lam": f"{lb.comprimento_onda(f):.4f} m", "lel": f"{lel:.2f} dB", "prx_el": f"{ganho - lel:.2f} dBm",
             "lld": f"{lld:.2f} dB", "prx_ld": f"{ganho - lld:.2f} dBm",
             "margem": f"{ganho - lld - self.sens.value():.2f} dB",
             "fresnel": f"{lb.raio_fresnel(self.d.value(), f, self.zona.value()):.2f} m"}
        for k, v in r.items():
            self.res[k].setText(v)
        dmax = max(self.d.value() * 3, self.d0.value() * 10)
        dd, el, ld = lb.curva_prx(f, self.ptx.value(), self.g_gw.value(), self.g_ns.value(),
                                  self.n.value(), self.d0.value(), dmax)
        ax = self.graf.limpar()
        ax.semilogx(dd, el, label="Espaço livre")
        ax.semilogx(dd, ld, label=f"Log-distance (n = {self.n.value():g})")
        ax.axhline(self.sens.value(), color="#da3633", ls="--", lw=1, label="Sensibilidade")
        ax.axvline(self.d.value(), color="gray", ls=":", lw=1)
        ax.plot([self.d.value()], [ganho - lld], "o", color="C1")
        ax.set_xlabel("Distância [m]"); ax.set_ylabel("Prx [dBm]"); ax.set_title("Potência recebida × distância")
        ax.grid(True, which="both", alpha=0.3); ax.legend()
        self.graf.desenhar()

    # ------------------------------------------------------------ projeto
    def _add_no(self, valores):
        r = self.tab_nos.rowCount()
        self.tab_nos.insertRow(r)
        for c, v in enumerate(valores):
            self.tab_nos.setItem(r, c, QTableWidgetItem(str(v)))

    def _rem_no(self):
        r = self.tab_nos.currentRow()
        if r >= 0:
            self.tab_nos.removeRow(r)

    def nos(self) -> list[lb.NoSensor]:
        nos = []
        for r in range(self.tab_nos.rowCount()):
            kw = {}
            for c, (rot, campo, tipo) in enumerate(COLS_NOS):
                it = self.tab_nos.item(r, c)
                txt = (it.text() if it else "").strip().replace(",", ".")
                if campo == "prx_medida_dbm" and not txt:
                    kw[campo] = None
                    continue
                try:
                    kw[campo] = tipo(txt) if tipo is str else float(txt or 0)
                except ValueError:
                    raise ValueError(f"Linha {r + 1}, coluna '{rot}': valor inválido '{txt}'.") from None
            if kw["distancia_m"] <= 0 or kw["d0_m"] <= 0:
                raise ValueError(f"Linha {r + 1}: distâncias devem ser maiores que zero.")
            nos.append(lb.NoSensor(**kw))
        return nos

    def calcular_projeto(self) -> pd.DataFrame | None:
        try:
            nos = self.nos()
        except ValueError as e:
            erro(self, str(e)); return None
        amb = lb.AtenuacoesAmbiente(self.a_par.value(), self.a_arm.value(), self.a_maq.value(), self.mf.value())
        res = [lb.calcular_no(n, self.f_proj.value() * 1e6, self.ptx_proj.value(), self.g_gw_proj.value(), amb)
               for n in nos]
        df = pd.DataFrame([r.como_dict() for r in res]).rename(columns={
            "nome": "Nó sensor", "distancia_m": "Distância [m]", "perda_d0_db": "Atenuação d0 [dB]",
            "perda_total_db": "Ltot calculada [dB]", "prx_dbm": "Prx calculada [dBm]",
            "prx_medida_dbm": "Prx medida [dBm]", "perda_medida_db": "Ltot medida [dB]",
            "ajuste_db": "Ajuste log-distance [dB]", "n_ajustado": "n ajustado"})
        self.tab_res.definir(df)
        self.df_proj = df
        return df

    def exportar(self):
        df = self.calcular_projeto()
        if df is None:
            return
        f = self.f.value() * 1e6
        d = np.unique(np.r_[np.logspace(np.log10(self.d0.value()), np.log10(max(self.d.value() * 3, 10)), 60),
                            self.d.value()])
        g = self.ptx.value() + self.g_gw.value() + self.g_ns.value()
        curva = pd.DataFrame({"Distância [m]": d, "L espaço livre [dB]": lb.perda_espaco_livre(d, f),
                              "Prx espaço livre [dBm]": g - lb.perda_espaco_livre(d, f),
                              "L log-distance [dB]": lb.perda_log_distance(d, f, self.n.value(), self.d0.value()),
                              "Prx log-distance [dBm]": g - lb.perda_log_distance(d, f, self.n.value(), self.d0.value())})
        try:
            pasta = exp.exportar(self.ctx.raiz, "link_budget", {
                "Enlace": exp.parametros_para_df({**self.estado()["enlace"],
                                                  **{k: w.text() for k, w in self.res.items()}}),
                "Curva Prx x d": curva,
                "Projeto - nós": df,
                "Projeto - parâmetros": exp.parametros_para_df(self.estado()["projeto"]),
            }, figuras={"prx_x_distancia": self.graf.fig})
        except OSError as e:
            erro(self, f"Falha ao exportar: {e}"); return
        info_exportacao(self, self.ctx, pasta)

    # ------------------------------------------------------------ estado
    def estado(self):
        tabela = [[(self.tab_nos.item(r, c).text() if self.tab_nos.item(r, c) else "")
                   for c in range(len(COLS_NOS))] for r in range(self.tab_nos.rowCount())]
        return {
            "enlace": {"freq_mhz": self.f.value(), "ptx_dbm": self.ptx.value(), "g_gw_dbi": self.g_gw.value(),
                       "g_ns_dbi": self.g_ns.value(), "distancia_m": self.d.value(), "d0_m": self.d0.value(),
                       "n": self.n.value(), "sensibilidade_dbm": self.sens.value(), "zona_fresnel": self.zona.value()},
            "projeto": {"freq_mhz": self.f_proj.value(), "ptx_dbm": self.ptx_proj.value(),
                        "g_gw_dbi": self.g_gw_proj.value(), "parede_db": self.a_par.value(),
                        "armario_db": self.a_arm.value(), "maquina_db": self.a_maq.value(),
                        "margem_fading_db": self.mf.value()},
            "nos": tabela,
        }

    def restaurar(self, e):
        en, pr = e.get("enlace", {}), e.get("projeto", {})
        for w, k in [(self.f, "freq_mhz"), (self.ptx, "ptx_dbm"), (self.g_gw, "g_gw_dbi"), (self.g_ns, "g_ns_dbi"),
                     (self.d, "distancia_m"), (self.d0, "d0_m"), (self.n, "n"), (self.sens, "sensibilidade_dbm"),
                     (self.zona, "zona_fresnel")]:
            if k in en: w.setValue(en[k])
        for w, k in [(self.f_proj, "freq_mhz"), (self.ptx_proj, "ptx_dbm"), (self.g_gw_proj, "g_gw_dbi"),
                     (self.a_par, "parede_db"), (self.a_arm, "armario_db"), (self.a_maq, "maquina_db"),
                     (self.mf, "margem_fading_db")]:
            if k in pr: w.setValue(pr[k])
        if e.get("nos"):
            self.tab_nos.setRowCount(0)
            for linha in e["nos"]:
                self._add_no(linha)
        self.calcular_projeto()
