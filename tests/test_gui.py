"""Teste de ponta a ponta da interface (offscreen), simulando o gateway gravando o log."""
from __future__ import annotations

import os

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("matplotlib")

import matplotlib  # noqa: E402

matplotlib.use("QtAgg")
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

CAB = "Time stamp,Contador,RSSI DL [dBm],SNR DL [dB],RSSI UL [dBm],SNR UL [dB]\n"


@pytest.fixture
def janela(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "cfg"))
    for nome in ("information", "critical", "warning"):
        monkeypatch.setattr(QMessageBox, nome, staticmethod(lambda *a, **k: QMessageBox.Close))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    from framework_lora.gui.janela import JanelaPrincipal
    w = JanelaPrincipal()
    w.ctx.definir_raiz(tmp_path)
    w.abas["gerencia"].cb_porta.setCurrentText("COM7")
    yield w, tmp_path, app
    w.ctx.monitor.parar()
    w.deleteLater()


def _escrever_log(caminho, linhas, inicio, rssi):
    novo = not caminho.exists()
    with open(caminho, "a", encoding="utf-8") as f:
        if novo:
            f.write(CAB)
        for i in range(inicio, inicio + linhas):
            f.write(f"Fri Sep  4 16:58:{i % 60:02d} 2026,{i},{rssi},5.5,{rssi - 2},6\n")


def test_gerencia_grava_parametros(janela):
    w, raiz, _ = janela
    g = w.abas["gerencia"]
    g.sp_medidas.setValue(250)
    g.sp_tempo.setValue(3)
    assert g.enviar(1)
    assert (raiz / "4_N4_Armazenamento/Parametros/PARAMETROS.txt").read_text() == "1\n250\n3.0\n7\n"
    g.parar_se_ativo()
    assert (raiz / "4_N4_Armazenamento/Parametros/PARAMETROS.txt").read_text().startswith("0\n")


def test_cliente_grava_limiar(janela):
    w, raiz, _ = janela
    c = w.abas["cliente"]
    c.spin.setValue(1500)
    assert "1550" in c.lb_hist.text()
    c.salvar()
    assert (raiz / "4_N4_Armazenamento/Parametros/parametros_cliente.txt").read_text() == "1500\n"


def test_assistente_diagrama_com_gateway_simulado(janela):
    w, raiz, app = janela
    pasta_logs = raiz / "4_N4_Armazenamento" / "Logs"
    pasta_logs.mkdir(parents=True)
    log = pasta_logs / "LOG_gerencia_2026_11_10.csv"
    survey = w.abas["site_survey"]
    survey._raiz_alterada(raiz)
    pa = w.abas["caracterizacao"].assistente
    pa.a_ini.setValue(0); pa.a_passo.setValue(90); pa.a_fim.setValue(270); pa.n_pac.setValue(5)
    pa.nova_sessao()
    s = pa.sessao
    assert [e.rotulo for e in s.etapas] == ["Referência", "0°", "90°", "180°", "270°"]

    rssi_ul = {"ref": -38, 0: -40, 90: -46, 180: -58, 270: -46}
    _escrever_log(log, 3, 1, -70)          # pacotes antigos, de antes da coleta
    w.ctx.monitor.verificar(forcar=True)
    contador = 4
    for chave in ["ref", 0, 90, 180, 270]:
        assert pa.bt_coletar.isEnabled()
        pa.coletar()
        par = (raiz / "4_N4_Armazenamento/Parametros/PARAMETROS.txt").read_text().splitlines()
        assert par[0] == "1" and par[1] == "5"
        _escrever_log(log, 3, contador, rssi_ul[chave] + 2)
        w.ctx.monitor.verificar(forcar=True)
        assert s.coletando and s.recebidos == 3
        _escrever_log(log, 4, contador + 3, rssi_ul[chave] + 2)   # passa de 5: só 5 são usados
        w.ctx.monitor.verificar(forcar=True)
        contador += 7
        assert not s.coletando
        assert (raiz / "4_N4_Armazenamento/Parametros/PARAMETROS.txt").read_text().startswith("0\n")
        if chave in ("ref", 0, 90):
            assert "Gire" in pa.lb_instr.text() or "ANTENA SOB TESTE" in pa.lb_instr.text()
    assert s.finalizada
    assert s.rssi_referencia() == pytest.approx(-38)
    assert pa.metr.ganho_max_dbi == pytest.approx(12.5 - 2)    # 0°: -40 vs ref -38
    assert pa.metr.fbr_db == pytest.approx(18)
    app.processEvents()

    # o site survey acompanhou o mesmo log ao vivo
    assert survey.res is not None and len(survey.res.dados) == 3 + 5 * 7
    pasta = None
    import framework_lora.gui.abas.caracterizacao as mod
    capturado = {}
    orig = mod.info_exportacao
    mod.info_exportacao = lambda parent, ctx, p: capturado.setdefault("p", p)
    try:
        pa.exportar()
    finally:
        mod.info_exportacao = orig
    pasta = capturado["p"]
    abas = pd.read_excel(pasta / "diagrama_radiacao.xlsx", sheet_name=None)
    assert {"Métricas", "Ganho por ângulo", "Etapas", "Pacotes coletados"} <= set(abas)
    assert len(abas["Pacotes coletados"]) == 25
    assert (pasta / "diagrama_polar.png").exists()

    # perda sistêmica preenchida a partir do assistente
    ps = w.abas["caracterizacao"].perda
    ps.preencher_assistente()
    t = ps.calcular()
    assert len(t) == 5 and t["Prx medida [dBm]"].iloc[0] == pytest.approx(-38)


def test_projeto_salvar_e_restaurar(janela):
    w, raiz, _ = janela
    w.abas["time_on_air"].payload.setValue(52)
    e = w.estado()
    w.abas["time_on_air"].payload.setValue(10)
    w.restaurar(e)
    assert w.abas["time_on_air"].payload.value() == 52
