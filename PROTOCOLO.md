# Protocolo do Projeto Final — MCEQ 12576

**Equipe:** Gustavo Kurten Mendes (RA 24008150), João Celso (RA 24012463) e Leonardo Mateus (RA 24007335)

**Registro:** base, VI, VD, desenho e teste previsto em 27/10/2026 (documento de fontes); limpeza em 09/11/2026 (ficha de proveniência); regras de classificação, critério entre ANOVA e Kruskal-Wallis, pares e medidas de efeito complementados em 15/11/2026, antes da primeira execução de `analise.py`.

## Campos herdados da Ficha de Hipótese, atualizados

| Campo | Registro |
| --- | --- |
| Problema | Peng et al. (2023) mediram o ganho de produtividade com IA sem olhar para testes, e LLMs em teste unitário são avaliados sobretudo em benchmarks (Zhang et al., 2025). Estudos com a base AIDev passaram a examinar testes em PRs de agentes (Haque et al., 2026); este projeto compara os agentes entre si pela proporção de linhas de teste, com teste de hipótese. |
| Pergunta | Em PRs de funcionalidade e de correção abertos por agentes de IA em projetos open source, a proporção das linhas adicionadas que está em arquivos de teste difere entre Codex, Copilot, Devin, Cursor e Claude Code? |
| H0 / H1 | H0: µCodex = µCopilot = µDevin = µCursor = µClaude Code (no Kruskal-Wallis, distribuições iguais). H1, bilateral: ao menos um agente difere. |
| VI e níveis | Agente que abriu o PR, 5 níveis. |
| VD e unidade | Proporção das linhas adicionadas no PR que estão em arquivos de teste, de 0 a 1. |
| Controle / moderadora | Recorte: repositórios com mais de 100 estrelas e PRs feat ou fix. Sem moderadora: a base não traz a experiência de quem usou o agente. |
| O que mudou em relação à ficha | A ficha previa experimento com estudantes, com e sem assistente (VD: tempo até 80% de cobertura; H1 unilateral). Pela regra R4 os dados têm de ser públicos, e não achamos base com essa medida. Mantido: o problema. Mudaram o contexto (PRs reais), a VI (agente contra agente), a VD e a H1 (bilateral, sem direção esperada entre agentes); a moderadora saiu. Não comparamos com PRs humanos porque o dicionário da base não documenta os arquivos alterados desses PRs e porque PRs rotulados como humanos podem conter código de agentes (Ghaleb, 2026). |

## Campos novos

| Campo | Registro |
| --- | --- |
| Base | AIDev (Li, Zhang e Hassan, 2026), subconjunto curado; Hugging Face `hao-li/AIDev`, tag v3, commit `3ca0045`; acesso em 09/11/2026; CC BY 4.0. |
| Justificativa | Artigo e versão fixa; dicionário de variáveis; licença aberta; mais de 300 PRs por agente no recorte; VD derivável do caminho e das linhas adicionadas; coleta documentada. Da v4 em diante a base não traz o tipo do PR. |
| Tipo de estudo | Observacional. |
| Desenho | k tratamentos independentes, k = 5. |
| Unidade e n por grupo | O PR; n após a limpeza em `resultados/limpeza.csv`. |
| Teste previsto, α | ANOVA de um fator, α = 0,05, estatística F; pares por Tukey HSD. |
| Teste alternativo | Se Levene (centro na mediana) ou D'Agostino-Pearson nos resíduos der p < 0,05: Kruskal-Wallis, com Dunn e correção de Holm nos pares. |
| Efeito e IC | η² ou ε² = H/(n − 1), com IC95% bootstrap (2.000 reamostragens por grupo, semente 2026); por par, δ de Cliff e diferença de médias com IC95% de Welch; figura com média e IC95% por agente. |
| Ameaças iniciais | Conclusão: muitos testes (Holm nos pares). Interna: estudo observacional; linguagem, projeto, período (Codex só desde 16/05/2025) e autosseleção. Construção: agente identificado por assinatura; tipo do PR classificado por LLM; coleta limitada a 30 commits; regra de caminho. Externa: repositórios públicos com mais de 100 estrelas, cinco agentes, dez/2024 a jul/2025. |

**Validação da regra:** conferência manual de 100 arquivos (50 classificados como teste e 50 não, semente 2026). A ficha de proveniência previa amostra aleatória simples; estratificamos para estimar também os testes que a regra deixa passar.

**Exploratórias:** (i) incluir os PRs com 30 commits, definida antes da execução; (ii) concentração por repositório e um ponto por par repositório-agente, definidas em 15/11/2026, depois de ver os resultados.

**Ameaças vistas depois da análise (15/11/2026):** PRs do mesmo repositório não são independentes, e 47% dos PRs do Codex vêm de um só repositório; a regra conta fixtures e saídas esperadas em pastas de teste como linhas de teste.
