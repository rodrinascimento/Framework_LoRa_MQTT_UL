"""Aba Gerência (Serial): substitui Setup_Parametros_Serial.py."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout,
                               QWidget)

from ...core import parametros as par
from ..comum import Contexto, grupo_form, rotulo_valor, spin_float, spin_int


def listar_portas() -> list[str]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [p.device for p in list_ports.comports()]


CORES = {par.Comando.INICIAR: "#1f6feb", par.Comando.PAUSAR: "#d29922", par.Comando.PARAR: "#da3633"}


class AbaGerencia(QWidget):
    titulo = "Gerência (Serial)"

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        ctx.gerencia = self

        # --- porta
        self.cb_porta = QComboBox()
        self.cb_porta.setEditable(True)
        self.cb_porta.setMinimumWidth(180)
        bt_portas = QPushButton("Atualizar portas")
        bt_portas.clicked.connect(self.atualizar_portas)
        linha_porta = QHBoxLayout()
        linha_porta.addWidget(self.cb_porta, 1)
        linha_porta.addWidget(bt_portas)
        w_porta = QWidget(); w_porta.setLayout(linha_porta)

        # --- tempo e medidas
        self.sp_tempo = spin_float(0.01, 3600, 0.2, casas=2, passo=0.1, sufixo="s")
        bt_curta = QPushButton(f"Short distance ({int(par.TEMPO_SHORT_DISTANCE * 1000)} ms)")
        bt_curta.clicked.connect(lambda: self.sp_tempo.setValue(par.TEMPO_SHORT_DISTANCE))
        bt_longa = QPushButton(f"Long distance ({par.TEMPO_LONG_DISTANCE:g} s)")
        bt_longa.clicked.connect(lambda: self.sp_tempo.setValue(par.TEMPO_LONG_DISTANCE))
        lt = QHBoxLayout(); lt.addWidget(self.sp_tempo); lt.addWidget(bt_curta); lt.addWidget(bt_longa)
        w_tempo = QWidget(); w_tempo.setLayout(lt)
        self.sp_medidas = spin_int(1, 1_000_000, 100)

        cfg = grupo_form("Parâmetros da medida", [
            ("Porta serial do gateway:", w_porta),
            ("Tempo entre pacotes:", w_tempo),
            ("Número de medidas:", self.sp_medidas),
        ])

        # --- comandos
        g_cmd = QGroupBox("Comandos de execução")
        gl = QGridLayout(g_cmd)
        botoes = [("▶  INICIAR", par.Comando.INICIAR, "#238636"), ("⏸  PAUSAR", par.Comando.PAUSAR, "#d29922"),
                  ("■  PARAR", par.Comando.PARAR, "#da3633"), ("⟳  ATUALIZAR", None, "#1f6feb")]
        for i, (txt, cmd, cor) in enumerate(botoes):
            b = QPushButton(txt)
            b.setMinimumHeight(40)
            b.setStyleSheet(f"QPushButton{{background:{cor};color:white;font-weight:bold;border-radius:6px}}"
                            f"QPushButton:hover{{background:{cor}cc}}")
            b.clicked.connect(self.atualizar if cmd is None else (lambda _=False, c=cmd: self.enviar(c)))
            gl.addWidget(b, 0, i)

        self.lb_status = QLabel("AGUARDANDO COMANDO")
        self.lb_status.setAlignment(Qt.AlignCenter)
        self.lb_status.setStyleSheet("font-size:16px;font-weight:bold;color:gray;padding:6px")
        gl.addWidget(self.lb_status, 1, 0, 1, 4)

        # --- acompanhamento ao vivo
        g_vivo = QGroupBox("Acompanhamento ao vivo (log do gateway)")
        lv = QGridLayout(g_vivo)
        self.lb_log = rotulo_valor("nenhum log encontrado")
        self.lb_log.setWordWrap(True)
        self.lb_pacotes = rotulo_valor()
        self.lb_rssi = rotulo_valor()
        self.lb_snr = rotulo_valor()
        self.pb = QProgressBar()
        self.pb.setFormat("%v / %m pacotes")
        for i, (r, w) in enumerate([("Arquivo:", self.lb_log), ("Pacotes:", self.lb_pacotes),
                                    ("Último RSSI DL / UL:", self.lb_rssi), ("Último SNR DL / UL:", self.lb_snr)]):
            lv.addWidget(QLabel(r), i, 0)
            lv.addWidget(w, i, 1)
        lv.addWidget(self.pb, 4, 0, 1, 2)

        # --- arquivo gravado
        g_arq = QGroupBox("Conteúdo de PARAMETROS.txt")
        la = QVBoxLayout(g_arq)
        self.txt_arquivo = QPlainTextEdit()
        self.txt_arquivo.setReadOnly(True)
        self.txt_arquivo.setMaximumHeight(110)
        self.lb_caminho = QLabel()
        self.lb_caminho.setStyleSheet("color:gray")
        self.lb_caminho.setWordWrap(True)
        la.addWidget(self.txt_arquivo)
        la.addWidget(self.lb_caminho)

        lay = QVBoxLayout(self)
        self.setMaximumWidth(980)
        lay.addWidget(cfg)
        lay.addWidget(g_cmd)
        lay.addWidget(g_vivo)
        lay.addWidget(g_arq)
        lay.addStretch(1)

        self.atualizar_portas()
        self._carregar_arquivo()
        ctx.raiz_alterada.connect(lambda _: self._carregar_arquivo())
        ctx.monitor.atualizado.connect(self._log_atualizado)

    # ------------------------------------------------------------ ações
    def atualizar_portas(self):
        atual = self.cb_porta.currentText()
        portas = listar_portas()
        self.cb_porta.clear()
        self.cb_porta.addItems(portas or [])
        if atual:
            self.cb_porta.setCurrentText(atual)
        elif not portas:
            self.cb_porta.setPlaceholderText("Nenhuma COM encontrada")
        self.ctx.log(f"Portas seriais: {', '.join(portas) if portas else 'nenhuma encontrada'}")

    def enviar(self, comando: int, medidas: int | None = None, silencioso: bool = False) -> bool:
        """Grava PARAMETROS.txt. Usado pelos botões e pelo assistente de diagrama."""
        try:
            p = par.ParametrosSerial.validar(comando, medidas or self.sp_medidas.value(),
                                             self.sp_tempo.value(), self.cb_porta.currentText())
            caminho = par.gravar_parametros_serial(self.ctx.raiz, p)
        except par.ErroValidacao as e:
            if not silencioso:
                QMessageBox.critical(self, "Erro", str(e))
            self.ctx.log(str(e), "erro")
            return False
        except OSError as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível gravar o arquivo de parâmetros: {e}")
            self.ctx.log(f"Falha ao gravar PARAMETROS.txt: {e}", "erro")
            return False
        cmd = par.Comando(comando)
        self.ctx.ultimo_comando = int(cmd)
        self.lb_status.setText(cmd.rotulo)
        self.lb_status.setStyleSheet(f"font-size:16px;font-weight:bold;color:{CORES[cmd]};padding:6px")
        self.pb.setMaximum(p.medidas)
        self._mostrar_arquivo(caminho)
        self.ctx.log(f"Comando {cmd.rotulo} enviado ({p.medidas} medidas, {p.tempo:g} s, porta {p.porta})",
                     "ok" if cmd != par.Comando.PARAR else "aviso")
        self.ctx.comando_enviado.emit(int(cmd))
        return True

    def atualizar(self):
        if self.enviar(par.Comando.INICIAR):
            QMessageBox.information(self, "Atualização",
                                    "Parâmetros atualizados com sucesso para o teste em andamento!")

    def parar_se_ativo(self):
        if self.ctx.ultimo_comando not in (None, int(par.Comando.PARAR)):
            self.enviar(par.Comando.PARAR, silencioso=True)

    # ------------------------------------------------------------ estado
    def _mostrar_arquivo(self, caminho):
        try:
            self.txt_arquivo.setPlainText(caminho.read_text(encoding="utf-8"))
        except OSError:
            self.txt_arquivo.setPlainText("")
        self.lb_caminho.setText(str(caminho))

    def _carregar_arquivo(self):
        p = par.ler_parametros_serial(self.ctx.raiz)
        caminho = self.ctx.raiz / par.PASTA_ARMAZENAMENTO / par.SUBPASTA_PARAMETROS / par.ARQUIVO_PARAMETROS
        if p:
            self.sp_medidas.setValue(p.medidas)
            self.sp_tempo.setValue(p.tempo)
            self.cb_porta.setCurrentText(p.porta)
            self.pb.setMaximum(p.medidas)
        self._mostrar_arquivo(caminho)

    def _log_atualizado(self, df, caminho):
        self.lb_log.setText(str(caminho))
        n = len(df)
        self.lb_pacotes.setText(str(n))
        self.pb.setValue(min(n, self.pb.maximum()))
        if n:
            u = df.iloc[-1]
            self.lb_rssi.setText(f"{u.rssi_dl:g} dBm / {u.rssi_ul:g} dBm")
            self.lb_snr.setText(f"{u.snr_dl:g} dB / {u.snr_ul:g} dB")

    def estado(self) -> dict:
        return {"porta": self.cb_porta.currentText(), "tempo": self.sp_tempo.value(),
                "medidas": self.sp_medidas.value()}

    def restaurar(self, e: dict):
        if "porta" in e:
            self.cb_porta.setCurrentText(e["porta"])
        self.sp_tempo.setValue(e.get("tempo", self.sp_tempo.value()))
        self.sp_medidas.setValue(e.get("medidas", self.sp_medidas.value()))
