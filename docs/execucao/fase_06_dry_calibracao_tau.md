# Fase 6 - DRY da Calibracao de Tau

## Data da execucao
- `2026-02-11` (local)

## Objetivo da fase
- Remover duplicacao da logica de calibracao de `tau` entre `pipeline` e `tau_cli`.
- Centralizar defaults e contratos de payload em um unico service.
- Garantir equivalencia funcional com testes de regressao cruzada.

## Mudancas realizadas
1. Criado `src/cut_precision/tau_service.py` como ponto unico para calibracao:
   - `calibrate_target_tau_from_patterns(...)`
   - `calibrate_labeled_tau_from_patterns(...)`
   - `build_target_tau_payload(...)`
   - `build_labeled_tau_payload(...)`
2. Defaults compartilhados movidos para constantes unicas no service:
   - `DEFAULT_TARGET_IPN`, `DEFAULT_ACCEPT_IPN`
   - `DEFAULT_TAU_MIN`, `DEFAULT_TAU_MAX`
   - `DEFAULT_CURVE_MAX_POINTS`, `DEFAULT_TAU_STATISTIC`
3. `src/cut_precision/cli_args.py` atualizado para consumir os defaults do service.
4. `src/cut_precision/pipeline_service.py` atualizado para consumir apenas o service de calibracao (target e labeled), eliminando duplicacao de fluxo.
5. `src/cut_precision/tau_cli.py` simplificado para orquestrar argumentos + logging, delegando regra de negocio ao service.
6. `src/cut_precision/pipeline_context.py` mantido tipado com `TauCalibrationContext` e alimentado com saidas do service.

## Testes adicionados/atualizados
- `tests/test_cli_tau_policy.py`:
  - `test_pipeline_and_tau_cli_target_mode_match_tau`
  - `test_pipeline_and_tau_cli_labeled_mode_match_tau`
- Cobertura de paridade: mesmo conjunto de relatórios e parametros resulta no mesmo `tau` entre `tau_cli` e `pipeline`.

## Validacao executada
- Teste focado na fase:
  - `4 passed in 258.26s`
- Suite completa:
  - `31 passed in 275.13s`
- Auditoria de dependencias:
  - `No known vulnerabilities found`

## Criterio de pronto da fase
- [x] `tau_service` criado.
- [x] Defaults unificados em constantes compartilhadas.
- [x] CLIs consumindo service central.
- [x] Testes de equivalencia adicionados.

## Arquivos impactados
- `src/cut_precision/tau_service.py`
- `src/cut_precision/cli_args.py`
- `src/cut_precision/pipeline_context.py`
- `src/cut_precision/pipeline_service.py`
- `src/cut_precision/tau_cli.py`
- `tests/test_cli_tau_policy.py`
- `plano_execucao_melhoria_codigo.md`
- `docs/execucao/backlog_priorizado.md`
