# Fase 3 - Observabilidade Base com Loguru

## Data da execucao
- `2026-02-11` (local)

## Objetivo da fase
- Padronizar logging estruturado.
- Incluir `run_id` por execucao.
- Registrar inicio/fim/falha por etapa.
- Persistir logs em console, arquivo texto e JSONL.

## Mudancas realizadas
1. Adicionada dependencia de runtime:
   - `loguru>=0.7.2` em `pyproject.toml`.
2. Criado modulo central de logging:
   - `src/cut_precision/logging_config.py`
   - `setup_logging(out_dir, run_id, debug)`
   - `log_stage(log, stage)` para eventos start/end/error com duracao.
3. Pipeline CLI instrumentada:
   - eventos de `pipeline.start` e `pipeline.end`.
   - etapas: `image.load`, `extract.ideal`, `extract.real`, `register`, `resample`, `distance.compute`, `metrics.compute`, `artifacts.write`.
   - eventos de `artifact.write` para arquivos gerados.
4. Tau CLI instrumentada:
   - eventos de inicio/fim/erro.
   - etapas `tau.target_ipn` e `tau.labeled`.
   - novos argumentos `--log-dir` e `--debug`.
5. `report.json` passou a incluir:
   - `run_id`
   - caminhos de `run.log` e `run.jsonl` em `artifacts`.
6. README atualizado com os novos artefatos de log.

## Validacao executada
- Instalacao do ambiente por lockfile:
  - `pip install -r requirements-dev.lock`
  - `pip install -e . --no-deps`
- Testes:
  - `24 passed in 93.21s`
- Auditoria de vulnerabilidades:
  - `No known vulnerabilities found`
- Smoke test do pipeline com logs:
  - comando: `python -m cut_precision.cli --template original.jpeg --test teste_1.jpg --out out/loguru_smoke --no-kd-validate`
  - arquivos gerados: `out/loguru_smoke/run.log` e `out/loguru_smoke/run.jsonl`.

## Criterio de pronto da fase
- [x] `run.log` e `run.jsonl` gerados por execucao.
- [x] Eventos de inicio/fim/falha por etapa implementados.
- [x] `run_id` presente nos eventos.
- [x] Logs estruturados aptos para ingestao.

## Arquivos impactados
- `src/cut_precision/logging_config.py`
- `src/cut_precision/cli.py`
- `src/cut_precision/tau_cli.py`
- `pyproject.toml`
- `requirements.lock`
- `requirements-dev.lock`
- `README.md`
