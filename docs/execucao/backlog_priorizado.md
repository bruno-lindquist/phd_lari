# Backlog Priorizado - Execucao do Plano

## Prioridade P0 (imediata)
- [x] `SEC-01`: corrigir dependencia vulneravel (`pillow >= 12.1.1`) e validar com `pip-audit`.
- [x] `SEC-02`: adotar lockfile reproduzivel e instalar a partir do lock no ambiente local/CI.
- [x] `SEC-03`: adicionar gate de CVE alta/critica na CI.

## Prioridade P1 (alta)
- [x] `ARQ-01`: quebrar `cli.py` em camadas (args, service, report builder).
- [x] `RES-01`: remover `except Exception` generico sem contexto.
- [x] `OBS-01`: implantar logging estruturado com Loguru (console + arquivo + jsonl + run_id).
- [x] `CFG-01`: validar ranges e coerencia de configuracao com falha antecipada.

## Prioridade P2 (media)
- [x] `DRY-01`: centralizar calibracao de tau em service unico para `cli.py` e `tau_cli.py`.
- `QLT-01`: mover magic numbers para configuracao tipada/documentada.
- [x] `TST-01`: ampliar testes para `calibration`, `io_utils`, `report`, `visualize` e caminhos de erro.

## Prioridade P3 (baixa)
- `PERF-01`: substituir deduplicacoes O(n^2) no `tau.py` por estruturas O(1) com `set`.
- [x] `DOC-01`: atualizar documentacao operacional final com fluxo de release.

## Criterio minimo de aprovacao por fase (DoD)
- Codigo DRY: sem duplicacao desnecessaria introduzida na fase.
- Nomenclatura clara: pastas, arquivos, classes, funcoes e variaveis autoexplicativos.
- Testes: todos os testes existentes verdes; novos testes para a mudanca da fase.
- Logs: eventos de inicio/fim/falha da fase com nivel adequado.
- Evidencia: arquivo de execucao da fase atualizado em `docs/execucao/`.

## Ordem de execucao recomendada
1. Fase 2 (seguranca e reprodutibilidade)
2. Fase 3 (observabilidade com Loguru)
3. Fase 4 (refatoracao arquitetural)
4. Fase 5 (validacao de configuracao)
5. Fase 6 (DRY da calibracao de tau)
6. Fase 7 (resiliencia e erros)
7. Fase 8 (cobertura e gates finais)
