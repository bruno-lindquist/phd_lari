# Cut Precision

Pipeline em Python para comparar contorno ideal (template) vs contorno real (recorte), com métricas objetivas de erro e score IPN.

## Requisitos

- Python 3.11+
- Dependências em `pyproject.toml`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
pip install -e . --no-deps
```

Para ambiente de runtime (sem dependencias de desenvolvimento):

```bash
pip install -r requirements.lock
pip install -e . --no-deps
```

## Execução do pipeline

Exemplo básico:

```bash
cut-precision \
  --template original.jpeg \
  --test teste_1.jpg \
  --out out
```

Exemplo com calibração automática de `tau` por relatórios rotulados e política:

```bash
cut-precision \
  --template original.jpeg \
  --test teste_1.jpg \
  --out out \
  --tau-auto-good-reports "dataset/good/*.json" \
  --tau-auto-bad-reports "dataset/bad/*.json" \
  --tau-auto-policy balanced \
  --tau-auto-prefer-px
```

## Calibração de `tau` (CLI dedicada)

Calibrar por alvo de IPN:

```bash
cut-precision-calibrate-tau \
  --reports "runs/*/report.json" \
  --target-ipn 80
```

Calibrar por classes (`good` vs `bad`) com política:

```bash
cut-precision-calibrate-tau \
  --good-reports "dataset/good/*.json" \
  --bad-reports "dataset/bad/*.json" \
  --accept-ipn 70 \
  --policy strict
```

Políticas disponíveis:

- `strict`: prioriza baixa aceitação de ruins (mais conservadora)
- `balanced`: equilíbrio entre separação e acurácia
- `lenient`: critério mais permissivo

Você pode sobrescrever parâmetros da política, por exemplo:

```bash
cut-precision-calibrate-tau \
  --good-reports "dataset/good/*.json" \
  --bad-reports "dataset/bad/*.json" \
  --policy balanced \
  --min-tpr 0.8
```

## Saídas

Em `--out`:

- `report.json` (métricas, calibração, registro, diagnóstico)
- `overlay.png`
- `error_map.png`
- `error_hist.png`
- `distances.csv`
- `run.log` (texto)
- `run.jsonl` (estruturado para ingestão)

## Testes

```bash
.venv/bin/python -m pytest -q
```

## Qualidade

Lint:

```bash
.venv/bin/ruff check src tests
```

Tipagem (escopo core):

```bash
.venv/bin/mypy
```

Cobertura dos modulos core (gate >= 85%):

```bash
.venv/bin/python -m pytest -q \
  --cov=cut_precision.calibration \
  --cov=cut_precision.io_utils \
  --cov=cut_precision.report \
  --cov=cut_precision.visualize \
  --cov-report=term-missing \
  --cov-fail-under=85
```
