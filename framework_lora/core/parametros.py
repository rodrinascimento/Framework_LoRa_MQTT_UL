"""Leitura e gravação dos arquivos de parâmetros lidos pelo gateway e pela borda.

Os formatos são idênticos aos dos scripts originais (Setup_Parametros_Serial.py e
Setup_Parametros_Cliente.py), para que o gateway continue funcionando sem mudanças.

PARAMETROS.txt (4 linhas):
    1. comando  (1 = iniciar/atualizar, 2 = pausar, 0 = parar)
    2. número de medidas (inteiro > 0)
    3. tempo entre pacotes em segundos (float)
    4. número da porta serial (ex.: "3" para COM3; outras plataformas: caminho do dispositivo)

parametros_cliente.txt (1 linha):
    1. limiar de ligar (inteiro de 0 a 4095)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

PASTA_ARMAZENAMENTO = "4_N4_Armazenamento"
SUBPASTA_PARAMETROS = "Parametros"
ARQUIVO_PARAMETROS = "PARAMETROS.txt"
ARQUIVO_CLIENTE = "parametros_cliente.txt"

LIMIAR_MIN = 0
LIMIAR_MAX = 4095
HISTERESE_CLIENTE = 50

TEMPO_SHORT_DISTANCE = 0.2
TEMPO_LONG_DISTANCE = 3.0


class Comando(IntEnum):
    PARAR = 0
    INICIAR = 1
    PAUSAR = 2

    @property
    def rotulo(self) -> str:
        return {Comando.PARAR: "PARADO", Comando.INICIAR: "INICIADO / ATUALIZADO",
                Comando.PAUSAR: "PAUSADO"}[self]


class ErroValidacao(ValueError):
    """Erro de validação de parâmetros, com mensagem pronta para o usuário."""


def pasta_parametros(raiz: str | os.PathLike) -> Path:
    """Pasta <raiz>/4_N4_Armazenamento/Parametros (criada se não existir)."""
    p = Path(raiz) / PASTA_ARMAZENAMENTO / SUBPASTA_PARAMETROS
    p.mkdir(parents=True, exist_ok=True)
    return p


def pasta_armazenamento(raiz: str | os.PathLike) -> Path:
    p = Path(raiz) / PASTA_ARMAZENAMENTO
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------- Gerência Serial
@dataclass
class ParametrosSerial:
    comando: Comando
    medidas: int
    tempo: float
    porta: str

    @staticmethod
    def validar(comando: int, medidas: str | int, tempo: str | float, porta: str) -> "ParametrosSerial":
        porta = (porta or "").strip()
        if not porta or "nenhuma" in porta.lower():
            raise ErroValidacao("Selecione uma porta serial válida para o Gateway.")
        try:
            tempo_f = float(str(tempo).strip().replace(",", "."))
            if tempo_f <= 0:
                raise ValueError
        except ValueError:
            raise ErroValidacao("O tempo entre pacotes deve ser um número maior que zero.") from None
        try:
            medidas_i = int(str(medidas).strip())
            if medidas_i <= 0:
                raise ValueError
        except ValueError:
            raise ErroValidacao("O número de medidas deve ser um inteiro maior que zero.") from None
        return ParametrosSerial(Comando(int(comando)), medidas_i, tempo_f, porta)

    @property
    def num_serial(self) -> str:
        """Linha 4 do arquivo: 'COM3' vira '3'; demais nomes são mantidos."""
        p = self.porta.strip()
        return p[3:] if p.upper().startswith("COM") else p

    def para_texto(self) -> str:
        return f"{int(self.comando)}\n{self.medidas}\n{self.tempo}\n{self.num_serial}\n"


def gravar_parametros_serial(raiz, params: ParametrosSerial) -> Path:
    caminho = pasta_parametros(raiz) / ARQUIVO_PARAMETROS
    caminho.write_text(params.para_texto(), encoding="utf-8")
    return caminho


def ler_parametros_serial(raiz) -> ParametrosSerial | None:
    caminho = Path(raiz) / PASTA_ARMAZENAMENTO / SUBPASTA_PARAMETROS / ARQUIVO_PARAMETROS
    try:
        linhas = [l.strip() for l in caminho.read_text(encoding="utf-8").splitlines()]
        if len(linhas) < 4:
            return None
        porta = linhas[3]
        if porta.isdigit():
            porta = f"COM{porta}"
        return ParametrosSerial(Comando(int(linhas[0])), int(linhas[1]), float(linhas[2]), porta)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- Cliente
def limiar_desligar(limiar_ligar: int) -> int:
    return min(LIMIAR_MAX, int(limiar_ligar) + HISTERESE_CLIENTE)


def validar_limiar(valor: str | int) -> int:
    try:
        v = int(str(valor).strip())
    except ValueError:
        raise ErroValidacao(f"Limiar inválido. Use um inteiro de {LIMIAR_MIN} a {LIMIAR_MAX}.") from None
    if not LIMIAR_MIN <= v <= LIMIAR_MAX:
        raise ErroValidacao(f"Limiar inválido. Use um inteiro de {LIMIAR_MIN} a {LIMIAR_MAX}.")
    return v


def gravar_limiar_cliente(raiz, limiar: int) -> Path:
    caminho = pasta_parametros(raiz) / ARQUIVO_CLIENTE
    caminho.write_text(f"{int(limiar)}\n", encoding="utf-8")
    return caminho


def ler_limiar_cliente(raiz, padrao: int = 2000) -> int:
    caminho = Path(raiz) / PASTA_ARMAZENAMENTO / SUBPASTA_PARAMETROS / ARQUIVO_CLIENTE
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return int(float(f.readline().strip().replace(",", ".")))
    except (OSError, ValueError):
        return padrao
