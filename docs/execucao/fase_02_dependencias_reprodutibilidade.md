# Fase 2 - Seguranca de Dependencias e Reprodutibilidade

## Data da execucao
- `2026-02-11` (local)

## Objetivo da fase
- Corrigir vulnerabilidades conhecidas de dependencias.
- Padronizar instalacao por lockfile para ambiente local e CI.
- Adicionar gate automatizado de auditoria de vulnerabilidades.

## Mudancas realizadas
1. Atualizada dependencia de runtime no projeto:
   - `pillow>=12.1.1` em `pyproject.toml`.
2. Adicionada ferramenta de auditoria no grupo dev:
   - `pip-audit>=2.9.0` em `pyproject.toml`.
3. Gerados lockfiles a partir do `pyproject.toml` (fonte unica de verdade):
   - `requirements.lock`
   - `requirements-dev.lock`
4. Atualizado setup no `README.md` para instalar via lockfile.
5. Atualizado `executar_pipeline.command` para preferir `requirements-dev.lock`.
6. Criado workflow de CI:
   - `.github/workflows/ci.yml` com jobs de `tests` e `dependency-audit`.

## Evidencias de validacao
- Instalacao por lockfile concluida com sucesso:
  - `pip install -r requirements-dev.lock`
  - `pip install -e . --no-deps`
- Suite de testes:
  - `24 passed in 92.05s`
- Auditoria de vulnerabilidades:
  - `No known vulnerabilities found`

## Observacao tecnica
- Para gerar lockfiles com `pip-tools`, foi necessario usar `pip 25.x` no ambiente local devido incompatibilidade observada com `pip 26` durante `pip-compile`.

## Criterio de pronto da fase
- [x] Dependencias vulneraveis corrigidas.
- [x] Lockfile versionado para instalacao reproduzivel.
- [x] Auditoria de vulnerabilidades integrada ao CI.
- [x] Regra de bloqueio de vulnerabilidade ativa no CI (`pip-audit`).

## Arquivos impactados
- `pyproject.toml`
- `requirements.lock`
- `requirements-dev.lock`
- `README.md`
- `executar_pipeline.command`
- `.github/workflows/ci.yml`
