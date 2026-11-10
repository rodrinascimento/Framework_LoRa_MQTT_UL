"""Time on Air LoRa (planilha 'LoRa Time on Air DataRate - MoT 20 Bytes').

Fórmula da Semtech (AN1200.13 / datasheet SX127x):
    Ts        = 2^SF / BW
    T_pream   = (n_preamb + 4,25) · Ts
    n_payload = 8 + max(ceil((8·PL − 4·SF + 28 + 16·CRC − 20·IH) / (4·(SF − 2·DE))) · (CR + 4), 0)
    ToA       = T_pream + n_payload · Ts

CRC e IH são 0 ou 1. DE (Low Data Rate Optimization) é ligado automaticamente quando
Ts > 16 ms, o que inclui SF11/125 kHz, SF12/125 kHz e SF12/250 kHz.

A planilha original usava (8 + 4,5)·Ts no preâmbulo e CRC = 2. Os parâmetros
`extra_preambulo` e `crc` permitem reproduzir esses valores para comparação.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from itertools import product

SFS = (7, 8, 9, 10, 11, 12)
BWS_KHZ = (125, 250, 500)
CRS = (1, 2, 3, 4)  # 4/5 .. 4/8


@dataclass
class ResultadoToA:
    payload_bytes: int
    sf: int
    bw_khz: float
    cr: int
    de: int
    t_simbolo_ms: float
    t_preambulo_ms: float
    n_simbolos_payload: int
    t_payload_ms: float
    toa_ms: float
    bitrate_nominal_bps: float
    taxa_simbolos_sps: float
    taxa_efetiva_bps: float

    @property
    def cr_texto(self) -> str:
        return f"4/{4 + self.cr}"

    def como_dict(self):
        d = asdict(self)
        d["cr_texto"] = self.cr_texto
        return d


def ldro_automatico(sf: int, bw_khz: float) -> int:
    return 1 if (2 ** sf) / (bw_khz * 1000) > 0.016 else 0


def calcular_toa(payload_bytes: int, sf: int, bw_khz: float, cr: int = 1,
                 n_preambulo: int = 8, crc: int = 1, header_implicito: int = 0,
                 de: int | None = None, extra_preambulo: float = 4.25) -> ResultadoToA:
    if not 6 <= sf <= 12:
        raise ValueError("SF deve estar entre 6 e 12.")
    if bw_khz <= 0:
        raise ValueError("A largura de banda deve ser maior que zero.")
    if cr not in CRS:
        raise ValueError("CR deve ser 1 (4/5), 2 (4/6), 3 (4/7) ou 4 (4/8).")
    if payload_bytes < 0:
        raise ValueError("O payload não pode ser negativo.")
    if de is None:
        de = ldro_automatico(sf, bw_khz)
    bw = bw_khz * 1000.0
    ts = (2 ** sf) / bw                     # s
    t_pre = (n_preambulo + extra_preambulo) * ts
    num = 8 * payload_bytes - 4 * sf + 28 + 16 * crc - 20 * header_implicito
    den = 4 * (sf - 2 * de)
    n_pay = 8 + max(math.ceil(num / den) * (cr + 4), 0)
    t_pay = n_pay * ts
    toa = t_pre + t_pay
    rb = sf * (bw / 2 ** sf) * (4 / (4 + cr))
    return ResultadoToA(
        payload_bytes=payload_bytes, sf=sf, bw_khz=bw_khz, cr=cr, de=de,
        t_simbolo_ms=ts * 1e3, t_preambulo_ms=t_pre * 1e3, n_simbolos_payload=n_pay,
        t_payload_ms=t_pay * 1e3, toa_ms=toa * 1e3, bitrate_nominal_bps=rb,
        taxa_simbolos_sps=bw / 2 ** sf,
        taxa_efetiva_bps=(8 * payload_bytes / toa) if toa > 0 else 0.0,
    )


def toa_planilha_original(payload_bytes: int, sf: int, bw_khz: float, cr: int, de: int) -> float:
    """ToA [ms] exatamente como a planilha antiga calculava, só para comparação.

    Diferenças em relação à Semtech: preâmbulo (8 + 4,5) em vez de (8 + 4,25), CRC = 2
    (32 bits) e o arredondamento para cima aplicado depois de multiplicar por (CR + 4).
    """
    ts = (2 ** sf) / bw_khz  # ms
    n = 8 + max(math.ceil((8 * payload_bytes - 4 * sf + 28 + 32) / (4 * (sf - 2 * de)) * (cr + 4)), 0)
    return (8 + 4.5 + n) * ts


def tabela_toa(payload_bytes: int, n_preambulo: int = 8, crc: int = 1, header_implicito: int = 0,
               sfs=SFS, bws=BWS_KHZ, crs=CRS, **kw) -> list[ResultadoToA]:
    """Todas as combinações SF × BW × CR (mesma ordem da planilha)."""
    return [calcular_toa(payload_bytes, sf, bw, cr, n_preambulo, crc, header_implicito, **kw)
            for sf, bw, cr in product(sfs, bws, crs)]


def tempo_minimo_entre_pacotes(toa_ms: float, duty_cycle: float) -> float:
    """Intervalo mínimo [s] entre transmissões para respeitar um duty cycle (ex.: 0,01)."""
    if not 0 < duty_cycle <= 1:
        raise ValueError("Duty cycle deve estar entre 0 e 1.")
    return toa_ms / 1000.0 / duty_cycle
