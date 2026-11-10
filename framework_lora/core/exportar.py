"""Exportação organizada de resultados.

Cada exportação cria uma pasta própria:
    <raiz>/4_N4_Armazenamento/Exportacoes/<AAAA-MM-DD>/<hh-mm-ss>_<tipo>[_<nome>]/
contendo um .xlsx com várias abas (resumo, dados, parâmetros), CSVs das tabelas e as
figuras em PNG.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from .parametros import pasta_armazenamento


def _limpar(nome: str) -> str:
    nome = re.sub(r"[^\w\-]+", "_", str(nome), flags=re.UNICODE).strip("_")
    return nome[:60] or "export"


def pasta_exportacao(raiz, tipo: str, nome: str | None = None, agora: datetime | None = None) -> Path:
    agora = agora or datetime.now()
    sufixo = _limpar(tipo) + (f"_{_limpar(nome)}" if nome else "")
    p = pasta_armazenamento(raiz) / "Exportacoes" / agora.strftime("%Y-%m-%d") / f"{agora:%H-%M-%S}_{sufixo}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _nome_aba(nome: str) -> str:
    return re.sub(r"[\[\]\*\?/\\:]", "_", nome)[:31]


def salvar_excel(caminho: Path, abas: dict[str, pd.DataFrame]) -> Path:
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    caminho = Path(caminho)
    with pd.ExcelWriter(caminho, engine="openpyxl") as w:
        for nome, df in abas.items():
            if df is None:
                continue
            aba = _nome_aba(nome)
            df.to_excel(w, sheet_name=aba, index=False)
            ws = w.sheets[aba]
            ws.freeze_panes = "A2"
            for cel in ws[1]:
                cel.font = Font(bold=True, color="FFFFFF")
                cel.fill = PatternFill("solid", fgColor="1F4E79")
            for i, col in enumerate(df.columns, start=1):
                amostra = [str(col)] + [str(v) for v in df[col].head(200).tolist()]
                ws.column_dimensions[get_column_letter(i)].width = min(45, max(10, max(map(len, amostra)) + 2))
    return caminho


def parametros_para_df(params: dict) -> pd.DataFrame:
    return pd.DataFrame([{"Parâmetro": k, "Valor": v} for k, v in params.items()])


def exportar(raiz, tipo: str, abas: dict[str, pd.DataFrame], figuras: dict | None = None,
             nome: str | None = None, csv: bool = True) -> Path:
    """Gera a pasta de exportação com .xlsx, CSVs e figuras. Devolve a pasta criada."""
    pasta = pasta_exportacao(raiz, tipo, nome)
    salvar_excel(pasta / f"{_limpar(tipo)}.xlsx", abas)
    if csv:
        for n, df in abas.items():
            if df is not None:
                df.to_csv(pasta / f"{_limpar(n)}.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
    for n, fig in (figuras or {}).items():
        fig.savefig(pasta / f"{_limpar(n)}.png", dpi=200, bbox_inches="tight")
    return pasta
