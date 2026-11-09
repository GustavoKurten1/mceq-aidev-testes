#!/usr/bin/env python3
"""
Ficha de proveniência e medição — base AIDev (subconjunto curado).

1. Fixa a versão da base (commit do Hugging Face) em dados/VERSAO.txt.
2. Baixa as tabelas usadas no projeto para dados/brutos/.
3. Imprime os números da ficha e salva tudo em saida_proveniencia.txt.

Uso:  python proveniencia.py
"""
from datetime import date
from pathlib import Path

import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

REPO = "hao-li/AIDev"
TABELAS = ["pull_request", "pr_commit_details", "pr_task_type", "repository"]
BRUTOS = Path("dados/brutos")
VERSAO = Path("dados/VERSAO.txt")
SAIDA = Path("saida_proveniencia.txt")
TIPOS_DO_RECORTE = {"feat", "fix"}

linhas = []


def log(texto=""):
    print(texto)
    linhas.append(str(texto))


def secao(titulo):
    log()
    log("=" * 64)
    log(titulo)
    log("=" * 64)


def versao_fixa():
    """Lê o commit registrado. Na primeira execução, registra o commit atual da base."""
    if VERSAO.exists():
        info = dict(l.split(": ", 1) for l in VERSAO.read_text().splitlines() if ": " in l)
        return info["commit"], info["data_de_acesso"]
    commit = HfApi().dataset_info(REPO).sha
    acesso = date.today().isoformat()
    VERSAO.parent.mkdir(parents=True, exist_ok=True)
    VERSAO.write_text(f"repositorio: {REPO}\ncommit: {commit}\ndata_de_acesso: {acesso}\n")
    return commit, acesso


def baixar(commit):
    BRUTOS.mkdir(parents=True, exist_ok=True)
    faltando = [t for t in TABELAS if not (BRUTOS / f"{t}.parquet").exists()]
    if not faltando:
        return
    arquivos = HfApi().list_repo_files(REPO, repo_type="dataset", revision=commit)
    for t in faltando:
        nome = f"{t}.parquet"
        if nome not in arquivos:
            raise SystemExit(f"{nome} não existe na base. Arquivos disponíveis:\n{arquivos}")
        print(f"Baixando {nome} (pode demorar)...")
        hf_hub_download(REPO, nome, repo_type="dataset", revision=commit, local_dir=BRUTOS)


def ler(tabela, colunas):
    caminho = BRUTOS / f"{tabela}.parquet"
    try:
        return pd.read_parquet(caminho, columns=colunas)
    except Exception:
        existentes = list(pd.read_parquet(caminho).columns)
        raise SystemExit(f"Colunas esperadas em {tabela}: {colunas}\nColunas encontradas: {existentes}")


def main():
    commit, acesso = versao_fixa()
    baixar(commit)

    pr = ler("pull_request", ["id", "agent", "created_at", "repo_id"])
    det = ler("pr_commit_details", ["sha", "pr_id", "filename", "status", "additions", "deletions"])
    tipo = ler("pr_task_type", ["id", "agent", "type"])
    repo = ler("repository", ["id", "language", "stars"])
    tabelas = {"pull_request": pr, "pr_commit_details": det, "pr_task_type": tipo, "repository": repo}

    # ids como texto, para comparar tabelas mesmo que os tipos difiram
    ids_pr = set(pr["id"].astype(str))
    det_pr = det["pr_id"].astype(str)
    tipo["type"] = tipo["type"].astype(str).str.strip().str.lower()

    secao("1. ORIGEM E VERSÃO")
    log(f"Base: {REPO} (Hugging Face)")
    log(f"Commit (versão): {commit}")
    log(f"Data de acesso: {acesso}")

    secao("2. TAMANHO DAS TABELAS (linhas)")
    for nome, df in tabelas.items():
        log(f"{nome}: {len(df):,}")

    secao("3. PRs POR AGENTE (pull_request)")
    log(pr["agent"].value_counts(dropna=False).to_string())

    secao("4. PERÍODO (created_at)")
    criado = pd.to_datetime(pr["created_at"], utc=True, errors="coerce")
    log(f"Geral: {criado.min()} até {criado.max()}")
    log(f"Datas que não puderam ser lidas: {criado.isna().sum():,}")
    periodo = criado.groupby(pr["agent"]).agg(["min", "max"])
    log(periodo.to_string())

    secao("5. DADOS AUSENTES (nulos por coluna)")
    for nome, df in tabelas.items():
        log(f"-- {nome}")
        log(df.isna().sum().to_string())

    secao("6. DUPLICADOS")
    log(f"pull_request: linhas com id repetido = {pr['id'].duplicated(keep=False).sum():,}")
    log(f"pr_commit_details: linhas idênticas (sha, pr_id, arquivo, status, linhas) = {det.duplicated().sum():,}")
    log(f"pr_task_type: linhas com id repetido = {tipo['id'].duplicated(keep=False).sum():,}")
    log(f"repository: linhas com id repetido = {repo['id'].duplicated(keep=False).sum():,}")

    secao("7. COBERTURA ENTRE TABELAS")
    prs_com_det = set(det_pr)
    prs_com_arquivo = set(det_pr[det["filename"].notna()])
    log(f"PRs sem nenhuma linha em pr_commit_details: {len(ids_pr - prs_com_det):,}")
    log(f"PRs com commits mas sem lista de arquivos (filename nulo): {len((ids_pr & prs_com_det) - prs_com_arquivo):,}")
    log(f"Linhas de pr_commit_details com pr_id fora de pull_request: {(~det_pr.isin(ids_pr)).sum():,}")
    log(f"PRs sem tipo em pr_task_type: {len(ids_pr - set(tipo['id'].astype(str))):,}")
    ids_repo = set(repo["id"].astype(str))
    log(f"PRs com repo_id fora de repository: {(~pr['repo_id'].astype(str).isin(ids_repo)).sum():,}")

    secao("8. TIPO DO PR (pr_task_type, classificado por LLM)")
    log(tipo["type"].value_counts(dropna=False).to_string())

    secao("9. PRÉVIA DO RECORTE: PRs feat/fix com lista de arquivos, por agente")
    ids_recorte = set(tipo.loc[tipo["type"].isin(TIPOS_DO_RECORTE), "id"].astype(str))
    no_recorte = pr["id"].astype(str).isin(ids_recorte & prs_com_arquivo)
    log(pr.loc[no_recorte, "agent"].value_counts().to_string())
    log(f"Total: {no_recorte.sum():,}")

    secao("10. TRUNCAGEM EM 30 ITENS")
    log("Na coleta da v3 as listas por PR não eram paginadas: no máximo 30 commits por PR.")
    log("Aqui: commits (sha) distintos por PR em pr_commit_details, só PRs de pull_request.")
    commits_por_pr = det.groupby(det_pr)["sha"].nunique()
    commits_por_pr = commits_por_pr[commits_por_pr.index.isin(ids_pr)]
    no_limite = set(commits_por_pr.index[commits_por_pr == 30])
    log(f"PRs com commits em pr_commit_details: {len(commits_por_pr):,}")
    log(f"Máximo de commits distintos em um PR: {commits_por_pr.max():,}")
    log(f"PRs com mais de 30 commits distintos: {(commits_por_pr > 30).sum():,}")
    log("PRs com exatamente 30 commits distintos (atingem o limite), por agente:")
    por_agente = pr.loc[pr["id"].astype(str).isin(no_limite), "agent"].value_counts()
    log(por_agente.reindex(pr["agent"].value_counts().index, fill_value=0).to_string())
    log(f"Total: {len(no_limite):,}")

    SAIDA.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"\nSaída salva em {SAIDA}")


if __name__ == "__main__":
    main()
