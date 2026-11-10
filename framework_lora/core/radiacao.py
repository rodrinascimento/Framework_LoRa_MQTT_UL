"""Caracterização de antena: perda sistêmica e diagrama de radiação.

Unifica os scripts 'Diagrama de Radiacao HPBW*.py' e a planilha 'Tópico 6.4 - Cálculo Perda
Sistêmica'.

Calibração por substituição (mesma fórmula do script e da coluna M da planilha):
    G_aut(θ) = G_ref + (RSSI(θ) − RSSI_ref)

Perda sistêmica de uma medida:
    Prx_calc = Ptx + G_ns − L_EL − LSMA + G_gw + X(t) − MF
    Perda    = Prx_medida − Prx_calc
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .linkbudget import perda_espaco_livre, C_LUZ


# ---------------------------------------------------------------- perda sistêmica
@dataclass
class MedidaSistemica:
    distancia_m: float
    ptx_dbm: float
    g_ns_dbi: float
    lsma_db: float
    g_gw_dbi: float
    prx_medida_dbm: float
    mf_db: float = 0.0
    x_db: float = 0.0


def perda_sistemica(m: MedidaSistemica, freq_hz: float) -> dict:
    lel = perda_espaco_livre(m.distancia_m, freq_hz, c=C_LUZ)
    prx = m.ptx_dbm + m.g_ns_dbi - lel - m.lsma_db + m.g_gw_dbi + m.x_db - m.mf_db
    return {"lel_db": lel, "prx_calculada_dbm": prx, "perda_sistemica_db": m.prx_medida_dbm - prx}


def tabela_perda_sistemica(df: pd.DataFrame, freq_hz: float, g_ref_dbi: float) -> pd.DataFrame:
    """Recebe colunas: angulo, distancia_m, ptx_dbm, g_ns_dbi, mf_db, x_db, lsma_db,
    prx_medida_dbm. A primeira linha é a referência (antena de ganho conhecido g_ref_dbi).
    Devolve a tabela com L_EL, ganho da antena por substituição, Prx calculada e perda."""
    if df.empty:
        return df.copy()
    out = df.copy().reset_index(drop=True)
    prx_ref = float(out.loc[0, "prx_medida_dbm"])
    out["g_gw_dbi"] = g_ref_dbi + (out["prx_medida_dbm"] - prx_ref)
    out.loc[0, "g_gw_dbi"] = g_ref_dbi
    out["lel_db"] = perda_espaco_livre(out["distancia_m"].to_numpy(float), freq_hz, c=C_LUZ)
    out["prx_calculada_dbm"] = (out["ptx_dbm"] + out["g_ns_dbi"] - out["lel_db"] - out["lsma_db"]
                                + out["g_gw_dbi"] + out["x_db"] - out["mf_db"])
    out["perda_sistemica_db"] = out["prx_medida_dbm"] - out["prx_calculada_dbm"]
    return out


# ---------------------------------------------------------------- diagrama de radiação
@dataclass
class MetricasRadiacao:
    ganho_max_dbi: float
    angulo_max: float
    nivel_corte_dbi: float
    hpbw_graus: float
    theta_esq: float | None
    theta_dir: float | None
    fbr_db: float
    ganho_traseiro_dbi: float
    angulo_traseiro: float

    def como_dict(self):
        return asdict(self)


def volta_completa(angulos) -> bool:
    """True quando os ângulos cobrem a volta inteira com espaçamento regular (ex.: 0…330 de 30 em 30)."""
    a = np.sort(np.unique(np.asarray(angulos, float) % 360))
    if len(a) < 3:
        return False
    passos = np.diff(np.r_[a, a[0] + 360])
    return passos.max() <= 1.5 * np.median(passos[:-1]) + 1e-9


def resumir_amostras(df: pd.DataFrame, rssi_ref: float, ganho_ref: float) -> pd.DataFrame:
    """Agrupa amostras (colunas 'angulo', 'rssi') por ângulo e aplica a calibração."""
    if not {"angulo", "rssi"}.issubset(df.columns):
        raise ValueError("O arquivo precisa ter as colunas 'angulo' e 'rssi'.")
    d = df[["angulo", "rssi"]].apply(pd.to_numeric, errors="coerce").dropna()
    if d.empty:
        raise ValueError("Nenhuma amostra válida de ângulo e RSSI.")
    d["angulo"] = d["angulo"] % 360
    r = d.groupby("angulo")["rssi"].agg(["mean", "std", "count"]).reset_index()
    r = r.sort_values("angulo").reset_index(drop=True)
    r["std"] = r["std"].fillna(0.0)
    r["ganho_dbi"] = ganho_ref + (r["mean"] - rssi_ref)
    return r


def _interp(th_a, g_a, th_b, g_b, g_corte):
    if g_b == g_a:
        return th_a
    return th_a + (th_b - th_a) * (g_corte - g_a) / (g_b - g_a)


def _cruzamento(df, idx_max, passo, g_corte):
    n = len(df)
    for i in range(n):
        a = (idx_max + passo * i) % n
        b = (idx_max + passo * (i + 1)) % n
        g1, g2 = df.loc[a, "ganho_dbi"], df.loc[b, "ganho_dbi"]
        if g1 >= g_corte >= g2:
            th1, th2 = df.loc[a, "angulo"], df.loc[b, "angulo"]
            # desenrola a passagem por 0°/360°
            if passo > 0 and th2 < th1:
                th2 += 360
            if passo < 0 and th2 > th1:
                th2 -= 360
            return _interp(th1, g1, th2, g2, g_corte) % 360
    return None


def calcular_hpbw(resumo: pd.DataFrame):
    df = resumo.sort_values("angulo").reset_index(drop=True)
    idx_max = int(df["ganho_dbi"].idxmax())
    g_max = float(df.loc[idx_max, "ganho_dbi"])
    g_corte = g_max - 3.01
    th_esq = _cruzamento(df, idx_max, -1, g_corte)
    th_dir = _cruzamento(df, idx_max, +1, g_corte)
    if th_esq is not None and th_dir is not None:
        hpbw = (th_dir - th_esq) % 360
    else:
        hpbw = float("nan")
    return hpbw, th_esq, th_dir, g_max, g_corte


def _dist_angular(a, b):
    d = np.abs(np.asarray(a, float) - b) % 360
    return np.minimum(d, 360 - d)


def calcular_fbr(resumo: pd.DataFrame):
    df = resumo.reset_index(drop=True)
    idx_max = int(df["ganho_dbi"].idxmax())
    g_front = float(df.loc[idx_max, "ganho_dbi"])
    ang_front = float(df.loc[idx_max, "angulo"])
    alvo = (ang_front + 180) % 360
    idx_back = int(np.argmin(_dist_angular(df["angulo"], alvo)))
    g_back = float(df.loc[idx_back, "ganho_dbi"])
    return g_front - g_back, g_front, g_back, ang_front, float(df.loc[idx_back, "angulo"])


def metricas(resumo: pd.DataFrame) -> MetricasRadiacao:
    if len(resumo) < 3:
        raise ValueError("São necessários pelo menos 3 ângulos para calcular HPBW e FBR.")
    hpbw, th_e, th_d, g_max, g_corte = calcular_hpbw(resumo)
    fbr, g_front, g_back, ang_front, ang_back = calcular_fbr(resumo)
    return MetricasRadiacao(g_max, ang_front, g_corte, hpbw, th_e, th_d, fbr, g_back, ang_back)


def gerar_amostras_ficticias(n_por_angulo: int = 1000, passo: int = 30, semente: int = 42) -> pd.DataFrame:
    angulos = np.arange(0, 360, passo)
    ideal = -48 + 10 * np.cos(np.radians(angulos))
    rng = np.random.default_rng(semente)
    linhas = [(a, round(float(v), 2)) for a, r in zip(angulos, ideal)
              for v in rng.normal(r, 0.8, n_por_angulo)]
    return pd.DataFrame(linhas, columns=["angulo", "rssi"])


def amostras_de_logs(logs: dict[float, pd.DataFrame], lado: str = "ul") -> pd.DataFrame:
    """Monta o DataFrame angulo,rssi a partir de logs do gateway (um log por ângulo)."""
    partes = []
    for ang, df in logs.items():
        r = df[f"rssi_{lado}"].dropna()
        partes.append(pd.DataFrame({"angulo": float(ang), "rssi": r.to_numpy()}))
    if not partes:
        raise ValueError("Nenhum log foi associado a um ângulo.")
    return pd.concat(partes, ignore_index=True)
