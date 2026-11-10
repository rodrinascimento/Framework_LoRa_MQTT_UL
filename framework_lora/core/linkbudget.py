"""Cálculos de link budget (planilha 'Tópico 3.2 - Linkbudget').

Modelos:
    * Espaço livre (Friis):  L_EL = 20·log10(4·π·d / λ)
    * Log-distance:          L(d) = L_EL(d0) + 10·n·log10(d / d0)
    * Projeto por nó:        L_tot = L_EL(d0) + 10·n·log10(d/d0) + paredes·A_parede
                                     + armários·A_armario + máquinas·A_maquina
                                     + A_altura + margem de fading
    * Zona de Fresnel (d1 = d2 = d/2):  r_n = sqrt(n·λ·d / 4)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

import numpy as np

C_LUZ_PLANILHA = 3e8          # valor usado nas planilhas de link budget
C_LUZ = 299_792_458.0         # valor usado na planilha de perda sistêmica


def comprimento_onda(freq_hz: float, c: float = C_LUZ_PLANILHA) -> float:
    if freq_hz <= 0:
        raise ValueError("A frequência deve ser maior que zero.")
    return c / freq_hz


def perda_espaco_livre(dist_m, freq_hz: float, c: float = C_LUZ_PLANILHA):
    """Atenuação em espaço livre [dB]. Aceita escalar ou array de distâncias."""
    lam = comprimento_onda(freq_hz, c)
    d = np.asarray(dist_m, dtype=float)
    if np.any(d <= 0):
        raise ValueError("A distância deve ser maior que zero.")
    r = 20 * np.log10(4 * np.pi * d / lam)
    return float(r) if r.ndim == 0 else r


def perda_log_distance(dist_m, freq_hz: float, n: float, d0_m: float = 1.0,
                       c: float = C_LUZ_PLANILHA):
    if d0_m <= 0:
        raise ValueError("A distância de referência deve ser maior que zero.")
    d = np.asarray(dist_m, dtype=float)
    r = perda_espaco_livre(d0_m, freq_hz, c) + 10 * n * np.log10(d / d0_m)
    return float(r) if np.ndim(r) == 0 else r


def potencia_recebida(ptx_dbm: float, g_tx_dbi: float, g_rx_dbi: float, perda_db):
    return ptx_dbm + g_tx_dbi + g_rx_dbi - np.asarray(perda_db) if np.ndim(perda_db) else \
        ptx_dbm + g_tx_dbi + g_rx_dbi - perda_db


def raio_fresnel(dist_m: float, freq_hz: float, zona: int = 1, c: float = C_LUZ) -> float:
    """Raio da n-ésima zona de Fresnel no ponto médio do enlace [m]."""
    lam = comprimento_onda(freq_hz, c)
    return math.sqrt(zona * lam * dist_m / 4)


# ---------------------------------------------------------------- Projeto (vários nós)
@dataclass
class AtenuacoesAmbiente:
    parede_db: float = 16.0
    armario_db: float = 3.0
    maquina_db: float = 5.0
    margem_fading_db: float = 20.0


@dataclass
class NoSensor:
    nome: str
    distancia_m: float
    d0_m: float = 1.0
    n: float = 3.0
    ganho_dbi: float = 2.0
    paredes: float = 0
    armarios: float = 0
    maquinas: float = 0
    atenuacao_altura_db: float = 0.0
    # Medidas de campo (opcionais) para comparação
    prx_medida_dbm: float | None = None


@dataclass
class ResultadoNo:
    nome: str
    distancia_m: float
    perda_d0_db: float
    perda_total_db: float
    prx_dbm: float
    prx_medida_dbm: float | None = None
    perda_medida_db: float | None = None
    ajuste_db: float | None = None
    n_ajustado: float | None = None

    def como_dict(self):
        return asdict(self)


def calcular_no(no: NoSensor, freq_hz: float, ptx_dbm: float, g_gw_dbi: float,
                amb: AtenuacoesAmbiente) -> ResultadoNo:
    l0 = perda_espaco_livre(no.d0_m, freq_hz)
    extras = (no.paredes * amb.parede_db + no.armarios * amb.armario_db
              + no.maquinas * amb.maquina_db + no.atenuacao_altura_db + amb.margem_fading_db)
    ltot = l0 + 10 * no.n * math.log10(no.distancia_m / no.d0_m) + extras
    prx = ptx_dbm + g_gw_dbi + no.ganho_dbi - ltot
    res = ResultadoNo(no.nome, no.distancia_m, l0, ltot, prx)
    if no.prx_medida_dbm is not None:
        lmed = ptx_dbm + g_gw_dbi + no.ganho_dbi - no.prx_medida_dbm
        res.prx_medida_dbm = no.prx_medida_dbm
        res.perda_medida_db = lmed
        res.ajuste_db = lmed - ltot
        # expoente n que reproduziria a perda medida, mantidos os demais termos
        if no.distancia_m != no.d0_m:
            res.n_ajustado = (lmed - l0 - extras) / (10 * math.log10(no.distancia_m / no.d0_m))
    return res


def curva_prx(freq_hz, ptx_dbm, g_tx_dbi, g_rx_dbi, n, d0_m=1.0, d_max_m=1000.0, pontos=300):
    """Curvas Prx × distância para espaço livre e log-distance."""
    d = np.logspace(np.log10(max(d0_m, 0.1)), np.log10(max(d_max_m, d0_m * 1.01)), pontos)
    prx_el = ptx_dbm + g_tx_dbi + g_rx_dbi - perda_espaco_livre(d, freq_hz)
    prx_ld = ptx_dbm + g_tx_dbi + g_rx_dbi - perda_log_distance(d, freq_hz, n, d0_m)
    return d, prx_el, prx_ld
