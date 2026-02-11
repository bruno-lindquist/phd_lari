# Fase 4 - Refatoracao Arquitetural da Orquestracao

## Data da execucao
- `2026-02-11` (local)

## Objetivo da fase
- Reduzir acoplamento de `cli.py`.
- Separar parser, orquestracao e construcao de relatorio.
- Tipar `tau_context` com dataclass dedicada.

## Mudancas realizadas
1. Parser extraido para modulo dedicado:
   - `src/cut_precision/cli_args.py` com `build_pipeline_parser`.
2. Orquestracao movida para camada de aplicacao:
   - `src/cut_precision/pipeline_service.py` com `run_pipeline(args)`.
3. Builder de relatorio extraido:
   - `src/cut_precision/report_builder.py` com:
     - `build_success_report(...)`
     - `build_failure_report(...)`
4. Contexto de calibracao tipado com dataclass:
   - `src/cut_precision/pipeline_context.py` com `TauCalibrationContext`.
5. `cli.py` convertido em fachada de interface:
   - parse de argumentos + delegacao para `run_pipeline`.
   - compatibilidade mantida para import de `_pick_best_registration_for_contour` usado nos testes.

## Compatibilidade preservada
- `cut_precision.cli:main` segue sendo entrypoint principal.
- Testes que importam `_pick_best_registration_for_contour` continuam validos.
- Assinatura da CLI nao foi alterada para usuarios finais.

## Validacao executada
- Testes:
  - `24 passed in 86.38s`
- Auditoria de dependencias:
  - `No known vulnerabilities found`
- Confirmacao de ausencia de logs indesejados na raiz:
  - `no-root-run-logs`

## Criterio de pronto da fase
- [x] Parsing movido para modulo dedicado.
- [x] Fluxo de pipeline movido para service.
- [x] Builder de relatorio extraido.
- [x] `tau_context` tipado com dataclass.
- [x] Compatibilidade de CLI validada por testes.

## Arquivos impactados
- `src/cut_precision/cli.py`
- `src/cut_precision/cli_args.py`
- `src/cut_precision/pipeline_service.py`
- `src/cut_precision/report_builder.py`
- `src/cut_precision/pipeline_context.py`
