#!/usr/bin/env python3
"""
Análise da hipótese principal — MCEQ 12576 (PUC-Campinas), base AIDev v3.

Pergunta: em PRs de funcionalidade e de correção abertos por agentes de IA em
projetos open source, a proporção de código de teste difere entre os agentes?

H0: as distribuições da VD são iguais nos cinco agentes.
H1 (bilateral): ao menos um agente difere dos demais.

Tudo o que está fixado neste arquivo (regra de arquivo de teste, exclusões,
regra de escolha do teste, alfa, semente) foi definido antes da primeira
execução sobre os dados.

Uso:      python analise.py
Entrada:  dados/brutos/*.parquet (baixados por proveniencia.py)
Saídas:   dados/limpos/prs_limpos.csv, resultados/*, figuras/vd_por_agente.png
"""
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

BRUTOS = Path("dados/brutos")
LIMPOS = Path("dados/limpos")
RES = Path("resultados")
FIG = Path("figuras")

ALFA = 0.05
SEMENTE = 2026
B = 2000                      # reamostragens bootstrap
TIPOS = {"feat", "fix"}       # recorte: funcionalidade e correção
LIMITE_COMMITS = 30           # limite da coleta da v3 (commits por PR)
ORDEM = ["OpenAI_Codex", "Copilot", "Devin", "Cursor", "Claude_Code"]
NOME = {"OpenAI_Codex": "Codex", "Copilot": "Copilot", "Devin": "Devin",
        "Cursor": "Cursor", "Claude_Code": "Claude Code"}

# ---------------------------------------------------------------- regras fixas
# Arquivo de teste: alguma pasta do caminho com um destes nomes...
PASTAS_TESTE = {"test", "tests", "__tests__", "spec"}
# ...ou nome do arquivo em uma destas convenções.
RE_TESTE = re.compile("|".join([
    r"^test_.+\.py$", r"^.+_test\.py$",                           # Python
    r"^.+_test\.go$",                                             # Go
    r"^.+(Test|Tests)\.(java|kt|scala|groovy|cs|php|swift)$",     # JVM, C#, PHP, Swift
    r"^.+\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)$",                # JavaScript/TypeScript
    r"^.+_(spec|test)\.rb$",                                      # Ruby
    r"^.+_test\.(dart|exs)$",                                     # Dart, Elixir
    r"^.+_test\.(c|cc|cpp|h|hpp)$",                               # C/C++
]))
# Arquivos de lock e gerados, excluídos do numerador e do denominador.
LOCKS = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
         "Pipfile.lock", "Cargo.lock", "composer.lock", "Gemfile.lock",
         "go.sum", "uv.lock", "bun.lockb"}
SUFIXOS_GERADOS = (".min.js", ".min.css")
PASTAS_EXCLUIDAS = {"vendor", "node_modules", "dist"}


def partes(caminho):
    p = str(caminho).replace("\\", "/").split("/")
    return p[:-1], p[-1]


def eh_teste(caminho):
    pastas, nome = partes(caminho)
    return any(x.lower() in PASTAS_TESTE for x in pastas) or bool(RE_TESTE.match(nome))


def eh_excluido(caminho):
    pastas, nome = partes(caminho)
    return nome in LOCKS or nome.endswith(SUFIXOS_GERADOS) or any(x in PASTAS_EXCLUIDAS for x in pastas)


saida = []


def log(texto=""):
    print(texto)
    saida.append(str(texto))


# ------------------------------------------------------------------ carga
def carregar():
    pr = pd.read_parquet(BRUTOS / "pull_request.parquet", columns=["id", "agent"])
    tipo = pd.read_parquet(BRUTOS / "pr_task_type.parquet", columns=["id", "type"])
    det = pd.read_parquet(BRUTOS / "pr_commit_details.parquet",
                          columns=["sha", "pr_id", "filename", "status", "additions", "deletions"])
    pr["id"] = pr["id"].astype(str)
    tipo["id"] = tipo["id"].astype(str)
    tipo["type"] = tipo["type"].astype(str).str.strip().str.lower()
    det["pr_id"] = det["pr_id"].astype(str)
    return pr.merge(tipo, on="id", how="left"), det


# ------------------------------------------------------------------ limpeza
def limpar(pr, det, excluir_limite=True):
    """Aplica as decisões de limpeza do protocolo e devolve (PRs limpos, log, arquivos)."""
    etapas = []

    def registrar(nome, ids):
        c = pr.loc[pr["id"].isin(ids), "agent"].value_counts()
        etapas.append({"etapa": nome, **{a: int(c.get(a, 0)) for a in ORDEM}, "total": int(c.sum())})

    ids = set(pr["id"])
    registrar("0. PRs no subconjunto curado", ids)

    n0 = len(det)
    det = det.drop_duplicates()
    linhas_dup = n0 - len(det)

    ids &= set(pr.loc[pr["type"].isin(TIPOS), "id"])
    registrar("1. Tipo feat ou fix", ids)

    commits = det.groupby("pr_id")["sha"].nunique()
    arq = det.dropna(subset=["filename", "additions"])
    ids &= set(arq["pr_id"])
    registrar("2. Com lista de arquivos", ids)

    if excluir_limite:
        ids -= set(commits[commits >= LIMITE_COMMITS].index)
        registrar(f"3. Sem PRs no limite de {LIMITE_COMMITS} commits", ids)

    arq = arq[arq["pr_id"].isin(ids)].copy()
    unicos = pd.Series(arq["filename"].unique())
    excl = dict(zip(unicos, unicos.map(eh_excluido)))
    teste = dict(zip(unicos, unicos.map(eh_teste)))
    arq["excluido"] = arq["filename"].map(excl)
    linhas_excl = int(arq["excluido"].sum())
    arq = arq[~arq["excluido"]].copy()
    arq["teste"] = arq["filename"].map(teste)
    arq["add_teste"] = np.where(arq["teste"], arq["additions"], 0)

    por_pr = arq.groupby("pr_id").agg(linhas_adicionadas=("additions", "sum"),
                                      linhas_teste=("add_teste", "sum")).reset_index()
    por_pr = por_pr[por_pr["linhas_adicionadas"] > 0]
    ids &= set(por_pr["pr_id"])
    registrar("4. Com linhas adicionadas após excluir lock e gerados", ids)

    df = (pr[pr["id"].isin(ids)][["id", "agent", "type"]]
          .merge(por_pr, left_on="id", right_on="pr_id").drop(columns="pr_id"))
    df["n_commits"] = df["id"].map(commits).astype(int)
    df["vd"] = df["linhas_teste"] / df["linhas_adicionadas"]
    info = {"linhas_duplicadas": linhas_dup, "linhas_lock_gerados": linhas_excl}
    return df, pd.DataFrame(etapas), info, arq


# ------------------------------------------------------------------ estatística
def ic_media(x):
    m, s, n = x.mean(), x.std(ddof=1), len(x)
    h = stats.t.ppf(1 - ALFA / 2, n - 1) * s / np.sqrt(n)
    return m - h, m + h


def descritiva(df):
    linhas = []
    for a in ORDEM:
        x = df.loc[df["agent"] == a, "vd"].to_numpy()
        li, ls = ic_media(x)
        linhas.append({"agente": NOME[a], "n": len(x), "media": x.mean(), "ic95_inf": li, "ic95_sup": ls,
                       "dp": x.std(ddof=1), "mediana": np.median(x), "q1": np.quantile(x, .25),
                       "q3": np.quantile(x, .75), "pct_com_teste": (x > 0).mean()})
    return pd.DataFrame(linhas)


def eta2(grupos):
    tudo = np.concatenate(grupos)
    sst = ((tudo - tudo.mean()) ** 2).sum()
    ssb = sum(len(g) * (g.mean() - tudo.mean()) ** 2 for g in grupos)
    return ssb / sst


def dunn_holm(grupos):
    tudo = np.concatenate(grupos)
    n = len(tudo)
    r = stats.rankdata(tudo)
    cortes = np.cumsum([0] + [len(g) for g in grupos])
    rbar = [r[cortes[i]:cortes[i + 1]].mean() for i in range(len(grupos))]
    _, cont = np.unique(tudo, return_counts=True)
    s2 = n * (n + 1) / 12 - (cont ** 3 - cont).sum() / (12 * (n - 1))
    pares = []
    for i in range(len(grupos)):
        for j in range(i + 1, len(grupos)):
            z = (rbar[i] - rbar[j]) / np.sqrt(s2 * (1 / len(grupos[i]) + 1 / len(grupos[j])))
            pares.append((i, j, z, 2 * stats.norm.sf(abs(z))))
    m = len(pares)
    ordem = np.argsort([p[3] for p in pares])
    ajust, maior = [0.0] * m, 0.0
    for pos, idx in enumerate(ordem):
        maior = max(maior, min(1.0, (m - pos) * pares[idx][3]))
        ajust[idx] = maior
    return [(i, j, z, p, ajust[k]) for k, (i, j, z, p) in enumerate(pares)]


def welch_dif(x, y):
    d = x.mean() - y.mean()
    vx, vy = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    gl = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1))
    h = stats.t.ppf(1 - ALFA / 2, gl) * np.sqrt(vx + vy)
    return d, d - h, d + h


def cliff(x, y):
    u = stats.mannwhitneyu(x, y, alternative="two-sided").statistic
    return 2 * u / (len(x) * len(y)) - 1


def bootstrap(grupos, rng):
    """IC percentil de 95% para épsilon² (Kruskal-Wallis) e eta² (ANOVA), reamostrando dentro de cada grupo."""
    n = sum(len(g) for g in grupos)
    eps, eta = np.empty(B), np.empty(B)
    for b in range(B):
        a = [rng.choice(g, size=len(g), replace=True) for g in grupos]
        eps[b] = stats.kruskal(*a).statistic / (n - 1)
        eta[b] = eta2(a)
    q = [100 * ALFA / 2, 100 * (1 - ALFA / 2)]
    return np.percentile(eps, q), np.percentile(eta, q)


def analisar(df, rng):
    grupos = [df.loc[df["agent"] == a, "vd"].to_numpy(dtype=float) for a in ORDEM]
    n, k = len(df), len(grupos)
    res = {"n": n, "k": k}
    res["F"], res["p_anova"] = stats.f_oneway(*grupos)
    res["eta2"] = eta2(grupos)
    res["levene_W"], res["levene_p"] = stats.levene(*grupos, center="median")
    resid = np.concatenate([g - g.mean() for g in grupos])
    res["normal_K2"], res["normal_p"] = stats.normaltest(resid)
    res["assimetria"], res["curtose"] = stats.skew(resid), stats.kurtosis(resid)
    res["pressupostos_ok"] = res["levene_p"] >= ALFA and res["normal_p"] >= ALFA
    res["H"], res["p_kw"] = stats.kruskal(*grupos)
    res["eps2"] = res["H"] / (n - 1)
    res["ic_eps2"], res["ic_eta2"] = bootstrap(grupos, rng)
    pares = []
    if res["pressupostos_ok"]:
        tk = stats.tukey_hsd(*grupos)
        post = [(i, j, np.nan, np.nan, tk.pvalue[i, j]) for i in range(k) for j in range(i + 1, k)]
    else:
        post = dunn_holm(grupos)
    for i, j, z, p, p_aj in post:
        d, li, ls = welch_dif(grupos[i], grupos[j])
        pares.append({"par": f"{NOME[ORDEM[i]]} x {NOME[ORDEM[j]]}", "z": z, "p": p, "p_ajustado": p_aj,
                      "significativo": p_aj < ALFA, "dif_medias": d, "ic95_inf": li, "ic95_sup": ls,
                      "delta_cliff": cliff(grupos[i], grupos[j])})
    return res, pd.DataFrame(pares)


def rotulo_delta(d):
    d = abs(d)
    return "desprezível" if d < .147 else "pequeno" if d < .33 else "médio" if d < .474 else "grande"


def rotulo_eps2(e):
    return "desprezível" if e < .01 else "pequeno" if e < .08 else "médio" if e < .26 else "grande"


def relatar(titulo, res, desc, pares):
    log("=" * 70)
    log(titulo)
    log("=" * 70)
    log(f"n = {res['n']:,} PRs em k = {res['k']} grupos independentes")
    log()
    log("Descritiva da VD (proporção de linhas adicionadas em arquivos de teste):")
    log(desc.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    log()
    log("Pressupostos da ANOVA (alfa = 0,05):")
    log(f"  Levene (centro na mediana): W = {res['levene_W']:.2f}, p = {res['levene_p']:.3g}")
    log(f"  Normalidade dos resíduos (D'Agostino-Pearson): K2 = {res['normal_K2']:.1f}, p = {res['normal_p']:.3g}")
    log(f"  Assimetria = {res['assimetria']:.2f}; curtose (excesso) = {res['curtose']:.2f}")
    log(f"  Pressupostos atendidos: {'sim' if res['pressupostos_ok'] else 'não'}")
    log()
    log(f"ANOVA de um fator: F({res['k'] - 1}, {res['n'] - res['k']}) = {res['F']:.2f}, p = {res['p_anova']:.3g}; "
        f"eta2 = {res['eta2']:.4f} [IC95% {res['ic_eta2'][0]:.4f}; {res['ic_eta2'][1]:.4f}]")
    log(f"Kruskal-Wallis: H({res['k'] - 1}) = {res['H']:.2f}, p = {res['p_kw']:.3g}; "
        f"epsilon2 = {res['eps2']:.4f} [IC95% {res['ic_eps2'][0]:.4f}; {res['ic_eps2'][1]:.4f}] "
        f"({rotulo_eps2(res['eps2'])})")
    principal = "ANOVA de um fator + Tukey HSD" if res["pressupostos_ok"] else "Kruskal-Wallis + Dunn (Holm)"
    p_principal = res["p_anova"] if res["pressupostos_ok"] else res["p_kw"]
    log(f"Teste principal pela regra do protocolo: {principal}")
    log(f"Decisão: {'rejeita H0' if p_principal < ALFA else 'não rejeita H0'} (alfa = {ALFA})")
    log()
    log("Comparações par a par (p ajustado; diferença de médias em pontos da proporção, IC95% de Welch; delta de Cliff):")
    t = pares.copy()
    t["efeito"] = t["delta_cliff"].map(rotulo_delta)
    log(t.to_string(index=False, float_format=lambda v: f"{v:.4g}"))
    log()


def figura(desc):
    azul, tinta, tinta2, grade = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
    fig, ax = plt.subplots(figsize=(3.4, 2.3), dpi=300)
    x = np.arange(len(desc))
    m = desc["media"].to_numpy() * 100
    erro = np.vstack([m - desc["ic95_inf"].to_numpy() * 100, desc["ic95_sup"].to_numpy() * 100 - m])
    ax.errorbar(x, m, yerr=erro, fmt="o", color=azul, ms=4.5, elinewidth=1.4, capsize=3, capthick=1.4, zorder=3)
    ax.set_xticks(x, [f"{a}\nn = {n:,}".replace(",", ".") for a, n in zip(desc["agente"], desc["n"])],
                  color=tinta)
    ax.set_ylim(0, max(desc["ic95_sup"]) * 100 * 1.15)
    ax.set_ylabel("Linhas de teste (%)", color=tinta)
    ax.yaxis.grid(True, color=grade, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for lado in ["top", "right", "left"]:
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(tinta2)
    ax.tick_params(axis="both", colors=tinta2, length=0, labelsize=7)
    fig.tight_layout()
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / "vd_por_agente.png")
    plt.close(fig)


def amostra_validacao(arq, ids, rng):
    """50 arquivos classificados como teste e 50 como não teste, sorteados, para conferência manual da regra."""
    a = arq[arq["pr_id"].isin(ids)].drop_duplicates(["pr_id", "filename"])
    partes_ = []
    for valor in (True, False):
        sub = a[a["teste"] == valor]
        idx = rng.choice(len(sub), size=min(50, len(sub)), replace=False)
        partes_.append(sub.iloc[np.sort(idx)])
    s = pd.concat(partes_)[["pr_id", "filename", "teste"]]
    s = s.rename(columns={"filename": "arquivo", "teste": "regra_diz_teste"})
    s["conferencia_manual_eh_teste"] = ""
    return s


def exploratoria_repositorios(df):
    """Exploratória: PRs do mesmo repositório não são independentes. Mede a concentração
    e repete o Kruskal-Wallis com um ponto por par repositório-agente (média da VD)."""
    repo = pd.read_parquet(BRUTOS / "pull_request.parquet", columns=["id", "repo_id"])
    repo["id"] = repo["id"].astype(str)
    d = df.merge(repo, on="id")
    log("=" * 70)
    log("ANÁLISE EXPLORATÓRIA: AGRUPAMENTO DOS PRs POR REPOSITÓRIO")
    log("=" * 70)
    linhas = []
    for a in ORDEM:
        cont = d.loc[d["agent"] == a, "repo_id"].value_counts()
        linhas.append({"agente": NOME[a], "prs": int(cont.sum()), "repositorios": cont.size,
                       "pct_maior_repo": cont.iloc[0] / cont.sum(), "pct_10_maiores": cont.iloc[:10].sum() / cont.sum()})
    log(pd.DataFrame(linhas).to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    nomes = pd.read_parquet(BRUTOS / "repository.parquet", columns=["id", "full_name"])
    nomes = dict(zip(nomes["id"], nomes["full_name"]))
    log()
    log("Maior repositório de cada agente: VD média dentro e fora dele")
    for a in ORDEM:
        s = d[d["agent"] == a]
        topo = s["repo_id"].value_counts().index[0]
        dentro, fora = s.loc[s["repo_id"] == topo, "vd"], s.loc[s["repo_id"] != topo, "vd"]
        log(f"  {NOME[a]}: {nomes.get(topo, topo)} ({len(dentro):,} PRs, média {dentro.mean():.4f}); "
            f"demais repositórios ({len(fora):,} PRs, média {fora.mean():.4f})")
    r = d.groupby(["agent", "repo_id"])["vd"].mean().reset_index()
    grupos = [r.loc[r["agent"] == a, "vd"].to_numpy() for a in ORDEM]
    n = len(r)
    h, p = stats.kruskal(*grupos)
    log()
    log("VD média por repositório (um ponto por par repositório-agente):")
    log(pd.DataFrame({"agente": [NOME[a] for a in ORDEM], "repositorios": [len(g) for g in grupos],
                      "media": [g.mean() for g in grupos], "mediana": [np.median(g) for g in grupos]})
        .to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    log(f"Kruskal-Wallis: H({len(grupos) - 1}) = {h:.2f}, p = {p:.3g}; epsilon2 = {h / (n - 1):.4f} (n = {n:,})")
    log()


def main():
    for p in (LIMPOS, RES, FIG):
        p.mkdir(parents=True, exist_ok=True)
    pr, det = carregar()

    df, etapas, info, arq = limpar(pr, det)
    df.to_csv(LIMPOS / "prs_limpos.csv", index=False, lineterminator="\n")
    etapas.to_csv(RES / "limpeza.csv", index=False, lineterminator="\n")
    log("LIMPEZA (PRs restantes por etapa)")
    log(etapas.to_string(index=False))
    log(f"Linhas idênticas removidas de pr_commit_details: {info['linhas_duplicadas']}")
    log(f"Linhas de arquivos de lock/gerados excluídas: {info['linhas_lock_gerados']:,}")
    log()

    rng = np.random.default_rng(SEMENTE)
    desc = descritiva(df)
    res, pares = analisar(df, rng)
    desc.to_csv(RES / "descritiva.csv", index=False, lineterminator="\n")
    pares.to_csv(RES / "pares.csv", index=False, lineterminator="\n")
    relatar("ANÁLISE CONFIRMATÓRIA (planejada no protocolo)", res, desc, pares)
    figura(desc)
    amostra_validacao(arq, set(df["id"]), rng).to_csv(RES / "amostra_validacao_regra.csv", index=False, lineterminator="\n")

    # Exploratória: mantém os PRs que atingiram o limite de 30 commits.
    df_s, etapas_s, _, _ = limpar(pr, det, excluir_limite=False)
    res_s, pares_s = analisar(df_s, np.random.default_rng(SEMENTE))
    relatar("ANÁLISE EXPLORATÓRIA DE SENSIBILIDADE (inclui PRs no limite de 30 commits)",
            res_s, descritiva(df_s), pares_s)

    exploratoria_repositorios(df)

    (RES / "resultado.txt").write_text("\n".join(saida) + "\n", encoding="utf-8", newline="\n")
    print(f"\nResultados em {RES}/, figura em {FIG}/vd_por_agente.png")


if __name__ == "__main__":
    main()
