"""Assistente guiado do diagrama de radiação.

Fluxo:
    1. (opcional) Referência: antena de ganho conhecido apontada para o nó → coleta N pacotes
       e define RSSI_ref como a média.
    2. Para cada ângulo (ex.: 0°, 30°, …, 330°): o usuário posiciona a antena sob teste,
       o assistente inicia a coleta, conta os pacotes novos que chegam ao log do gateway e,
       ao atingir N, pede para girar a antena para o próximo ângulo.
    3. Ao fim, monta as amostras (angulo, rssi), calcula G(θ), HPBW e FBR.

A lógica não depende da interface: a GUI chama `marcar_inicio()` ao iniciar cada coleta e
`atualizar(df_log, caminho)` sempre que o log muda.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

REFERENCIA = "referencia"


@dataclass
class Etapa:
    chave: str | float            # REFERENCIA ou ângulo em graus
    amostras: pd.DataFrame | None = None

    @property
    def concluida(self) -> bool:
        return self.amostras is not None and not self.amostras.empty

    @property
    def rotulo(self) -> str:
        return "Referência" if self.chave == REFERENCIA else f"{self.chave:g}°"


def lista_angulos(inicio: float = 0, passo: float = 30, fim: float = 330) -> list[float]:
    if passo <= 0:
        raise ValueError("O passo deve ser maior que zero.")
    if fim < inicio:
        raise ValueError("O ângulo final deve ser maior ou igual ao inicial.")
    angs = list(np.arange(inicio, fim + 1e-9, passo))
    return [float(a % 360) for a in angs]


@dataclass
class SessaoRadiacao:
    angulos: list[float]
    pacotes_por_etapa: int = 100
    lado: str = "ul"                       # qual RSSI usar: 'ul' ou 'dl'
    com_referencia: bool = True
    etapas: list[Etapa] = field(default_factory=list)
    indice: int = 0
    # estado da coleta em andamento
    _log_base: Path | None = None
    _linhas_base: int = 0
    coletando: bool = False
    recebidos: int = 0

    def __post_init__(self):
        if self.pacotes_por_etapa < 1:
            raise ValueError("O número de pacotes por etapa deve ser pelo menos 1.")
        if self.lado not in ("ul", "dl"):
            raise ValueError("Lado deve ser 'ul' ou 'dl'.")
        if not self.etapas:
            chaves = ([REFERENCIA] if self.com_referencia else []) + list(self.angulos)
            self.etapas = [Etapa(c) for c in chaves]

    # ------------------------------------------------------------ navegação
    @property
    def atual(self) -> Etapa | None:
        return self.etapas[self.indice] if self.indice < len(self.etapas) else None

    @property
    def finalizada(self) -> bool:
        return all(e.concluida for e in self.etapas)

    @property
    def progresso(self) -> tuple[int, int]:
        return sum(e.concluida for e in self.etapas), len(self.etapas)

    def instrucao(self) -> str:
        e = self.atual
        if e is None:
            return "Todas as etapas foram concluídas. Calcule e exporte o diagrama."
        if e.chave == REFERENCIA:
            return ("Monte a ANTENA DE REFERÊNCIA (ganho conhecido) no gateway, alinhada com o nó "
                    "sensor, e clique em 'Coletar'.")
        if self.indice == (1 if self.com_referencia else 0):
            return (f"Monte a ANTENA SOB TESTE e aponte para {e.chave:g}° (direção do nó sensor). "
                    "Clique em 'Coletar'.")
        return f"Gire a antena sob teste para {e.chave:g}° e clique em 'Coletar'."

    def ir_para(self, indice: int):
        if not 0 <= indice < len(self.etapas):
            raise IndexError("Etapa inexistente.")
        self.cancelar()
        self.indice = indice

    def avancar(self):
        self.cancelar()
        pend = [i for i, e in enumerate(self.etapas) if not e.concluida]
        depois = [i for i in pend if i > self.indice]
        self.indice = depois[0] if depois else (pend[0] if pend else len(self.etapas))

    def refazer(self, indice: int | None = None):
        i = self.indice if indice is None else indice
        self.etapas[i].amostras = None
        self.ir_para(i)

    # ------------------------------------------------------------ coleta
    def marcar_inicio(self, caminho_log: Path | None, linhas_atuais: int):
        """Registra o estado do log no instante em que a coleta começa."""
        self._log_base = Path(caminho_log) if caminho_log else None
        self._linhas_base = int(linhas_atuais)
        self.coletando = True
        self.recebidos = 0

    def cancelar(self):
        self.coletando = False
        self.recebidos = 0

    def novas_linhas(self, df_log: pd.DataFrame, caminho_log: Path | None) -> pd.DataFrame:
        """Linhas que chegaram depois de `marcar_inicio`. Um log novo conta por inteiro."""
        if caminho_log is not None and self._log_base is not None and Path(caminho_log) == self._log_base:
            return df_log.iloc[self._linhas_base:]
        return df_log if caminho_log is not None else df_log.iloc[0:0]

    def atualizar(self, df_log: pd.DataFrame, caminho_log: Path | None) -> bool:
        """Atualiza a contagem. Devolve True quando a etapa atual acabou de ser concluída."""
        if not self.coletando or self.atual is None:
            return False
        novas = self.novas_linhas(df_log, caminho_log)
        col = f"rssi_{self.lado}"
        novas = novas[novas[col].notna()] if col in novas else novas.iloc[0:0]
        self.recebidos = len(novas)
        if self.recebidos >= self.pacotes_por_etapa:
            self.concluir(novas.iloc[: self.pacotes_por_etapa])
            return True
        return False

    def concluir(self, amostras: pd.DataFrame):
        """Conclui a etapa atual com as amostras dadas (também usado para importar um log)."""
        if self.atual is None:
            return
        if amostras is None or amostras.empty:
            raise ValueError("Nenhuma amostra para concluir a etapa.")
        self.atual.amostras = amostras.reset_index(drop=True).copy()
        self.coletando = False
        self.avancar()

    # ------------------------------------------------------------ resultados
    def rssi_referencia(self) -> float | None:
        for e in self.etapas:
            if e.chave == REFERENCIA and e.concluida:
                return float(e.amostras[f"rssi_{self.lado}"].mean())
        return None

    def amostras_angulo_rssi(self) -> pd.DataFrame:
        partes = [pd.DataFrame({"angulo": float(e.chave),
                                "rssi": e.amostras[f"rssi_{self.lado}"].dropna().to_numpy()})
                  for e in self.etapas if e.chave != REFERENCIA and e.concluida]
        if not partes:
            return pd.DataFrame(columns=["angulo", "rssi"])
        return pd.concat(partes, ignore_index=True)

    def tabela_etapas(self) -> pd.DataFrame:
        col = f"rssi_{self.lado}"
        reg = []
        for e in self.etapas:
            if e.concluida:
                r = e.amostras[col].dropna()
                reg.append({"Etapa": e.rotulo, "Pacotes": len(r), "RSSI médio [dBm]": r.mean(),
                            "Desvio [dB]": r.std(), "Mín [dBm]": r.min(), "Máx [dBm]": r.max()})
            else:
                reg.append({"Etapa": e.rotulo, "Pacotes": 0, "RSSI médio [dBm]": np.nan,
                            "Desvio [dB]": np.nan, "Mín [dBm]": np.nan, "Máx [dBm]": np.nan})
        return pd.DataFrame(reg)

    def amostras_brutas(self) -> pd.DataFrame:
        """Todas as linhas de log coletadas, com a etapa de origem."""
        partes = []
        for e in self.etapas:
            if e.concluida:
                p = e.amostras.copy()
                p.insert(0, "etapa", e.rotulo)
                partes.append(p)
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
