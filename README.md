# mceq-aidev-testes

Projeto final de MCEQ 12576 (Métodos de Computação Experimental e Quantitativa), PUC-Campinas, 2º semestre de 2026.
Equipe: Gustavo Kurten Mendes, João Celso e Leonardo Mateus.

## Pergunta

Em pull requests de funcionalidade e de correção abertos por agentes de IA em projetos open source, a proporção de código de teste difere entre os agentes (OpenAI Codex, GitHub Copilot, Devin, Cursor e Claude Code)?

Estudo observacional: os grupos não foram sorteados, então os resultados indicam associação, não causa.

## Dados

- Base: AIDev (Li, Zhang e Hassan, MSR 2026), subconjunto curado (repositórios com mais de 100 estrelas).
- Origem: Hugging Face, `hao-li/AIDev`, tag v3, commit `3ca0045773097b138b064550dfd6e72229f40bee` (fixado em `dados/VERSAO.txt`).
- Licença: CC BY 4.0. Data de acesso: 09/11/2026.
- Os dados brutos (cerca de 500 MB) não ficam no repositório: `proveniencia.py` baixa a versão fixada.

## Como reproduzir

Requer Python 3.10 ou mais recente.

```
python -m venv .venv
.venv\Scripts\activate          (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python proveniencia.py          baixa os dados e gera saida_proveniencia.txt
python analise.py               limpeza, testes e figura (cerca de 3 minutos)
```

O `requirements.txt` fixa as versões exatas usadas no artigo. Com elas, `python analise.py` reproduz os arquivos de `resultados/` byte a byte; `git status` não deve mostrar nenhuma mudança neles depois da execução.

## Arquivos

- `PROTOCOLO.md`: o plano da análise registrado antes de rodar `analise.py`, com o que mudou em relação à Ficha de Hipótese.
- `proveniencia.py`: baixa a base na versão fixada e conta tamanho, ausentes, duplicados e período (ficha de proveniência).
- `analise.py`: aplica a limpeza do protocolo, calcula a VD, roda os testes e gera a figura. A semente (2026) é fixa.
- `resultados/resultado.txt`: todos os números do artigo, incluindo as análises exploratórias.
- `resultados/limpeza.csv`, `descritiva.csv`, `pares.csv`: tabelas da limpeza, da descritiva e das comparações par a par.
- `resultados/amostra_validacao_regra.csv`: 100 arquivos sorteados para conferência manual da regra de arquivo de teste.
- `dados/limpos/prs_limpos.csv`: um PR por linha, com a VD.
- `figuras/vd_por_agente.png`: média da VD por agente com IC de 95%.
