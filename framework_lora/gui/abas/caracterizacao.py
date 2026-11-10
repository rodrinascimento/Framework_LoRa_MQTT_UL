"""Aba Caracterização de antena: assistente guiado do diagrama de radiação e perda sistêmica.

Substitui 'Diagrama de Radiacao HPBW.py', 'Diagrama de Radiacao HPBW e DesvPad.py' e a planilha
'Tópico 6.4 - Cálculo Perda Sistêmica'.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ...core import assistente_radiacao as ar
from ...core import exportar as exp
from ...core import linkbudget as lb
from ...core import parametros as par
from ...core import radiacao as rad
from ...core import survey
from ..comum import (Contexto, Grafico, TabelaDataFrame, erro, grupo_form, info_exportacao, rotulo_valor,
                     spin_float, spin_int)


# ====================================================================== assistente
class PainelAssistente(QWidget):
    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        self.sessao: ar.SessaoRadiacao | None = None
        self.amostras_externas: pd.DataFrame | None = None   # CSV angulo,rssi carregado
        self.resumo: pd.DataFrame | None = None
        self.metr: rad.MetricasRadiacao | None = None

        # ---------------- configuração
        self.a_ini = spin_float(0, 359, 0, casas=1, sufixo="°")
        self.a_passo = spin_float(1, 180, 30, casas=1, sufixo="°")
        self.a_fim = spin_float(0, 359.9, 330, casas=1, sufixo="°")
        self.n_pac = spin_int(1, 100000, 100, "pacotes")
        self.lado = QComboBox(); self.lado.addItems(["Uplink (no gateway)", "Downlink (no nó)"])
        self.ck_ref = QCheckBox("Medir antena de referência antes"); self.ck_ref.setChecked(True)
        self.g_ref = spin_float(-30, 50, 12.5, sufixo="dBi")
        self.rssi_ref = spin_float(-200, 30, -35, sufixo="dBm")
        self.ck_parar = QCheckBox("Enviar PARAR ao fim de cada etapa"); self.ck_parar.setChecked(True)
        bt_nova = QPushButton("Nova sessão guiada"); bt_nova.setStyleSheet("font-weight:bold")
        bt_nova.clicked.connect(self.nova_sessao)
        cfg = grupo_form("1. Configurar a medição", [
            ("Ângulo inicial:", self.a_ini), ("Passo:", self.a_passo), ("Ângulo final:", self.a_fim),
            ("Pacotes por ângulo:", self.n_pac), ("RSSI usado:", self.lado), ("", self.ck_ref),
            ("Ganho da antena de referência:", self.g_ref),
            ("RSSI de referência (manual):", self.rssi_ref), ("", self.ck_parar), ("", bt_nova)])
        cfg.setMaximumWidth(440)
        self.ck_ref.toggled.connect(lambda v: self.rssi_ref.setEnabled(not v))
        self.rssi_ref.setEnabled(False)

        # ---------------- condução
        self.lista = QListWidget()
        self.lista.currentRowChanged.connect(self._selecionar_etapa)
        self.lb_instr = QLabel("Configure a medição e clique em 'Nova sessão guiada'.")
        self.lb_instr.setWordWrap(True)
        self.lb_instr.setMinimumHeight(70)
        self.lb_instr.setStyleSheet("font-size:15px;font-weight:600;padding:10px;border-radius:8px;"
                                    "background:#1f6feb22;border:1px solid #1f6feb")
        self.pb = QProgressBar(); self.pb.setFormat("%v / %m pacotes")
        self.lb_ultimo = QLabel(""); self.lb_ultimo.setStyleSheet("color:gray")
        self.bt_coletar = QPushButton("▶  Coletar")
        self.bt_coletar.setMinimumHeight(40)
        self.bt_coletar.setStyleSheet("QPushButton{background:#238636;color:white;font-weight:bold;border-radius:6px}"
                                      "QPushButton:disabled{background:#8b949e}")
        self.bt_coletar.clicked.connect(self.coletar)
        self.bt_cancelar = QPushButton("■  Cancelar coleta"); self.bt_cancelar.clicked.connect(self.cancelar)
        self.bt_concluir = QPushButton("Concluir com o que chegou"); self.bt_concluir.clicked.connect(self.concluir_parcial)
        self.bt_importar = QPushButton("Importar log para esta etapa…"); self.bt_importar.clicked.connect(self.importar_log)
        self.bt_refazer = QPushButton("Refazer etapa"); self.bt_refazer.clicked.connect(self.refazer)
        lb1 = QHBoxLayout(); lb1.addWidget(self.bt_coletar, 2); lb1.addWidget(self.bt_cancelar, 1)
        lb2 = QHBoxLayout()
        for b in (self.bt_concluir, self.bt_importar, self.bt_refazer): lb2.addWidget(b)
        g_cond = QGroupBox("2. Coletar ângulo a ângulo")
        lc = QVBoxLayout(g_cond)
        lc.addWidget(self.lb_instr); lc.addWidget(self.pb); lc.addWidget(self.lb_ultimo)
        lc.addLayout(lb1); lc.addLayout(lb2)
        lc.addWidget(QLabel("Etapas:")); lc.addWidget(self.lista, 1)

        # ---------------- resultados
        self.graf = Grafico(polar=True, tamanho=(6, 6))
        self.graf.setMinimumHeight(420)
        self.ck_sigma = QCheckBox("Mostrar banda ±1σ"); self.ck_sigma.setChecked(True)
        self.ck_sigma.toggled.connect(lambda _: self.plotar())
        bt_csv = QPushButton("Abrir CSV angulo,rssi…"); bt_csv.clicked.connect(self.abrir_csv)
        bt_teste = QPushButton("Gerar dados de teste"); bt_teste.clicked.connect(self.dados_teste)
        bt_exp = QPushButton("Exportar diagrama…"); bt_exp.setStyleSheet("font-weight:bold")
        bt_exp.clicked.connect(self.exportar)
        self.tab_metr = TabelaDataFrame()
        self.tab_metr.setMaximumHeight(230)
        self.tab_etapas = TabelaDataFrame(casas=2)
        lr = QHBoxLayout(); lr.addWidget(self.ck_sigma); lr.addStretch(1)
        lr.addWidget(bt_csv); lr.addWidget(bt_teste); lr.addWidget(bt_exp)
        g_res = QGroupBox("3. Diagrama de radiação")
        lgr = QVBoxLayout(g_res)
        lgr.addLayout(lr)
        sub = QTabWidget()
        sub.addTab(self.graf, "Diagrama polar")
        sub.addTab(self.tab_etapas, "Etapas")
        lgr.addWidget(sub, 1)
        lgr.addWidget(self.tab_metr)

        split = QSplitter(Qt.Horizontal)
        w_esq = QWidget(); le = QVBoxLayout(w_esq); le.setContentsMargins(0, 0, 0, 0)
        le.addWidget(cfg); le.addWidget(g_cond, 1)
        split.addWidget(w_esq); split.addWidget(g_res)
        split.setSizes([460, 800])
        QVBoxLayout(self).addWidget(split)

        for w in (self.g_ref, self.rssi_ref):
            w.valueChanged.connect(lambda _: self.recalcular())
        ctx.monitor.atualizado.connect(self._log_atualizado)
        self._atualizar_ui()
        self.recalcular()

    # ------------------------------------------------------------ sessão
    @property
    def _lado(self):
        return "ul" if self.lado.currentIndex() == 0 else "dl"

    def nova_sessao(self):
        if self.sessao and any(e.concluida for e in self.sessao.etapas):
            if QMessageBox.question(self, "Nova sessão", "Descartar a sessão atual e começar outra?") != QMessageBox.Yes:
                return
        try:
            angs = ar.lista_angulos(self.a_ini.value(), self.a_passo.value(), self.a_fim.value())
            self.sessao = ar.SessaoRadiacao(angs, self.n_pac.value(), self._lado, self.ck_ref.isChecked())
        except ValueError as e:
            erro(self, str(e)); return
        self.amostras_externas = None
        self.ctx.log(f"Sessão de diagrama: {len(angs)} ângulos, {self.n_pac.value()} pacotes por etapa", "ok")
        self._atualizar_ui()
        self.recalcular()

    def _selecionar_etapa(self, i):
        if self.sessao and 0 <= i < len(self.sessao.etapas) and i != self.sessao.indice and not self.sessao.coletando:
            self.sessao.ir_para(i)
            self._atualizar_ui()

    def coletar(self):
        s = self.sessao
        if s is None or s.atual is None:
            return
        g = self.ctx.gerencia
        if g is None or not g.enviar(par.Comando.INICIAR, medidas=s.pacotes_por_etapa):
            erro(self, "Não foi possível iniciar a coleta. Confira a porta serial na aba Gerência.")
            return
        caminho, linhas = self.ctx.monitor.estado_atual()
        s.marcar_inicio(caminho, linhas)
        if not self.ctx.monitor.ativo:
            self.ctx.monitor.iniciar()
        self.ctx.log(f"Coletando {s.atual.rotulo} (a partir de {linhas} linhas em "
                     f"{caminho.name if caminho else 'nenhum log ainda'})")
        self._atualizar_ui()

    def cancelar(self):
        if self.sessao:
            self.sessao.cancelar()
        if self.ctx.gerencia:
            self.ctx.gerencia.enviar(par.Comando.PARAR, silencioso=True)
        self._atualizar_ui()

    def _log_atualizado(self, df, caminho):
        s = self.sessao
        if s is None or not s.coletando:
            return
        rotulo = s.atual.rotulo
        concluiu = s.atualizar(df, caminho)
        novas = s.novas_linhas(df, caminho)
        col = f"rssi_{s.lado}"
        if len(novas) and novas[col].notna().any():
            self.lb_ultimo.setText(f"Último RSSI: {novas[col].dropna().iloc[-1]:g} dBm")
        if concluiu:
            self._etapa_concluida(rotulo)
        else:
            self.pb.setValue(s.recebidos)

    def _etapa_concluida(self, rotulo):
        if self.ck_parar.isChecked() and self.ctx.gerencia:
            self.ctx.gerencia.enviar(par.Comando.PARAR, silencioso=True)
        self.ctx.log(f"Etapa {rotulo} concluída", "ok")
        QApplication.beep()
        self.recalcular()
        self._atualizar_ui()
        if self.sessao.finalizada:
            QMessageBox.information(self, "Diagrama concluído",
                                    "Todas as etapas foram coletadas. Confira o diagrama e exporte os resultados.")

    def concluir_parcial(self):
        s = self.sessao
        if not s or not s.coletando:
            return
        caminho, _ = self.ctx.monitor.estado_atual()
        novas = s.novas_linhas(self.ctx.monitor.df, caminho)
        novas = novas[novas[f"rssi_{s.lado}"].notna()]
        if novas.empty:
            erro(self, "Nenhum pacote chegou ainda nesta etapa."); return
        rot = s.atual.rotulo
        s.concluir(novas)
        self._etapa_concluida(rot)

    def importar_log(self):
        s = self.sessao
        if not s or s.atual is None:
            erro(self, "Crie uma sessão guiada primeiro."); return
        p, _ = QFileDialog.getOpenFileName(self, f"Log para {s.atual.rotulo}", str(par.pasta_armazenamento(self.ctx.raiz)),
                                           "Logs (*.csv *.txt *.log *.tsv *.xlsx *.xlsm);;Todos (*)")
        if not p:
            return
        try:
            df = survey.ler_log(p)
            rot = s.atual.rotulo
            s.concluir(df[df[f"rssi_{s.lado}"].notna()])
        except Exception as e:
            erro(self, f"Não foi possível usar o log: {e}"); return
        self.ctx.log(f"Etapa {rot} importada de {Path(p).name} ({len(df)} linhas)", "ok")
        self.recalcular(); self._atualizar_ui()

    def refazer(self):
        s = self.sessao
        if not s:
            return
        i = self.lista.currentRow()
        s.refazer(i if i >= 0 else None)
        self.recalcular(); self._atualizar_ui()

    # ------------------------------------------------------------ dados avulsos
    def abrir_csv(self):
        p, _ = QFileDialog.getOpenFileName(self, "Amostras angulo,rssi", str(self.ctx.raiz), "CSV (*.csv);;Todos (*)")
        if not p:
            return
        try:
            df = pd.read_csv(p, sep=None, engine="python")
            df.columns = [str(c).strip().lower() for c in df.columns]
            rad.resumir_amostras(df, 0, 0)
        except Exception as e:
            erro(self, f"Arquivo inválido: {e}"); return
        self.amostras_externas = df
        self.sessao = None
        self.ck_ref.setChecked(False)
        self.ctx.log(f"Amostras carregadas de {Path(p).name} ({len(df)} linhas)", "ok")
        self._atualizar_ui(); self.recalcular()

    def dados_teste(self):
        self.amostras_externas = rad.gerar_amostras_ficticias()
        self.sessao = None
        self.ck_ref.setChecked(False)
        self.rssi_ref.setValue(-35); self.g_ref.setValue(12.5)
        self.ctx.log("Dados de teste gerados (cosseno + ruído gaussiano σ = 0,8 dB)")
        self._atualizar_ui(); self.recalcular()

    # ------------------------------------------------------------ cálculo e gráfico
    def amostras(self) -> pd.DataFrame:
        if self.sessao:
            return self.sessao.amostras_angulo_rssi()
        if self.amostras_externas is not None:
            return self.amostras_externas
        return pd.DataFrame(columns=["angulo", "rssi"])

    def rssi_referencia(self) -> float:
        if self.sessao and self.sessao.com_referencia:
            r = self.sessao.rssi_referencia()
            if r is not None:
                self.rssi_ref.blockSignals(True)
                self.rssi_ref.setValue(r)
                self.rssi_ref.blockSignals(False)
                return r
        return self.rssi_ref.value()

    def recalcular(self):
        a = self.amostras()
        self.resumo, self.metr = None, None
        if self.sessao:
            self.tab_etapas.definir(self.sessao.tabela_etapas())
        if len(a):
            self.resumo = rad.resumir_amostras(a, self.rssi_referencia(), self.g_ref.value())
            if len(self.resumo) >= 3 and rad.volta_completa(self.resumo["angulo"]):
                self.metr = rad.metricas(self.resumo)
        self.tab_metr.definir(self.tabela_metricas())
        self.plotar()

    def tabela_metricas(self) -> pd.DataFrame:
        m = self.metr
        ref = self.rssi_referencia() if (self.sessao or self.amostras_externas is not None) else np.nan
        linhas = [("RSSI de referência", ref, "dBm"), ("Ganho da antena de referência", self.g_ref.value(), "dBi")]
        if m:
            linhas += [("Ganho máximo (boresight)", m.ganho_max_dbi, "dBi"), ("Ângulo do máximo", m.angulo_max, "°"),
                       ("Nível de corte (−3 dB)", m.nivel_corte_dbi, "dBi"), ("Largura de feixe (HPBW)", m.hpbw_graus, "°"),
                       ("Ganho traseiro", m.ganho_traseiro_dbi, "dBi"), ("Ângulo traseiro", m.angulo_traseiro, "°"),
                       ("Relação frente-costas (FBR)", m.fbr_db, "dB")]
        return pd.DataFrame(linhas, columns=["Grandeza", "Valor", "Unidade"])

    def plotar(self):
        ax = self.graf.limpar()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        r = self.resumo
        if r is None or r.empty:
            ax.set_title("Sem dados ainda")
            self.graf.desenhar(); return
        fechado = len(r) > 2 and rad.volta_completa(r["angulo"])
        rp = pd.concat([r, r.iloc[[0]].assign(angulo=r.iloc[0]["angulo"] + 360)], ignore_index=True) \
            if fechado else r
        th = np.radians(rp["angulo"].to_numpy(float))
        g = rp["ganho_dbi"].to_numpy(float)
        sd = rp["std"].to_numpy(float)
        if self.ck_sigma.isChecked():
            ax.fill_between(th, g - sd, g + sd, color="#1f77b4", alpha=0.25, label=r"Incerteza ($\pm 1\sigma$)")
        ax.plot(th, g, "o-", color="#1f77b4", lw=2.2, ms=4, label="Ganho médio (dBi)")
        m = self.metr
        titulo = "Diagrama de radiação"
        if m and not np.isnan(m.hpbw_graus):
            ax.plot([np.radians(m.theta_esq), np.radians(m.theta_dir)], [m.nivel_corte_dbi] * 2,
                    "r--", lw=1.5, label=f"HPBW {m.hpbw_graus:.1f}° (−3 dB)")
            ax.scatter([np.radians(m.theta_esq), np.radians(m.theta_dir)], [m.nivel_corte_dbi] * 2, color="red", zorder=5)
        if not fechado:
            titulo += "\n(parcial: HPBW e FBR aparecem quando todos os ângulos forem coletados)"
        if m:
            titulo += f"\nHPBW = {m.hpbw_graus:.1f}°  |  FBR = {m.fbr_db:.1f} dB  |  Gmáx = {m.ganho_max_dbi:.2f} dBi"
        # próxima posição da antena (assistente)
        if self.sessao and self.sessao.atual is not None and self.sessao.atual.chave != ar.REFERENCIA:
            ax.annotate("", xy=(np.radians(float(self.sessao.atual.chave)), np.nanmax(g + sd) + 2),
                        xytext=(0, np.nanmin(g - sd) - 5), arrowprops=dict(arrowstyle="->", color="#d29922", lw=2))
        lo = np.floor(np.nanmin(g - sd) / 5) * 5 - 5
        hi = np.ceil(np.nanmax(g + sd) / 5) * 5 + 5
        ax.set_rlim(lo, hi)
        ax.set_rlabel_position(135)
        ax.grid(True, ls="--", alpha=0.6)
        ax.set_title(titulo, va="bottom", fontsize=11, pad=16)
        self.graf.fig.legend(loc="outside lower center", ncol=3, fontsize=8, frameon=False)
        self.graf.desenhar()

    # ------------------------------------------------------------ interface
    def _atualizar_ui(self):
        s = self.sessao
        self.lista.blockSignals(True)
        self.lista.clear()
        if s:
            for i, e in enumerate(s.etapas):
                marca = "✔" if e.concluida else ("●" if i == s.indice else "○")
                extra = f" — {len(e.amostras)} pacotes" if e.concluida else ""
                it = QListWidgetItem(f"{marca}  {e.rotulo}{extra}")
                if e.concluida:
                    it.setForeground(QColor("#238636"))
                elif i == s.indice:
                    it.setForeground(QColor("#1f6feb"))
                self.lista.addItem(it)
            if s.indice < len(s.etapas):
                self.lista.setCurrentRow(s.indice)
            feitos, total = s.progresso
            instr = s.instrucao()
            if s.coletando:
                instr = f"Coletando {s.atual.rotulo}… aguarde {s.pacotes_por_etapa} pacotes."
            self.lb_instr.setText(f"[{feitos}/{total}]  {instr}")
            self.pb.setMaximum(s.pacotes_por_etapa)
            self.pb.setValue(s.recebidos if s.coletando else (s.pacotes_por_etapa if s.atual is None else 0))
        elif self.amostras_externas is not None:
            self.lb_instr.setText("Usando amostras carregadas de arquivo (sem coleta guiada).")
        self.lista.blockSignals(False)
        ativo = bool(s and s.atual is not None)
        self.bt_coletar.setEnabled(ativo and not s.coletando)
        self.bt_cancelar.setEnabled(bool(s and s.coletando))
        self.bt_concluir.setEnabled(bool(s and s.coletando))
        self.bt_importar.setEnabled(ativo and not s.coletando)
        self.bt_refazer.setEnabled(bool(s) and not (s and s.coletando))
        for w in (self.a_ini, self.a_passo, self.a_fim, self.n_pac, self.lado, self.ck_ref):
            w.setEnabled(not (s and s.coletando))

    def exportar(self):
        if self.resumo is None or self.resumo.empty:
            erro(self, "Ainda não há dados para exportar."); return
        resumo = self.resumo.rename(columns={"angulo": "Ângulo [°]", "mean": "RSSI médio [dBm]", "std": "Desvio [dB]",
                                             "count": "Pacotes", "ganho_dbi": "Ganho [dBi]"})
        abas = {"Métricas": self.tabela_metricas(), "Ganho por ângulo": resumo}
        if self.sessao:
            abas["Etapas"] = self.sessao.tabela_etapas()
            abas["Pacotes coletados"] = self.sessao.amostras_brutas()
        abas["Amostras angulo-rssi"] = self.amostras()
        abas["Parâmetros"] = exp.parametros_para_df(self.estado())
        try:
            pasta = exp.exportar(self.ctx.raiz, "diagrama_radiacao", abas, figuras={"diagrama_polar": self.graf.fig})
        except OSError as e:
            erro(self, f"Falha ao exportar: {e}"); return
        info_exportacao(self, self.ctx, pasta)

    def estado(self):
        return {"angulo_inicial": self.a_ini.value(), "passo": self.a_passo.value(), "angulo_final": self.a_fim.value(),
                "pacotes_por_angulo": self.n_pac.value(), "lado": self._lado, "com_referencia": self.ck_ref.isChecked(),
                "ganho_ref_dbi": self.g_ref.value(), "rssi_ref_dbm": self.rssi_ref.value(),
                "parar_ao_concluir": self.ck_parar.isChecked(), "banda_sigma": self.ck_sigma.isChecked()}

    def restaurar(self, e):
        self.a_ini.setValue(e.get("angulo_inicial", 0)); self.a_passo.setValue(e.get("passo", 30))
        self.a_fim.setValue(e.get("angulo_final", 330)); self.n_pac.setValue(e.get("pacotes_por_angulo", 100))
        self.lado.setCurrentIndex(0 if e.get("lado", "ul") == "ul" else 1)
        self.ck_ref.setChecked(e.get("com_referencia", True)); self.g_ref.setValue(e.get("ganho_ref_dbi", 12.5))
        self.rssi_ref.setValue(e.get("rssi_ref_dbm", -35)); self.ck_parar.setChecked(e.get("parar_ao_concluir", True))
        self.ck_sigma.setChecked(e.get("banda_sigma", True))


# ====================================================================== perda sistêmica
COLS_PS = [("Ângulo [°]", "angulo"), ("d [m]", "distancia_m"), ("Ptx [dBm]", "ptx_dbm"), ("G nó [dBi]", "g_ns_dbi"),
           ("MF [dB]", "mf_db"), ("X(t) [dB]", "x_db"), ("LSMA [dB]", "lsma_db"), ("Prx medida [dBm]", "prx_medida_dbm")]


class PainelPerdaSistemica(QWidget):
    def __init__(self, ctx: Contexto, assistente: PainelAssistente):
        super().__init__()
        self.ctx = ctx
        self.assist = assistente
        self.f = spin_float(1, 10000, 903, casas=3, sufixo="MHz")
        self.g_ref = spin_float(-30, 50, 12.5, sufixo="dBi")
        self.d = spin_float(0.1, 1e6, 5, sufixo="m")
        self.ptx = spin_float(-30, 40, 17, sufixo="dBm")
        self.g_ns = spin_float(-20, 40, 5, sufixo="dBi")
        self.lsma = spin_float(0, 50, 0.5, sufixo="dB")
        self.mf = spin_float(0, 50, 0, sufixo="dB")
        self.x = spin_float(-50, 50, 0, sufixo="dB")
        self.zona = spin_int(1, 20, 5)
        self.lb_fresnel = rotulo_valor()
        cfg = grupo_form("Parâmetros comuns (aplicados ao preencher)", [
            ("Frequência:", self.f), ("Ganho antena de referência:", self.g_ref), ("Distância:", self.d),
            ("Ptx do nó:", self.ptx), ("Ganho antena do nó:", self.g_ns), ("LSMA (cabos/conectores):", self.lsma),
            ("Margem de fading MF:", self.mf), ("X(t):", self.x), ("Zona de Fresnel n:", self.zona),
            ("Altura livre necessária (d1 = d2):", self.lb_fresnel)])
        cfg.setMaximumWidth(400)

        self.tab = QTableWidget(0, len(COLS_PS))
        self.tab.setHorizontalHeaderLabels([c[0] for c in COLS_PS])
        self.tab.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        bt_assist = QPushButton("Preencher com o assistente"); bt_assist.clicked.connect(self.preencher_assistente)
        bt_add = QPushButton("+ Linha"); bt_add.clicked.connect(lambda: self._add([0, *self._comuns(), -45]))
        bt_rem = QPushButton("− Remover"); bt_rem.clicked.connect(lambda: self.tab.removeRow(self.tab.currentRow()))
        bt_calc = QPushButton("Calcular"); bt_calc.clicked.connect(self.calcular)
        bt_exp = QPushButton("Exportar…"); bt_exp.clicked.connect(self.exportar)
        lb = QHBoxLayout()
        for b in (bt_assist, bt_add, bt_rem, bt_calc): lb.addWidget(b)
        lb.addStretch(1); lb.addWidget(bt_exp)
        self.res = TabelaDataFrame()
        nota = QLabel("A 1ª linha é a medida de referência. Prx_calc = Ptx + G_nó − L_EL − LSMA + G_gw + X(t) − MF; "
                      "Perda sistêmica = Prx_medida − Prx_calc; G_gw(θ) = G_ref + (Prx(θ) − Prx_ref).")
        nota.setWordWrap(True); nota.setStyleSheet("color:gray")
        dir_ = QVBoxLayout()
        dir_.addWidget(QLabel("Medidas (editável):")); dir_.addWidget(self.tab, 1); dir_.addLayout(lb)
        dir_.addWidget(QLabel("Resultado:")); dir_.addWidget(self.res, 1); dir_.addWidget(nota)
        lay = QHBoxLayout(self)
        lay.addWidget(cfg); lay.addLayout(dir_, 1)

        exemplo = [-35, -41, -43, -51, -45]
        for i, prx in enumerate(exemplo):
            self._add([30 * (i - 1) if i else 0, *self._comuns(), prx])
        for w in (self.f, self.d, self.zona):
            w.valueChanged.connect(self._fresnel)
        self._fresnel()
        self.calcular()

    def _comuns(self):
        return [self.d.value(), self.ptx.value(), self.g_ns.value(), self.mf.value(), self.x.value(), self.lsma.value()]

    def _fresnel(self):
        self.lb_fresnel.setText(f"{lb.raio_fresnel(self.d.value(), self.f.value() * 1e6, self.zona.value()):.2f} m")

    def _add(self, valores):
        r = self.tab.rowCount()
        self.tab.insertRow(r)
        for c, v in enumerate(valores):
            self.tab.setItem(r, c, QTableWidgetItem(f"{v:g}" if isinstance(v, (int, float)) else str(v)))

    def dataframe(self) -> pd.DataFrame:
        linhas = []
        for r in range(self.tab.rowCount()):
            reg = {}
            for c, (rot, k) in enumerate(COLS_PS):
                it = self.tab.item(r, c)
                try:
                    reg[k] = float((it.text() if it else "").replace(",", "."))
                except ValueError:
                    raise ValueError(f"Linha {r + 1}, coluna '{rot}': valor inválido.") from None
            linhas.append(reg)
        return pd.DataFrame(linhas, columns=[k for _, k in COLS_PS])

    def preencher_assistente(self):
        s = self.assist.sessao
        if not s or not any(e.concluida for e in s.etapas):
            erro(self, "Colete pelo menos uma etapa no assistente primeiro."); return
        self.tab.setRowCount(0)
        col = f"rssi_{s.lado}"
        for e in s.etapas:
            if e.concluida:
                ang = 0 if e.chave == ar.REFERENCIA else e.chave
                self._add([ang, *self._comuns(), round(float(e.amostras[col].mean()), 3)])
        self.g_ref.setValue(self.assist.g_ref.value())
        self.calcular()

    def calcular(self) -> pd.DataFrame | None:
        try:
            df = self.dataframe()
        except ValueError as e:
            erro(self, str(e)); return None
        t = rad.tabela_perda_sistemica(df, self.f.value() * 1e6, self.g_ref.value())
        if t.empty:
            self.res.definir(t); return t
        t = t.rename(columns={"angulo": "Ângulo [°]", "distancia_m": "d [m]", "ptx_dbm": "Ptx [dBm]",
                              "g_ns_dbi": "G nó [dBi]", "mf_db": "MF [dB]", "x_db": "X(t) [dB]", "lsma_db": "LSMA [dB]",
                              "prx_medida_dbm": "Prx medida [dBm]", "g_gw_dbi": "G gateway [dBi]", "lel_db": "L_EL [dB]",
                              "prx_calculada_dbm": "Prx calculada [dBm]", "perda_sistemica_db": "Perda sistêmica [dB]"})
        t.insert(0, "Medida", ["Referência"] + [str(i) for i in range(1, len(t))])
        self.res.definir(t)
        return t

    def exportar(self):
        t = self.calcular()
        if t is None or t.empty:
            return
        try:
            pasta = exp.exportar(self.ctx.raiz, "perda_sistemica", {
                "Perda sistêmica": t,
                "Parâmetros": exp.parametros_para_df({"Frequência [MHz]": self.f.value(),
                                                      "Ganho referência [dBi]": self.g_ref.value(),
                                                      "Zona de Fresnel": self.zona.value(),
                                                      "Altura livre [m]": self.lb_fresnel.text()})})
        except OSError as e:
            erro(self, f"Falha ao exportar: {e}"); return
        info_exportacao(self, self.ctx, pasta)

    def estado(self):
        return {"freq_mhz": self.f.value(), "g_ref_dbi": self.g_ref.value(), "distancia_m": self.d.value(),
                "ptx_dbm": self.ptx.value(), "g_ns_dbi": self.g_ns.value(), "lsma_db": self.lsma.value(),
                "mf_db": self.mf.value(), "x_db": self.x.value(), "zona": self.zona.value(),
                "tabela": [[(self.tab.item(r, c).text() if self.tab.item(r, c) else "") for c in range(len(COLS_PS))]
                           for r in range(self.tab.rowCount())]}

    def restaurar(self, e):
        for w, k in [(self.f, "freq_mhz"), (self.g_ref, "g_ref_dbi"), (self.d, "distancia_m"), (self.ptx, "ptx_dbm"),
                     (self.g_ns, "g_ns_dbi"), (self.lsma, "lsma_db"), (self.mf, "mf_db"), (self.x, "x_db"),
                     (self.zona, "zona")]:
            if k in e: w.setValue(e[k])
        if e.get("tabela"):
            self.tab.setRowCount(0)
            for linha in e["tabela"]:
                self._add(linha)
        self.calcular()


# ====================================================================== aba
class AbaCaracterizacao(QWidget):
    titulo = "Caracterização de antena"

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.assistente = PainelAssistente(ctx)
        self.perda = PainelPerdaSistemica(ctx, self.assistente)
        abas = QTabWidget()
        abas.addTab(self.assistente, "Diagrama de radiação (assistente guiado)")
        abas.addTab(self.perda, "Perda sistêmica")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(abas)

    def estado(self):
        return {"assistente": self.assistente.estado(), "perda": self.perda.estado()}

    def restaurar(self, e):
        self.assistente.restaurar(e.get("assistente", {}))
        self.perda.restaurar(e.get("perda", {}))
