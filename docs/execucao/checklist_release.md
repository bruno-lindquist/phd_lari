# Checklist de Release

## Objetivo
Padronizar o gate final antes de liberar alteracoes do `cut-precision`.

## Checklist obrigatorio
- [ ] Dependencias instaladas a partir de `requirements-dev.lock` (ou `requirements.lock` para runtime).
- [ ] `ruff check src tests` passou sem erros.
- [ ] `mypy` passou no escopo core configurado.
- [ ] `pytest` com gate de cobertura core passou (`>= 85%`).
- [ ] `pip-audit -r requirements-dev.lock` sem vulnerabilidades conhecidas.
- [ ] CI verde nos jobs `quality-gates` e `dependency-audit`.
- [ ] Artefatos esperados do pipeline validados em execucao de smoke:
  - [ ] `report.json`
  - [ ] `overlay.png`
  - [ ] `error_map.png`
  - [ ] `error_hist.png`
  - [ ] `distances.csv`
  - [ ] `run.log`
  - [ ] `run.jsonl`
- [ ] Mudancas de configuracao/documentacao refletidas no `README.md` e no plano de execucao.

## Comandos de referencia
```bash
.venv/bin/ruff check src tests
.venv/bin/mypy
.venv/bin/python -m pytest -q \
  --cov=cut_precision.calibration \
  --cov=cut_precision.io_utils \
  --cov=cut_precision.report \
  --cov=cut_precision.visualize \
  --cov-report=term-missing \
  --cov-fail-under=85
.venv/bin/pip-audit -r requirements-dev.lock
```
