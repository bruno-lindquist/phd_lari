# Fase 7 - Resiliencia, Tratamento de Erros e IO Seguro

## Data da execucao
- `2026-02-11` (local)

## Objetivo da fase
- Reduzir capturas genericas de excecao sem contexto.
- Tornar falhas de IO de artefatos explicitamente detectaveis.
- Cobrir caminhos de erro/fallback com testes.

## Mudancas realizadas
1. Revisao de `except Exception` sem contexto:
   - `src/cut_precision/pipeline_service.py` (`_git_commit`) atualizado para capturar apenas:
     - `FileNotFoundError`
     - `OSError`
     - `subprocess.CalledProcessError`
   - `src/cut_precision/tau.py` atualizado para capturar apenas:
     - `OSError`
     - `json.JSONDecodeError`
   - `src/cut_precision/tau_export.py` atualizado para capturar apenas `ImportError` no carregamento opcional de matplotlib.
   - `src/cut_precision/tau_cli.py` removeu `try/except Exception` de topo e passou a usar `log_stage("tau_calibration")` para logging estruturado de falha.
2. Endurecimento de IO em visualizacao (`src/cut_precision/visualize.py`):
   - criado `_write_image_or_raise(...)` com validacao de retorno de `cv2.imwrite`.
   - `save_mask(...)` e `save_overlay(...)` agora falham com `OSError` quando a escrita nao ocorre.
   - `save_error_map(...)` e `save_histogram(...)` passaram a garantir criacao de pasta pai antes de salvar.
3. Mantido apenas `except Exception` com contexto estruturado em `src/cut_precision/logging_config.py` (`log_stage`), para registrar erro da etapa com `event`, `stage`, `status` e `duration_ms`.

## Testes adicionados
- `tests/test_resilience_io.py`:
  - `test_git_commit_returns_none_when_git_unavailable`
  - `test_save_mask_raises_when_image_write_fails`
  - `test_save_overlay_raises_when_image_write_fails`

## Validacao executada
- Teste focado da fase:
  - `3 passed in 0.63s`
- Suite completa:
  - `34 passed in 268.19s`
- Auditoria de dependencias:
  - `No known vulnerabilities found`

## Criterio de pronto da fase
- [x] `except Exception` revisados e reduzidos.
- [x] Erros com contexto estruturado implementados.
- [x] Escrita de artefatos validada.
- [x] Testes de caminhos de falha criados.

## Arquivos impactados
- `src/cut_precision/pipeline_service.py`
- `src/cut_precision/tau.py`
- `src/cut_precision/tau_cli.py`
- `src/cut_precision/tau_export.py`
- `src/cut_precision/visualize.py`
- `tests/test_resilience_io.py`
- `plano_execucao_melhoria_codigo.md`
- `docs/execucao/backlog_priorizado.md`
