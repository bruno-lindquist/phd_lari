# Cut Precision

Pipeline em Python para comparar o contorno ideal (template) com o contorno real (recorte), gerando métricas objetivas de erro e score IPN com artefatos visuais e logs estruturados.

## Sumário

- [Visão Geral](#visão-geral)
- [Principais Funcionalidades](#principais-funcionalidades)
- [Status do Projeto e Compatibilidade](#status-do-projeto-e-compatibilidade)
- [Arquitetura (Alto Nível)](#arquitetura-alto-nível)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Como Rodar](#como-rodar)
- [Saídas e Artefatos](#saídas-e-artefatos)
- [Como Testar](#como-testar)
- [Lint, Tipagem e Quality Gates](#lint-tipagem-e-quality-gates)
- [Build e Empacotamento](#build-e-empacotamento)
- [Logs e Observabilidade](#logs-e-observabilidade)
- [Deploy](#deploy)
- [Troubleshooting / Problemas Comuns](#troubleshooting--problemas-comuns)
- [Roadmap](#roadmap)
- [Versionamento e Release](#versionamento-e-release)
- [Contribuindo](#contribuindo)
- [Segurança](#segurança)
- [Licença](#licença)
- [Créditos / Agradecimentos](#créditos--agradecimentos)

## Visão Geral

Este projeto existe para medir, de forma reproduzível, a precisão de corte entre:

1. Um contorno de referência (imagem template).
2. Um contorno real (imagem do recorte).

O pipeline executa extração de contornos, alinhamento geométrico, cálculo de distâncias, normalização por escala (IPN), geração de relatório estruturado (`report.json`) e artefatos visuais (`overlay`, mapa de erro, histograma), além de logs de execução em texto e JSONL.

## Principais Funcionalidades

- Extração separada de contorno ideal e contorno real.
- Registro/alinhamento com múltiplos métodos:
  - `orb_homography` (principal)
  - `axes_fallback`
  - `ecc_fallback`
  - `identity_fallback` (fallback final)
- Seleção automática do melhor registro por menor MAD de contorno.
- Cálculo de distância principal via Distance Transform.
- Validação opcional via KDTree (`validate_with_kdtree`).
- Métricas:
  - `mad`, `std`, `p95`, `max`
  - diagnósticos bidirecionais (`real->ideal`, `ideal->real`, Hausdorff)
  - IPN (com clamp e tolerância relativa `tau`)
- Calibração `px -> mm`:
  - automática por régua detectada
  - manual via `--manual-mm-per-px`
- Auto-calibração de `tau`:
  - por alvo de IPN
  - por classes (`good` vs `bad`) com políticas (`strict`, `balanced`, `lenient`)
- CLI dedicada para calibração de `tau`.
- Logs com `loguru`:
  - console
  - `run.log`
  - `run.jsonl` estruturado
- CI com gates de qualidade e auditoria de dependências.

## Status do Projeto e Compatibilidade

| Item | Estado observado |
|---|---|
| Versão do pacote | `0.1.0` |
| Versão Python requerida | `>=3.11` |
| CI | GitHub Actions em `python-version: "3.11"` |
| Fases de hardening/documentadas | Fases 1 a 8 marcadas como concluídas em `2026-02-11` (`docs/execucao/`) |
| Lockfiles | `requirements.lock` e `requirements-dev.lock` versionados |

**TODO:** definir formalmente o rótulo de maturidade (`alpha`, `beta`, `prod`) no README e no processo de release.  
Como descobrir: alinhar com mantenedores e registrar decisão junto à versão.

**Compatibilidade de SO:**

- CLI Python: sem matriz oficial de SO no repositório.
- Scripts `.command`: voltados a ambiente com `bash` e fluxo típico de macOS.
- **TODO:** validar oficialmente Linux/Windows e publicar matriz de suporte.

## Arquitetura (Alto Nível)

```text
[template + test]
       |
       v
[load images]
       |
       v
[extract ideal] + [extract real]
       |
       v
[registration candidates: ORB -> AXES -> ECC]
       |
       v
[select best by contour MAD]
       |
       v
[resample contours]
       |
       v
[distance transform + optional KDTree validation]
       |
       v
[metrics + calibration mm/px + IPN]
       |
       v
[artifacts + report.json + run.log + run.jsonl]
```

### Fluxo resumido

1. Carrega imagens e configuração (`AppConfig`).
2. Extrai contornos ideal/real.
3. Tenta registro por ORB e fallbacks.
4. Reamostra contornos.
5. Mede distâncias e valida (opcionalmente) com KDTree.
6. Calcula métricas e IPN.
7. Salva artefatos e relatório.
8. Em caso de falha na extração, gera `report.json` com `status: "failed"` e encerra com código `2`.

## Estrutura do Repositório

```text
.
├── .github/workflows/ci.yml
├── config/
│   └── default.json
├── docs/
│   ├── plano_projeto_comparacao_corte.md
│   ├── plano_execucao_melhoria_codigo.md
│   └── execucao/
│       ├── backlog_priorizado.md
│       ├── checklist_release.md
│       ├── fase_01_baseline.md
│       ├── fase_02_dependencias_reprodutibilidade.md
│       ├── fase_03_observabilidade_loguru.md
│       ├── fase_04_refatoracao_arquitetural.md
│       ├── fase_05_validacao_configuracao.md
│       ├── fase_06_dry_calibracao_tau.md
│       ├── fase_07_resiliencia_erros_io.md
│       └── fase_08_testes_qualidade_gate.md
├── executar_pipeline.command
├── limpar_projeto.command
├── pyproject.toml
├── requirements.lock
├── requirements-dev.lock
├── src/cut_precision/
│   ├── __main__.py
│   ├── cli.py
│   ├── cli_args.py
│   ├── pipeline_service.py
│   ├── report_builder.py
│   ├── pipeline_context.py
│   ├── config.py
│   ├── logging_config.py
│   ├── extract.py
│   ├── register.py
│   ├── calibration.py
│   ├── resample.py
│   ├── distance.py
│   ├── metrics.py
│   ├── visualize.py
│   ├── report.py
│   ├── tau.py
│   ├── tau_service.py
│   ├── tau_export.py
│   └── tau_cli.py
└── tests/
    ├── test_cli_tau_policy.py
    ├── test_tau_calibration.py
    ├── test_registration_selection.py
    ├── test_register_axes.py
    ├── test_distance_transform.py
    ├── test_extract_ideal.py
    ├── test_resample.py
    ├── test_metrics.py
    ├── test_ipn.py
    ├── test_config_validation.py
    ├── test_calibration_io_report.py
    └── test_resilience_io.py
```

## Requisitos

### Runtime

Dependências diretas (de `pyproject.toml`):

- `numpy>=1.26`
- `opencv-python>=4.9`
- `scipy>=1.11`
- `matplotlib>=3.8`
- `scikit-image>=0.22`
- `pillow>=12.1.1`
- `loguru>=0.7.2`

### Desenvolvimento

- `pytest>=8.0`
- `pytest-cov>=5.0`
- `ruff>=0.9.7`
- `mypy>=1.14.1`
- `pip-audit>=2.9.0`

### Reprodutibilidade

- Use lockfiles versionados:
  - `requirements.lock` (runtime)
  - `requirements-dev.lock` (dev)

## Instalação

### 1) Ambiente de desenvolvimento (recomendado)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
pip install -e . --no-deps
```

### 2) Ambiente de runtime (sem dependências de dev)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install -e . --no-deps
```

### 3) Instalação via script local

```bash
./executar_pipeline.command
```

O script:

- cria `.venv` se necessário;
- instala dependências (preferindo `requirements-dev.lock`);
- instala o projeto em modo editável;
- executa o pipeline;
- grava saída em `out/<timestamp>/`.

## Configuração

### Variáveis de ambiente

| NOME | O que faz | Default | Obrigatória | Exemplo |
|---|---|---|---|---|
| `PYTHON_BIN` | Define o executável Python usado por `executar_pipeline.command` | `python3` | Não | `PYTHON_BIN=/usr/bin/python3 ./executar_pipeline.command` |

**Observação:** o pacote/CLI não depende de `.env` nem de variáveis de ambiente obrigatórias para rodar.

### Arquivos de configuração suportados

- `--config <arquivo>` aceita:
  - `.json`
  - `.yaml` / `.yml`
- Exemplo oficial no repositório: `config/default.json`.

**Importante:** YAML exige `PyYAML`, que não está nas dependências padrão.  
Se usar YAML:

```bash
pip install pyyaml
```

### Precedência de configuração

1. Defaults internos (`AppConfig`).
2. Sobrescrita parcial via arquivo de config (`--config`).
3. Sobrescrita via CLI:
   - `--step-px`
   - `--num-points`
   - `--tau`
   - `--manual-mm-per-px`
   - `--no-kd-validate`
4. Auto-calibração de `tau` (`--tau-auto-*`) sobrescreve `--tau`.

### Parâmetros de `config/default.json`

Todos os campos abaixo têm default e não são obrigatórios no arquivo (pode sobrescrever parcialmente).

#### `extraction`

| Chave | O que faz | Default | Obrigatória | Exemplo |
|---|---|---|---|---|
| `ideal_adaptive_block_size` | Tamanho do bloco da limiarização adaptativa (ímpar) | `35` | Não | `35` |
| `ideal_adaptive_c` | Constante C do threshold adaptativo | `7` | Não | `7` |
| `ideal_close_kernel` | Kernel de fechamento no ideal | `5` | Não | `5` |
| `ideal_dilate_kernel` | Kernel de dilatação no ideal | `3` | Não | `3` |
| `ideal_min_area_ratio` | Área mínima relativa para componentes | `0.001` | Não | `0.001` |
| `ideal_group_area_ratio_to_max` | Limiar relativo de área para grupo de componentes centrais | `0.35` | Não | `0.35` |
| `ideal_group_center_radius_ratio` | Raio relativo para filtro por centralidade | `0.45` | Não | `0.45` |
| `ideal_group_close_kernel` | Kernel de fechamento do grupo ideal | `9` | Não | `9` |
| `line_removal_min_length_ratio` | Razão mínima para remover linhas longas (Hough) | `0.3` | Não | `0.3` |
| `line_removal_thickness` | Espessura da máscara de remoção de linhas | `3` | Não | `3` |
| `real_lab_l_threshold` | Threshold de luminosidade L no LAB para recorte real | `95` | Não | `95` |
| `real_hsv_v_threshold` | Threshold de canal V no HSV para recorte real | `90` | Não | `90` |
| `real_close_kernel` | Kernel de fechamento no real | `5` | Não | `5` |
| `real_open_kernel` | Kernel de abertura no real | `3` | Não | `3` |

#### `registration`

| Chave | O que faz | Default | Obrigatória | Exemplo |
|---|---|---|---|---|
| `orb_nfeatures` | Nº de features ORB | `3000` | Não | `3000` |
| `knn_ratio` | Ratio test no matching ORB | `0.75` | Não | `0.75` |
| `ransac_reproj_threshold` | Threshold de reprojeção no RANSAC | `3.0` | Não | `3.0` |
| `min_matches` | Mínimo de matches para homografia | `20` | Não | `20` |
| `min_inlier_ratio` | Mínima razão de inliers | `0.2` | Não | `0.2` |
| `use_axes_fallback` | Habilita fallback por eixos | `true` | Não | `true` |
| `axes_canny_low` | Canny low no fallback de eixos | `50` | Não | `50` |
| `axes_canny_high` | Canny high no fallback de eixos | `150` | Não | `150` |
| `axes_hough_threshold` | Threshold de Hough no fallback de eixos | `120` | Não | `120` |
| `axes_segment_min_line_ratio` | Razão mínima de comprimento de linha | `0.05` | Não | `0.05` |
| `axes_max_line_gap` | Gap máximo entre segmentos | `15` | Não | `15` |
| `axes_angle_tolerance_deg` | Tolerância angular para detectar eixos | `20.0` | Não | `20.0` |
| `axes_horizontal_roi_min_y_ratio` | ROI mínima em Y para eixo horizontal | `0.65` | Não | `0.65` |
| `axes_vertical_roi_max_x_ratio` | ROI máxima em X para eixo vertical | `0.35` | Não | `0.35` |
| `use_ecc_fallback` | Habilita fallback ECC | `true` | Não | `true` |
| `ecc_motion` | Modo ECC (`translation`, `euclidean`, `affine`, `homography`) | `"affine"` | Não | `"affine"` |
| `ecc_iterations` | Iterações ECC | `1500` | Não | `1500` |
| `ecc_eps` | Critério de convergência ECC | `1e-06` | Não | `1e-06` |

#### `calibration`

| Chave | O que faz | Default | Obrigatória | Exemplo |
|---|---|---|---|---|
| `manual_mm_per_px` | Sobrescreve calibração automática | `null` | Não | `0.1082` |
| `ruler_mm` | Comprimento da régua de referência (mm) | `120.0` | Não | `120.0` |
| `canny_low` | Canny low para detecção da régua | `50` | Não | `50` |
| `canny_high` | Canny high para detecção da régua | `150` | Não | `150` |
| `hough_threshold` | Threshold Hough para régua | `80` | Não | `80` |
| `hough_max_gap` | Gap máximo Hough para régua | `10` | Não | `10` |
| `ruler_min_line_ratio` | Razão mínima de comprimento da linha da régua | `0.2` | Não | `0.2` |

#### `distance`

| Chave | O que faz | Default | Obrigatória | Exemplo |
|---|---|---|---|---|
| `draw_thickness` | Espessura para desenhar contorno ideal no mapa de distância | `1` | Não | `1` |
| `use_bilinear` | Usa amostragem bilinear no distance map | `true` | Não | `true` |
| `validate_with_kdtree` | Validação cruzada com KDTree | `true` | Não | `true` |
| `validation_tolerance_px` | Tolerância média absoluta DT vs KDTree | `1.5` | Não | `1.5` |

#### `metrics`

| Chave | O que faz | Default | Obrigatória | Exemplo |
|---|---|---|---|---|
| `tau` | Fator de tolerância relativa do IPN | `0.02` | Não | `0.02` |
| `clamp_low` | Limite inferior do IPN | `0.0` | Não | `0.0` |
| `clamp_high` | Limite superior do IPN | `100.0` | Não | `100.0` |

#### `sampling`

| Chave | O que faz | Default | Obrigatória | Exemplo |
|---|---|---|---|---|
| `step_px` | Passo de reamostragem por arco (quando `num_points` é `null`) | `1.5` | Não | `1.5` |
| `num_points` | Número fixo de pontos de contorno | `null` | Não | `1200` |
| `max_points` | Teto de pontos reamostrados | `20000` | Não | `20000` |

## Como Rodar

### CLI principal (`cut-precision`)

Execução mínima:

```bash
cut-precision \
  --template original.jpeg \
  --test teste_1.jpg \
  --out out
```

Com config JSON:

```bash
cut-precision \
  --template original.jpeg \
  --test teste_1.jpg \
  --out out \
  --config config/default.json
```

Com `tau` fixo e override manual de escala:

```bash
cut-precision \
  --template original.jpeg \
  --test teste_1.jpg \
  --out out \
  --tau 0.02 \
  --manual-mm-per-px 0.1082
```

Auto-calibração `tau` por alvo de IPN (a partir de relatórios):

```bash
cut-precision \
  --template original.jpeg \
  --test teste_1.jpg \
  --out out \
  --tau-auto-reports "runs/*/report.json" \
  --tau-auto-target-ipn 80 \
  --tau-auto-statistic median
```

Auto-calibração `tau` por classes (`good`/`bad`) com política e curva:

```bash
cut-precision \
  --template original.jpeg \
  --test teste_1.jpg \
  --out out \
  --tau-auto-good-reports "dataset/good/*.json" \
  --tau-auto-bad-reports "dataset/bad/*.json" \
  --tau-auto-policy balanced \
  --tau-auto-accept-ipn 70 \
  --tau-auto-curve-csv out/tau_curve.csv \
  --tau-auto-curve-png out/tau_curve.png
```

Executar com debug (salva artefato intermediário `real_mask.png`):

```bash
cut-precision \
  --template original.jpeg \
  --test teste_1.jpg \
  --out out \
  --debug
```

### CLI de calibração (`cut-precision-calibrate-tau`)

Modo alvo de IPN:

```bash
cut-precision-calibrate-tau \
  --reports "runs/*/report.json" \
  --target-ipn 80 \
  --statistic median
```

Modo por classes com política:

```bash
cut-precision-calibrate-tau \
  --good-reports "dataset/good/*.json" \
  --bad-reports "dataset/bad/*.json" \
  --accept-ipn 70 \
  --policy balanced
```

Com exportação de curva:

```bash
cut-precision-calibrate-tau \
  --good-reports "dataset/good/*.json" \
  --bad-reports "dataset/bad/*.json" \
  --accept-ipn 70 \
  --policy strict \
  --curve-csv out/tau_curve.csv \
  --curve-png out/tau_curve.png
```

Com diretório de logs da calibração:

```bash
cut-precision-calibrate-tau \
  --reports "runs/*/report.json" \
  --target-ipn 80 \
  --log-dir out/tau_logs \
  --debug
```

### Scripts utilitários

Pipeline automatizado local:

```bash
./executar_pipeline.command
```

Limpeza padrão:

```bash
./limpar_projeto.command
```

Limpeza completa (inclui `.venv/`):

```bash
./limpar_projeto.command --full
```

Ajuda do script de limpeza:

```bash
./limpar_projeto.command --help
```

### Códigos de saída

| Código | Situação |
|---|---|
| `0` | Execução concluída com sucesso |
| `2` | Falha de extração de contorno (pipeline gera `report.json` com `status: "failed"`) |
| `!=0` | Erro de argumento/configuração/IO/exceção em execução |

## Saídas e Artefatos

Em `--out` (ou `out/<timestamp>` no script `.command`):

- `report.json`: relatório completo (inputs, registro, calibração, métricas, artefatos, config efetiva).
- `overlay.png`: contornos ideal/real sobrepostos.
- `error_map.png`: mapa visual de erro por ponto.
- `error_hist.png`: histograma de distâncias.
- `distances.csv`: colunas `idx,x,y,d_px,d_mm`.
- `run.log`: log texto.
- `run.jsonl`: log estruturado serializado.

### Estrutura de alto nível do `report.json`

- `status`
- `run_id`
- `timestamp_utc`
- `version`
- `inputs`
- `registration`
- `calibration`
- `distance_method`
- `diagnostics`
- `metrics`
- `tau_calibration`
- `artifacts`
- `config`
- `git`

## Como Testar

### Testes unitários/integrados

```bash
.venv/bin/python -m pytest -q
```

### Cobertura (gate core >= 85%)

```bash
.venv/bin/python -m pytest -q \
  --cov=cut_precision.calibration \
  --cov=cut_precision.io_utils \
  --cov=cut_precision.report \
  --cov=cut_precision.visualize \
  --cov-report=term-missing \
  --cov-fail-under=85
```

### Escopo atual dos testes

- Métricas e IPN.
- Reamostragem.
- Distance transform.
- Seleção de registro.
- Fallback por eixos.
- Validação de configuração.
- Calibração e IO.
- Paridade entre CLI principal e CLI de `tau`.

**TODO:** não há suíte e2e formal separada (cenários fim a fim com dataset versionado).  
Como descobrir: criar pasta de fixtures estáveis e job dedicado no CI.

## Lint, Tipagem e Quality Gates

### Lint

```bash
.venv/bin/ruff check src tests
```

### Tipagem

```bash
.venv/bin/mypy
```

Observação: o `mypy` está configurado para um escopo core de módulos específicos em `pyproject.toml`.

### Auditoria de vulnerabilidades

```bash
.venv/bin/pip-audit -r requirements-dev.lock
```

### CI/CD atual

Arquivo: `.github/workflows/ci.yml`  
Triggers: `push` e `pull_request`.

Jobs:

1. `quality-gates`
2. `dependency-audit`

O job `quality-gates` executa:

- instalação por lockfile
- `ruff check src tests`
- `mypy`
- `pytest` com `--cov-fail-under=85`

O job `dependency-audit` executa:

- instalação por lockfile
- `pip-audit -r requirements-dev.lock`

## Build e Empacotamento

- Backend configurado: `setuptools.build_meta`.
- Requisitos de build: `setuptools>=68`, `wheel`.
- Entrypoints:
  - `cut-precision`
  - `cut-precision-calibrate-tau`

**TODO:** o repositório não documenta um comando oficial de build/distribuição no README.  
Como descobrir: validar fluxo de empacotamento e registrar um procedimento único de release (ex.: wheel/sdist).

## Logs e Observabilidade

### O que é gerado

- `run.log` (texto)
- `run.jsonl` (JSON serializado por evento)
- `run_id` único por execução
- eventos por etapa via contexto `log_stage(...)`

Etapas instrumentadas incluem:

- `image.load`
- `extract.ideal`
- `extract.real`
- `register`
- `resample`
- `distance.compute`
- `metrics.compute`
- `artifacts.write`

### Snippet seguro de configuração Loguru (stdout + arquivo + rotação/retenção)

```python
from pathlib import Path
import sys
from loguru import logger

def setup_logging(out_dir: Path, run_id: str, debug: bool = False):
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if debug else "INFO")
    logger.add(out_dir / "run.log", level="DEBUG", rotation="10 MB", retention="14 days")
    logger.add(
        out_dir / "run.jsonl",
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        serialize=True,
    )
    return logger.bind(run_id=run_id)

log = setup_logging(Path("out"), run_id="abc123def456")
log.bind(event="pipeline.start", stage="pipeline", status="started").info("pipeline_started")
log.bind(event="artifact.write", stage="artifacts.write", artifact="report_json").info("artifact_written")
```

## Deploy

Não há artefatos/manifests de deploy no repositório (Docker, Kubernetes, serverless etc.).

**TODO:** definir estratégia de deploy/distribuição.  
Como descobrir: decidir se o alvo é pacote Python (PyPI), serviço, ou execução local, e documentar pipeline correspondente.

## Troubleshooting / Problemas Comuns

| Sintoma / Erro | Causa comum | Como resolver |
|---|---|---|
| `Could not load image: ...` | caminho inválido para `--template` ou `--test` | validar path/arquivo e permissões |
| `Config file not found: ...` | `--config` aponta para arquivo inexistente | corrigir caminho |
| `Unsupported config extension: ...` | extensão não suportada | usar `.json`, `.yaml` ou `.yml` |
| `YAML config requested but PyYAML is not installed` | uso de YAML sem `PyYAML` | `pip install pyyaml` |
| `Use either --tau-auto-reports OR (--tau-auto-good-reports with --tau-auto-bad-reports)` | modos de auto-calibração misturados | escolher apenas um modo |
| `Both --tau-auto-good-reports and --tau-auto-bad-reports are required together` | faltou um dos conjuntos rotulados | informar os dois globs |
| `--curve-csv/--curve-png are only available in labeled mode` | export de curva em modo `--reports` | usar modo `good/bad` |
| `No valid reports found for tau calibration` | globs sem relatórios válidos | revisar paths e conteúdo dos `report.json` |
| Pipeline retorna `2` e `status: "failed"` | falha na extração (`no_ideal_contour_found` ou `no_real_contour_found`) | revisar qualidade/contraste da imagem e parâmetros de `extraction` |
| `Could not write image artifact: ...` | falha de escrita de arquivo de imagem | verificar permissões e espaço em disco |
| `ModuleNotFoundError` (ex.: `numpy`, `loguru`) | ambiente sem dependências | reinstalar usando lockfile |

## Roadmap

### Estado do plano documentado

As fases abaixo aparecem concluídas em `docs/plano_execucao_melhoria_codigo.md` e `docs/execucao/`:

1. Baseline técnico e preparação.
2. Segurança de dependências e reprodutibilidade.
3. Observabilidade com Loguru.
4. Refatoração arquitetural da orquestração.
5. Validação forte de configuração.
6. DRY da calibração de tau.
7. Resiliência e IO seguro.
8. Testes + quality gate + checklist de release.

### Próximos itens ainda não formalizados

- **TODO:** definir milestones pós-0.1.0 (features e critérios de promoção de maturidade).
- **TODO:** publicar roadmap público (issues/milestones).
- **TODO:** adicionar suíte e2e estável com dataset de referência versionado.

## Versionamento e Release

- Versão atual do pacote: `0.1.0` (em `pyproject.toml` e `src/cut_precision/__init__.py`).
- Checklist operacional de release: `docs/execucao/checklist_release.md`.
- Gate de release inclui:
  - lint
  - mypy
  - cobertura core
  - `pip-audit`
  - validação de artefatos de smoke run

Comandos de referência do checklist:

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

**TODO:** não há política explícita de tags/CHANGELOG no repositório.  
Como descobrir: definir convenção (`SemVer + tag + changelog`) e automatizar no CI.

## Contribuindo

**Estado atual:** não existe `CONTRIBUTING.md` no repositório.

Fluxo mínimo recomendado com base no checklist já versionado:

1. Instalar dependências via `requirements-dev.lock`.
2. Rodar lint, tipagem, testes/cobertura e `pip-audit`.
3. Garantir que mudanças de config e operação estejam refletidas no README.
4. Abrir PR com CI verde (`quality-gates` e `dependency-audit`).

**TODO:** criar `CONTRIBUTING.md` com padrão de branches, convenção de commits e template de PR.

## Segurança

- Dependências fixadas em lockfiles.
- Auditoria de vulnerabilidades (`pip-audit`) integrada ao CI.
- Log estruturado com campos de contexto e sem dump bruto de imagem.
- `out/`, `.venv/` e caches estão no `.gitignore`.

Boas práticas operacionais:

1. Não versionar dados sensíveis em imagens de teste.
2. Não registrar segredos/tokens em logs.
3. Rodar auditoria de dependências antes de release.

**TODO:** adicionar `SECURITY.md` com política de reporte de vulnerabilidades.

## Licença

**TODO:** o repositório não possui arquivo `LICENSE` visível.  
Como descobrir: confirmar com mantenedores e adicionar a licença escolhida (ex.: MIT/Apache-2.0) com texto completo.

## Créditos / Agradecimentos

- Projeto `cut-precision` (pacote `cut_precision`).
- Base técnica construída sobre `numpy`, `opencv-python`, `scipy`, `matplotlib`, `scikit-image`, `pillow` e `loguru`.
- Planejamento e execução técnica documentados em `docs/plano_projeto_comparacao_corte.md` e `docs/execucao/`.

**TODO:** listar mantenedores/autores oficialmente no repositório (seção `AUTHORS` ou equivalente).
