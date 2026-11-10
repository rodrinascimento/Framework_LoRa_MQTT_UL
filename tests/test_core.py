"""Testes da lógica de cálculo, conferidos contra os valores salvos nas planilhas do repositório."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from framework_lora.core import (assistente_radiacao as ar, exportar, linkbudget as lb,
                                parametros as par, radiacao as rad, survey, toa)

RAIZ = Path(__file__).resolve().parents[1]
PLAN_LB = RAIZ / "Tópico 3.2 - Linkbudget 26 10 24 (1).xlsx"
PLAN_TOA = RAIZ / "LoRa Time on Air DataRate - MoT 20 Bytes.xlsx"
PLAN_PS = RAIZ / "Tópico 6.4 - Cálculo Perda Sistêmica.xlsx"

openpyxl = pytest.importorskip("openpyxl")


def _valores(caminho, aba):
    return openpyxl.load_workbook(caminho, data_only=True)[aba]


# ------------------------------------------------------------------ parâmetros
def test_parametros_serial_formato_identico_ao_script_original(tmp_path):
    p = par.ParametrosSerial.validar(1, "100", "0,2", "COM3")
    caminho = par.gravar_parametros_serial(tmp_path, p)
    assert caminho == tmp_path / "4_N4_Armazenamento" / "Parametros" / "PARAMETROS.txt"
    assert caminho.read_text() == "1\n100\n0.2\n3\n"
    lido = par.ler_parametros_serial(tmp_path)
    assert (lido.comando, lido.medidas, lido.tempo, lido.porta) == (1, 100, 0.2, "COM3")


def test_parametros_serial_linux_mantem_dispositivo(tmp_path):
    p = par.ParametrosSerial.validar(2, 10, 3, "/dev/ttyUSB0")
    assert p.para_texto() == "2\n10\n3.0\n/dev/ttyUSB0\n"


@pytest.mark.parametrize("medidas,tempo,porta", [("0", "1", "COM1"), ("10", "x", "COM1"),
                                                  ("10", "1", ""), ("10", "1", "Nenhuma COM encontrada")])
def test_parametros_serial_validacao(medidas, tempo, porta):
    with pytest.raises(par.ErroValidacao):
        par.ParametrosSerial.validar(1, medidas, tempo, porta)


def test_cliente_histerese_e_arquivo(tmp_path):
    assert par.limiar_desligar(2000) == 2050
    assert par.limiar_desligar(4090) == 4095
    par.gravar_limiar_cliente(tmp_path, 1234)
    assert (tmp_path / "4_N4_Armazenamento/Parametros/parametros_cliente.txt").read_text() == "1234\n"
    assert par.ler_limiar_cliente(tmp_path) == 1234
    assert par.ler_limiar_cliente(tmp_path / "nada") == 2000
    with pytest.raises(par.ErroValidacao):
        par.validar_limiar("5000")


# ------------------------------------------------------------------ link budget
def test_espaco_livre_e_log_distance_iguais_a_planilha():
    el = _valores(PLAN_LB, "Espaço Livre")
    assert lb.perda_espaco_livre(60000, 915e6) == pytest.approx(el["B12"].value, abs=1e-6)
    assert lb.potencia_recebida(17, 12, 2, el["B12"].value) == pytest.approx(el["B14"].value, abs=1e-6)
    ld = _valores(PLAN_LB, "Log-distance")
    assert lb.perda_log_distance(1000, 915e6, 4, 1) == pytest.approx(ld["B16"].value, abs=1e-6)


def test_projeto_por_no_igual_a_planilha():
    ws = _valores(PLAN_LB, "Projeto Fábrica de Sorvetes")
    amb = lb.AtenuacoesAmbiente(16, 3, 5, 20)
    lrc = lb.calcular_no(lb.NoSensor("LRC", 33, 1, 3.0, 2, 2, 1, 0), 903e6, 17, 2, amb)
    src = lb.calcular_no(lb.NoSensor("SRC", 40, 1, 3.2, 2, 3, 0, 0), 903e6, 17, 2, amb)
    assert lrc.perda_total_db == pytest.approx(ws["J11"].value, abs=1e-6)
    assert lrc.prx_dbm == pytest.approx(ws["K11"].value, abs=1e-6)
    assert src.perda_total_db == pytest.approx(ws["J12"].value, abs=1e-6)
    assert src.prx_dbm == pytest.approx(ws["K12"].value, abs=1e-6)


def test_ajuste_log_distance_com_medida():
    lbw = _valores(PLAN_LB, "Linkbudget")
    amb = lb.AtenuacoesAmbiente(16, 3, 5, 20)
    no = lb.NoSensor("LRC", 33, 1, 3.0, 2, 2, 1, 0, prx_medida_dbm=lbw["H4"].value)
    r = lb.calcular_no(no, 903e6, 17, 2, amb)
    assert r.perda_medida_db == pytest.approx(lbw["L4"].value, abs=1e-6)
    assert r.ajuste_db == pytest.approx(lbw["M4"].value, abs=1e-6)
    # o n ajustado reproduz a perda medida
    no2 = lb.NoSensor("LRC", 33, 1, r.n_ajustado, 2, 2, 1, 0)
    assert lb.calcular_no(no2, 903e6, 17, 2, amb).perda_total_db == pytest.approx(r.perda_medida_db)


def test_fresnel():
    ws = openpyxl.load_workbook(PLAN_PS)["Espaço Livre"]
    lam = 299792458 / 903e6
    assert lb.raio_fresnel(5, 903e6, 5) == pytest.approx(math.sqrt(5 * lam * 5 / 4))


# ------------------------------------------------------------------ time on air
def test_toa_semtech_valores_conhecidos():
    # Valores de referência do LoRa Calculator da Semtech (PL 20 B, preâmbulo 8, CRC on, header explícito)
    assert toa.calcular_toa(20, 7, 125, 1).toa_ms == pytest.approx(56.576, abs=1e-3)
    assert toa.calcular_toa(20, 12, 125, 1).toa_ms == pytest.approx(1318.912, abs=1e-3)
    assert toa.calcular_toa(20, 12, 125, 1).de == 1
    assert toa.calcular_toa(20, 12, 250, 1).de == 1   # Ts = 16,384 ms > 16 ms
    assert toa.calcular_toa(20, 11, 250, 1).de == 0


def test_toa_planilha_original_reproduzida():
    ws = _valores(PLAN_TOA, "Página1")
    for r in range(3, 75):
        sf, bw, cr, de, q = (ws[f"{c}{r}"].value for c in "BCELQ")
        assert toa.toa_planilha_original(20, sf, bw, cr, de) == pytest.approx(q, abs=1e-6)


def test_tabela_toa_tem_todas_combinacoes():
    t = toa.tabela_toa(20)
    assert len(t) == 6 * 3 * 4
    assert t[0].bitrate_nominal_bps == pytest.approx(5468.75)


# ------------------------------------------------------------------ site survey
@pytest.fixture(scope="module")
def log_sensor1():
    ws = _valores(PLAN_LB, "MedidasSensor1")
    linhas = [[c.value for c in r[:6]] for r in ws.iter_rows(min_row=2, max_row=ws.max_row)]
    df = pd.DataFrame(linhas, columns=survey.COLUNAS)
    return ws, survey._finalizar(df)


def test_survey_igual_a_planilha(log_sensor1):
    ws, df = log_sensor1
    res = survey.analisar(df, 10)
    d = res.dados
    assert d["mm_dl"][0] == pytest.approx(ws["N2"].value, abs=1e-6)
    assert d["dif_dl"][0] == pytest.approx(ws["Q2"].value, abs=1e-6)
    assert d["dp_dl"][0] == pytest.approx(ws["T2"].value, abs=1e-6)
    assert res.dl.rssi_max == ws["H3"].value and res.dl.rssi_min == ws["H5"].value
    assert res.dl.snr_max == ws["H7"].value and res.dl.snr_min == ws["H9"].value
    assert res.dl.desvio_padrao == pytest.approx(ws["H13"].value, abs=1e-6)
    assert res.ul.desvio_padrao == pytest.approx(ws["I13"].value, abs=1e-6)
    assert res.dl.desvio_padrao_medio == pytest.approx(ws["H15"].value, abs=1e-6)
    assert res.ul.desvio_padrao_medio == pytest.approx(ws["I15"].value, abs=1e-6)
    # a planilha calcula a média a partir da linha 11 (AVERAGE(N11:N990))
    assert d["mm_dl"][9:].mean() == pytest.approx(ws["H11"].value, abs=1e-6)
    assert d["mm_ul"][9:].mean() == pytest.approx(ws["I11"].value, abs=1e-6)
    assert res.pacotes_esperados == 1000 and res.pacotes_recebidos == 989


@pytest.mark.parametrize("texto", [
    "Time stamp,Contador,RSSI DL [dBm],SNR DL [dB],RSSI UL [dBm],SNR UL [dB]\n"
    "Fri Sep  4 16:58:36 2026,1,-65,5.75,-67.5,5\nFri Sep  4 16:58:37 2026,2,-64,5.5,-67,6\n",
    "Fri Sep  4 16:58:36 2026;1;-65;5,75;-67,5;5\nFri Sep  4 16:58:37 2026;2;-64;5,5;-67;6\n",
    "Fri Sep  4 16:58:36 2026\t1\t-65\t5.75\t-67.5\t5\nFri Sep  4 16:58:37 2026\t2\t-64\t5.5\t-67\t6\n",
    "Fri Sep  4 16:58:36 2026 1 -65 5.75 -67.5 5\nFri Sep  4 16:58:37 2026 2 -64 5.5 -67 6\n",
    "contador,rssi_ul,snr_ul,rssi_dl,snr_dl\n1,-67.5,5,-65,5.75\n2,-67,6,-64,5.5\n",
])
def test_importador_de_logs_varios_formatos(texto):
    df = survey.ler_log_texto(texto)
    assert len(df) == 2
    assert df["rssi_dl"].tolist() == [-65, -64]
    assert df["rssi_ul"].tolist() == [-67.5, -67]
    assert df["snr_dl"].tolist() == [5.75, 5.5]
    assert df["contador"].tolist() == [1, 2]


def test_log_mais_recente(tmp_path):
    import os, time
    (tmp_path / "a").mkdir()
    p1 = tmp_path / "a" / "LOG_gerencia_1.csv"; p1.write_text("x")
    p2 = tmp_path / "LOG_gerencia_2.txt"; p2.write_text("x")
    os.utime(p1, (time.time() - 100, time.time() - 100))
    (tmp_path / "outro.csv").write_text("x")
    assert survey.log_mais_recente(tmp_path) == p2


# ------------------------------------------------------------------ caracterização
def test_perda_sistemica_igual_a_planilha():
    ws = _valores(PLAN_PS, "Espaço Livre")
    linhas = []
    for r in range(4, 18):
        linhas.append({"angulo": ws[f"L{r}"].value, "distancia_m": ws[f"E{r}"].value,
                       "ptx_dbm": ws[f"F{r}"].value, "g_ns_dbi": ws[f"G{r}"].value,
                       "mf_db": ws[f"I{r}"].value, "x_db": ws[f"J{r}"].value,
                       "lsma_db": ws[f"K{r}"].value, "prx_medida_dbm": ws[f"O{r}"].value})
    t = rad.tabela_perda_sistemica(pd.DataFrame(linhas), 903e6, 12.5)
    for i, r in enumerate(range(4, 18)):
        assert t.loc[i, "lel_db"] == pytest.approx(ws[f"H{r}"].value, abs=1e-6)
        assert t.loc[i, "g_gw_dbi"] == pytest.approx(ws[f"M{r}"].value, abs=1e-6)
        assert t.loc[i, "prx_calculada_dbm"] == pytest.approx(ws[f"N{r}"].value, abs=1e-6)
        assert t.loc[i, "perda_sistemica_db"] == pytest.approx(ws[f"P{r}"].value, abs=1e-6)


def test_diagrama_dados_ficticios():
    resumo = rad.resumir_amostras(rad.gerar_amostras_ficticias(), -35.0, 12.5)
    m = rad.metricas(resumo)
    assert m.angulo_max == 0
    assert m.ganho_traseiro_dbi < m.ganho_max_dbi
    assert m.fbr_db == pytest.approx(20, abs=0.5)        # cos: +10 na frente, −10 atrás
    assert m.hpbw_graus == pytest.approx(87.445, abs=1e-3)   # mesmo valor do script original


def test_fbr_trata_volta_de_360_graus():
    # frente em 180°, traseira deve ser 0° (e não 330°)
    angs = np.arange(0, 360, 30)
    g = -np.abs(((angs - 180 + 180) % 360) - 180) / 10.0
    resumo = pd.DataFrame({"angulo": angs, "ganho_dbi": g})
    fbr, gf, gb, af, ab = rad.calcular_fbr(resumo)
    assert af == 180 and ab == 0
    # frente em 175°: alvo 355°, a amostra mais próxima é 0° (5°), não 330° (25°)
    resumo2 = pd.DataFrame({"angulo": [0, 90, 175, 270, 330], "ganho_dbi": [1, 2, 9, 2, 0]})
    assert rad.calcular_fbr(resumo2)[4] == 0


def test_hpbw_atravessando_zero():
    angs = np.arange(0, 360, 10)
    g = 10 - np.minimum(np.abs(angs - 350), 360 - np.abs(angs - 350)) / 10.0  # pico em 350°
    resumo = pd.DataFrame({"angulo": angs, "ganho_dbi": g})
    hpbw, te, td, gmax, _ = rad.calcular_hpbw(resumo)
    assert gmax == 10
    assert hpbw == pytest.approx(60.2, abs=0.01)
    assert te == pytest.approx(319.9, abs=0.01) and td == pytest.approx(20.1, abs=0.01)


# ------------------------------------------------------------------ assistente
def _log(n, rssi=-60.0, inicio=1):
    return pd.DataFrame({"timestamp": "", "contador": np.arange(inicio, inicio + n),
                         "rssi_dl": rssi, "snr_dl": 5.0, "rssi_ul": rssi, "snr_ul": 5.0})


def test_assistente_fluxo_completo(tmp_path):
    s = ar.SessaoRadiacao(ar.lista_angulos(0, 90, 270), pacotes_por_etapa=5)
    assert [e.rotulo for e in s.etapas] == ["Referência", "0°", "90°", "180°", "270°"]
    assert "REFERÊNCIA" in s.instrucao()
    log = tmp_path / "LOG.csv"
    total = _log(3)
    s.marcar_inicio(log, len(total))                  # 3 linhas antigas são ignoradas
    assert not s.atualizar(_log(6), log) and s.recebidos == 3
    assert s.atualizar(_log(8, -40), log)             # 5 novas → conclui referência
    assert s.rssi_referencia() == pytest.approx(-40)
    assert "ANTENA SOB TESTE" in s.instrucao()
    ganhos = {0: -40, 90: -45, 180: -60, 270: -45}
    n = 8
    for ang in (0, 90, 180, 270):
        assert s.atual.chave == ang
        s.marcar_inicio(log, n)
        df = pd.concat([_log(n), _log(5, ganhos[ang])], ignore_index=True)
        assert s.atualizar(df, log)
        n += 5
        if ang != 270:
            assert "Gire" in s.instrucao()
    assert s.finalizada and s.progresso == (5, 5)
    amostras = s.amostras_angulo_rssi()
    assert len(amostras) == 20
    resumo = rad.resumir_amostras(amostras, s.rssi_referencia(), 12.5)
    assert resumo.loc[resumo.angulo == 180, "ganho_dbi"].item() == pytest.approx(-7.5)


def test_assistente_log_novo_conta_inteiro_e_refazer(tmp_path):
    s = ar.SessaoRadiacao([0, 180], pacotes_por_etapa=4, com_referencia=False)
    s.marcar_inicio(tmp_path / "LOG_1.csv", 50)
    assert s.atualizar(_log(4), tmp_path / "LOG_2.csv")   # gateway abriu um log novo
    assert s.atual.chave == 180
    s.refazer(0)
    assert s.atual.chave == 0 and not s.etapas[0].concluida


def test_exportacao_organizada(tmp_path):
    res = survey.analisar(_log(30), 10)
    pasta = exportar.exportar(tmp_path, "site_survey", {"Resumo": res.tabela_resumo(),
                              "Dados": survey.dados_para_exportar(res)}, nome="LOG teste")
    assert pasta.parent.parent == tmp_path / "4_N4_Armazenamento" / "Exportacoes"
    assert (pasta / "site_survey.xlsx").exists() and (pasta / "Resumo.csv").exists()
    abas = pd.read_excel(pasta / "site_survey.xlsx", sheet_name=None)
    assert set(abas) == {"Resumo", "Dados"} and len(abas["Dados"]) == 30


def test_volta_completa():
    assert rad.volta_completa(range(0, 360, 30))
    assert not rad.volta_completa([0, 30, 60, 90, 120, 150, 180])
    assert rad.volta_completa([0, 90, 180, 270])
    assert not rad.volta_completa([0, 90])
