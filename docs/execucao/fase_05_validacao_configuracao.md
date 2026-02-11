# Fase 5 - Validacao Forte de Configuracao

## Data da execucao
- `2026-02-11` (local)

## Objetivo da fase
- Aplicar validacao fail-fast para parametros de configuracao.
- Garantir mensagens de erro claras por campo.
- Cobrir configuracoes invalidas com testes de unidade.

## Mudancas realizadas
1. `src/cut_precision/config.py` reestruturado com validadores por secao:
   - `ExtractionConfig.validate()`
   - `RegistrationConfig.validate()`
   - `CalibrationConfig.validate()`
   - `DistanceConfig.validate()`
   - `MetricsConfig.validate()`
   - `SamplingConfig.validate()`
   - `AppConfig.validate()`
2. `__post_init__` adicionado em cada dataclass para validacao imediata.
3. Regras implementadas:
   - faixas numericas e limites (ex.: `0..255`, `> 0`, `>= 0`)
   - coerencia entre campos (ex.: `canny_low < canny_high`)
   - restricoes de razao (`(0,1]` ou `[0,1]`)
   - validacao de opcoes enumeradas (`ecc_motion`)
4. Mensagens de erro padronizadas:
   - formato: `Invalid config '<campo>': <regra>. Got <valor>`

## Testes adicionados
- `tests/test_config_validation.py`:
  - config padrao valida
  - bloqueio de bloco adaptativo par
  - bloqueio de `ecc_motion` invalido
  - rejeicao de `metrics.tau <= 0`
  - rejeicao de ordem invalida em canny

## Validacao executada
- Testes:
  - `29 passed in 86.07s`
- Auditoria de dependencias:
  - `No known vulnerabilities found`

## Criterio de pronto da fase
- [x] Validacoes por secao implementadas.
- [x] Ranges e coerencia revisados.
- [x] Erros padronizados de configuracao criados.
- [x] Testes de config invalida adicionados.

## Arquivos impactados
- `src/cut_precision/config.py`
- `tests/test_config_validation.py`
