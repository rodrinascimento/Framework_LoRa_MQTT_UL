"""Site survey: importação dos logs do gateway e estatísticas de RSSI/SNR.

Reproduz as abas 'MedidasSensor*' da planilha de link budget e 'MedidasANT*' da planilha de
perda sistêmica:
    * máximo e mínimo de RSSI e SNR (DL e UL);
    * média móvel do RSSI calculada em mW (janela para frente, como na planilha);
    * diferença RSSI − média móvel e seu desvio padrão;
    * desvio padrão móvel da diferença e sua média ("desvio padrão médio").

O importador aceita CSV/TXT/LOG com vírgula, ponto e vírgula ou tabulação, com ou sem
cabeçalho, e também planilhas .xlsx no formato das abas 'MedidasSensor'. Quando não há
delimitador reconhecível, cada linha é lida como "<timestamp> <contador> <rssi_dl> <snr_dl>
<rssi_ul> <snr_ul>", com o timestamp podendo conter espaços (ex.: saída de time.ctime()).
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, asdict, field
from pathlib import Path

import numpy as np
import pandas as pd

COLUNAS = ["timestamp", "contador", "rssi_dl", "snr_dl", "rssi_ul", "snr_ul"]
ROTULOS = {
    "timestamp": "Time stamp", "contador": "Contador",
    "rssi_dl": "RSSI DL [dBm]", "snr_dl": "SNR DL [dB]",
    "rssi_ul": "RSSI UL [dBm]", "snr_ul": "SNR UL [dB]",
}
EXTENSOES_LOG = (".csv", ".txt", ".log", ".tsv", ".xlsx", ".xlsm")
_NUM = r"[-+]?\d+(?:[.,]\d+)?"


def _normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return re.sub(r"[\s_\-\[\]()]+", " ", txt.lower()).strip()


def _mapear_coluna(nome: str) -> str | None:
    n = _normalizar(nome)
    lado = "dl" if re.search(r"\b(dl|down|downlink)\b", n) else (
        "ul" if re.search(r"\b(ul|up|uplink)\b", n) else None)
    if "rssi" in n and lado:
        return f"rssi_{lado}"
    if "snr" in n and lado:
        return f"snr_{lado}"
    if any(k in n for k in ("contador", "counter", "count", "seq", "pacote", "id")):
        return "contador"
    if any(k in n for k in ("time", "data", "hora", "date", "stamp")):
        return "timestamp"
    return None


def _para_float(serie: pd.Series) -> pd.Series:
    if serie.dtype == object:
        serie = serie.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(serie, errors="coerce")


def _finalizar(df: pd.DataFrame) -> pd.DataFrame:
    for c in COLUNAS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[COLUNAS].copy()
    for c in COLUNAS[1:]:
        df[c] = _para_float(df[c])
    df["timestamp"] = df["timestamp"].astype(str).str.strip()
    df = df.dropna(subset=["rssi_dl", "rssi_ul"], how="all").reset_index(drop=True)
    if df.empty:
        raise ValueError("Nenhuma linha com RSSI foi encontrada no arquivo.")
    return df


def _ler_texto_livre(texto: str) -> pd.DataFrame:
    padrao = re.compile(rf"^(.*?)[\s,;]*({_NUM})[\s,;]+({_NUM})[\s,;]+({_NUM})[\s,;]+({_NUM})[\s,;]+({_NUM})\s*[,;]?\s*$")
    linhas = []
    for linha in texto.splitlines():
        m = padrao.match(linha.strip())
        if m:
            linhas.append(dict(zip(COLUNAS, [m.group(1).strip(" ,;")] + list(m.groups()[1:]))))
    return pd.DataFrame(linhas)


def ler_log_texto(texto: str) -> pd.DataFrame:
    """Converte o conteúdo de um log em DataFrame com as colunas de COLUNAS."""
    amostra = "\n".join(texto.splitlines()[:20])
    delim = None
    try:
        delim = csv.Sniffer().sniff(amostra, delimiters=",;\t").delimiter
    except csv.Error:
        pass
    if delim:
        decimal = "," if delim == ";" else "."
        bruto = pd.read_csv(io.StringIO(texto), sep=delim, header=None, dtype=str,
                            skip_blank_lines=True, engine="python")
        bruto = bruto.dropna(axis=1, how="all")
        primeira = bruto.iloc[0].tolist()
        tem_cabecalho = sum(_mapear_coluna(str(v)) is not None for v in primeira) >= 2
        if tem_cabecalho:
            mapa = {}
            for i, v in enumerate(primeira):
                alvo = _mapear_coluna(str(v))
                if alvo and alvo not in mapa.values():
                    mapa[bruto.columns[i]] = alvo
            df = bruto.iloc[1:].rename(columns=mapa)
            df = df[[c for c in df.columns if c in COLUNAS]]
        else:
            df = bruto.iloc[:, :6].copy()
            if df.shape[1] == 5:     # sem timestamp
                df.insert(0, "timestamp", "")
            df.columns = COLUNAS[: df.shape[1]]
        if decimal == ",":
            for c in df.columns:
                if c != "timestamp":
                    df[c] = df[c].astype(str).str.replace(",", ".", regex=False)
        try:
            return _finalizar(df)
        except ValueError:
            pass
    return _finalizar(_ler_texto_livre(texto))


def ler_log(caminho: str | Path, aba: str | None = None) -> pd.DataFrame:
    caminho = Path(caminho)
    if caminho.suffix.lower() in (".xlsx", ".xlsm"):
        bruto = pd.read_excel(caminho, sheet_name=aba or 0, header=0, usecols="A:F")
        mapa = {c: _mapear_coluna(c) for c in bruto.columns}
        if sum(v is not None for v in mapa.values()) >= 3:
            bruto = bruto.rename(columns={k: v for k, v in mapa.items() if v})
        else:
            bruto.columns = COLUNAS[: bruto.shape[1]]
        return _finalizar(bruto)
    dados = caminho.read_bytes()
    for cod in ("utf-8-sig", "latin-1"):
        try:
            texto = dados.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    return ler_log_texto(texto)


def log_mais_recente(pasta: str | Path, padrao: str = "log") -> Path | None:
    """Arquivo de log mais recente (busca recursiva) cujo nome contém `padrao`."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        return None
    candidatos = [p for p in pasta.rglob("*") if p.is_file()
                  and "Exportacoes" not in p.relative_to(pasta).parts
                  and p.suffix.lower() in EXTENSOES_LOG
                  and padrao.lower() in p.name.lower()]
    return max(candidatos, key=lambda p: p.stat().st_mtime, default=None)


# ---------------------------------------------------------------- estatísticas
def dbm_para_mw(dbm):
    return np.power(10.0, np.asarray(dbm, dtype=float) / 10.0)


def mw_para_dbm(mw):
    return 10.0 * np.log10(np.asarray(mw, dtype=float))


def media_movel_mw(rssi_dbm: pd.Series, janela: int) -> pd.Series:
    """Média móvel em mW convertida para dBm, janela para frente (linhas i..i+N−1).

    No fim da série a janela encolhe, como o AVERAGE do Excel ignorando células vazias.
    """
    mw = pd.Series(dbm_para_mw(rssi_dbm), index=rssi_dbm.index)
    media = mw[::-1].rolling(janela, min_periods=1).mean()[::-1]
    return pd.Series(mw_para_dbm(media), index=rssi_dbm.index)


def desvio_movel(serie: pd.Series, janela: int) -> pd.Series:
    return serie[::-1].rolling(janela, min_periods=2).std()[::-1]


@dataclass
class EstatisticasEnlace:
    lado: str
    n_amostras: int
    rssi_max: float
    rssi_min: float
    rssi_media_dbm: float          # média aritmética em dBm
    rssi_media_mw_dbm: float       # média em mW convertida para dBm
    rssi_media_mm_dbm: float       # média da média móvel (como a planilha)
    snr_max: float
    snr_min: float
    snr_media: float
    desvio_padrao: float           # desvio da diferença RSSI − média móvel
    desvio_padrao_medio: float     # média do desvio móvel

    def como_dict(self):
        return asdict(self)


@dataclass
class ResultadoSurvey:
    dados: pd.DataFrame
    dl: EstatisticasEnlace | None
    ul: EstatisticasEnlace | None
    janela: int
    pacotes_esperados: int | None = None
    pacotes_recebidos: int = 0

    @property
    def per(self) -> float | None:
        if not self.pacotes_esperados:
            return None
        return max(0.0, 1 - self.pacotes_recebidos / self.pacotes_esperados)

    def tabela_resumo(self) -> pd.DataFrame:
        linhas = [
            ("Amostras", "n_amostras", ""),
            ("Máximo RSSI", "rssi_max", "dBm"), ("Mínimo RSSI", "rssi_min", "dBm"),
            ("Média RSSI (média móvel)", "rssi_media_mm_dbm", "dBm"),
            ("Média RSSI (em mW)", "rssi_media_mw_dbm", "dBm"),
            ("Média RSSI (em dBm)", "rssi_media_dbm", "dBm"),
            ("Desvio padrão RSSI", "desvio_padrao", "dB"),
            ("Desvio padrão médio RSSI", "desvio_padrao_medio", "dB"),
            ("Máximo SNR", "snr_max", "dB"), ("Mínimo SNR", "snr_min", "dB"),
            ("Média SNR", "snr_media", "dB"),
        ]
        reg = []
        for rotulo, attr, un in linhas:
            reg.append({
                "Grandeza": rotulo, "Unidade": un,
                "Downlink": getattr(self.dl, attr) if self.dl else np.nan,
                "Uplink": getattr(self.ul, attr) if self.ul else np.nan,
            })
        reg.append({"Grandeza": "Janela da média móvel", "Unidade": "amostras",
                    "Downlink": self.janela, "Uplink": self.janela})
        if self.pacotes_esperados:
            reg.append({"Grandeza": "Pacotes recebidos / esperados", "Unidade": "",
                        "Downlink": f"{self.pacotes_recebidos}/{self.pacotes_esperados}",
                        "Uplink": f"{self.pacotes_recebidos}/{self.pacotes_esperados}"})
            reg.append({"Grandeza": "Perda de pacotes (PER)", "Unidade": "%",
                        "Downlink": 100 * self.per, "Uplink": 100 * self.per})
        return pd.DataFrame(reg)


def _estatisticas(df: pd.DataFrame, lado: str, janela: int) -> EstatisticasEnlace | None:
    rssi = df[f"rssi_{lado}"].dropna()
    if rssi.empty:
        return None
    snr = df[f"snr_{lado}"].dropna()
    mm = df[f"mm_{lado}"].dropna()
    return EstatisticasEnlace(
        lado=lado.upper(), n_amostras=int(rssi.size),
        rssi_max=float(rssi.max()), rssi_min=float(rssi.min()),
        rssi_media_dbm=float(rssi.mean()),
        rssi_media_mw_dbm=float(mw_para_dbm(dbm_para_mw(rssi).mean())),
        rssi_media_mm_dbm=float(mm.mean()),
        snr_max=float(snr.max()) if not snr.empty else np.nan,
        snr_min=float(snr.min()) if not snr.empty else np.nan,
        snr_media=float(snr.mean()) if not snr.empty else np.nan,
        desvio_padrao=float(df[f"dif_{lado}"].std()),
        desvio_padrao_medio=float(df[f"dp_{lado}"].mean()),
    )


def analisar(df: pd.DataFrame, janela: int = 10) -> ResultadoSurvey:
    if janela < 1:
        raise ValueError("A janela da média móvel deve ser pelo menos 1.")
    df = df.copy()
    for lado in ("dl", "ul"):
        rssi = df[f"rssi_{lado}"]
        if rssi.notna().any():
            df[f"mm_{lado}"] = media_movel_mw(rssi, janela)
            df[f"dif_{lado}"] = rssi - df[f"mm_{lado}"]
            df[f"dp_{lado}"] = desvio_movel(df[f"dif_{lado}"], janela)
        else:
            df[f"mm_{lado}"] = df[f"dif_{lado}"] = df[f"dp_{lado}"] = np.nan
    cont = df["contador"].dropna()
    esperados = int(cont.max() - cont.min() + 1) if not cont.empty else None
    return ResultadoSurvey(df, _estatisticas(df, "dl", janela), _estatisticas(df, "ul", janela),
                           janela, esperados, int(cont.nunique()) if not cont.empty else len(df))


def dados_para_exportar(res: ResultadoSurvey) -> pd.DataFrame:
    nomes = dict(ROTULOS)
    nomes.update({
        "mm_dl": "Média Móvel RSSI DL [dBm]", "mm_ul": "Média Móvel RSSI UL [dBm]",
        "dif_dl": "RSSI − Média Móvel DL [dB]", "dif_ul": "RSSI − Média Móvel UL [dB]",
        "dp_dl": "Desvio Padrão Móvel DL [dB]", "dp_ul": "Desvio Padrão Móvel UL [dB]",
    })
    return res.dados.rename(columns=nomes)
