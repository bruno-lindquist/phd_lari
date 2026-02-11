# Plano de Execucao Detalhado - Melhoria de Codigo

## Objetivo
Executar a melhoria do projeto `cut-precision` em fases pequenas, verificaveis e com baixo risco de regressao, cobrindo arquitetura, qualidade, seguranca, performance, testes e observabilidade.

## Premissas de Execucao
- Base atual com testes passando (`pytest`).
- Nao realizar mudancas grandes sem validar cada fase com testes.
- Cada fase deve gerar artefatos objetivos (codigo, testes, documentos, logs).
- Ordem recomendada: Fase 1 ate Fase 8.

## Diretrizes Obrigatorias Transversais (todas as fases)
- DRY e obrigatorio: evitar duplicacao de regra de negocio, validacao, parsing e formatacao de payload.
- Sempre que for detectada duplicacao, extrair para funcao, classe, modulo ou service reutilizavel.
- Nomes de pastas, arquivos, classes, funcoes, variaveis e constantes devem ser claros, consistentes e autoexplicativos.
- Evitar abreviacoes ambiguas (`tmp`, `obj`, `val`, `data2`) quando houver alternativa descritiva.
- Em revisao de PR, qualquer excecao a DRY ou nomenclatura deve ser justificada por escrito.

**Checklist transversal obrigatorio (aplicar em cada fase)**
- [x] Nao foi introduzida duplicacao desnecessaria (DRY atendido).
- [x] Nomes novos/alterados sao autoexplicativos e consistentes com o dominio.
- [x] Estrutura de pastas e arquivos permanece clara e coerente.
- [x] Excecoes (se houver) foram justificadas tecnicamente no PR.

## Status de Execucao
- [x] Fase 1 - Baseline Tecnico e Preparacao
- [x] Fase 2 - Seguranca de Dependencias e Reprodutibilidade
- [x] Fase 3 - Observabilidade Base com Loguru
- [x] Fase 4 - Refatoracao Arquitetural da Orquestracao
- [x] Fase 5 - Validacao Forte de Configuracao
- [x] Fase 6 - DRY da Calibracao de Tau
- [x] Fase 7 - Resiliencia, Tratamento de Erros e IO Seguro
- [x] Fase 8 - Testes, Qualidade e Gate de Entrega

## Fase 1 - Baseline Tecnico e Preparacao
**Objetivo:** congelar o estado atual e preparar a execucao segura das proximas fases.

**Entradas**
- Repositorio atual.
- Suite de testes existente.
- Relatorio tecnico de melhorias.

**Passos (ordem de execucao)**
1. Rodar `pytest -q` e registrar resultado baseline.
2. Registrar versoes de runtime/dependencias (`python --version`, `pip freeze`).
3. Criar documento de backlog priorizado com IDs (ARQ-01, SEC-01, OBS-01, etc.).
4. Definir convencao de branch e PR (uma fase por PR).
5. Definir criterio minimo de aprovacao por fase.

**Saidas**
- Baseline de testes documentado.
- Baseline de dependencias documentado.
- Backlog priorizado por severidade e risco.

**Criterio de pronto**
- Estado baseline reproduzivel e documentado.
- Backlog e ordem de execucao aprovados.

**Checklist**
- [x] `pytest -q` executado e resultado salvo.
- [x] Snapshot de dependencias salvo.
- [x] Backlog com IDs e prioridade criado.
- [x] Criterios de aprovacao por fase definidos.

---

## Fase 2 - Seguranca de Dependencias e Reprodutibilidade
**Objetivo:** eliminar vulnerabilidades conhecidas e tornar o ambiente deterministico.

**Entradas**
- `pyproject.toml`.
- Resultado de auditoria de dependencias.

**Passos (ordem de execucao)**
1. Atualizar dependencias vulneraveis (ex.: `pillow >= 12.1.1`).
2. Definir estrategia de lockfile (`requirements.lock`, `uv.lock` ou equivalente).
3. Padronizar instalacao para ambiente local e CI a partir do lock.
4. Incluir auditoria automatica de CVE no pipeline (`pip-audit`).
5. Adicionar gate de falha para CVEs de severidade alta/critica.

**Saidas**
- Dependencias corrigidas.
- Lockfile versionado.
- Job de auditoria de seguranca ativo.

**Criterio de pronto**
- Nenhuma vulnerabilidade aberta de severidade alta/critica.
- Build reproduzivel a partir do lockfile.

**Checklist**
- [x] `pillow` atualizado para versao corrigida.
- [x] Lockfile gerado e commitado.
- [x] Auditoria de CVE integrada na CI.
- [x] Regra de bloqueio para CVEs alta/critica ativa.

---

## Fase 3 - Observabilidade Base com Loguru
**Objetivo:** padronizar logging estruturado para depuracao, auditoria e operacao.

**Entradas**
- Fluxo atual do pipeline (`cli.py`, `tau_cli.py`).
- Pasta de saida de execucao (`out/`).

**Passos (ordem de execucao)**
1. Adicionar `loguru` como dependencia de runtime.
2. Criar modulo dedicado de configuracao de logs (ex.: `src/cut_precision/logging_config.py`).
3. Configurar sink de console human-readable.
4. Configurar sink de arquivo rotativo detalhado (`run.log`).
5. Configurar sink estruturado JSON (`run.jsonl`) para ingestao.
6. Implementar `run_id` unico por execucao e `logger.bind(run_id=...)`.
7. Instrumentar inicio/fim de cada etapa: extract, register, calibration, distance, metrics, export.
8. Padronizar eventos com nome curto (`event`) e campos de contexto.
9. Garantir redacao de campos sensiveis e evitar logs com payload binario/imagem.

**Saidas**
- Logging centralizado e consistente.
- Logs por etapa com duracao e status.
- Trilha de auditoria por `run_id`.

**Criterio de pronto**
- Qualquer execucao produz `run.log` e `run.jsonl`.
- Falhas ficam rastreaveis por etapa e stacktrace.

**Checklist**
- [x] `loguru` adicionado ao projeto.
- [x] Modulo `logging_config` criado.
- [x] Sinks console, arquivo e JSON funcionando.
- [x] `run_id` presente em todos os eventos.
- [x] Etapas principais instrumentadas com inicio/fim/duracao.
- [x] Politica de redacao aplicada.

---

## Fase 4 - Refatoracao Arquitetural da Orquestracao
**Objetivo:** reduzir acoplamento no `cli.py` e separar responsabilidades.

**Entradas**
- `src/cut_precision/cli.py` atual.
- Contratos atuais de funcoes de dominio.

**Passos (ordem de execucao)**
1. Extrair parsing de argumentos para modulo proprio (ex.: `cli_args.py`).
2. Extrair orquestracao para `pipeline_service.py`.
3. Extrair construcao de relatorio para `report_builder.py`.
4. Transformar `tau_context` em dataclass tipada.
5. Manter `cli.py` apenas como camada de interface.
6. Garantir compatibilidade total de argumentos existentes.

**Saidas**
- `cli.py` menor e focado em interface.
- Camadas de aplicacao e dominio separadas.
- Melhor testabilidade por unidade.

**Criterio de pronto**
- Funcoes extraidas com testes passando.
- CLI permanece compativel com os comandos atuais.

**Checklist**
- [x] Parsing movido para modulo dedicado.
- [x] Fluxo de pipeline movido para service.
- [x] Builder de relatorio extraido.
- [x] `tau_context` tipado com dataclass.
- [x] Compatibilidade de CLI validada.

---

## Fase 5 - Validacao Forte de Configuracao
**Objetivo:** falhar cedo com mensagens claras para parametros invalidos.

**Entradas**
- `src/cut_precision/config.py`.
- `config/default.json`.

**Passos (ordem de execucao)**
1. Criar validadores por secao (`ExtractionConfig`, `RegistrationConfig`, etc.).
2. Validar ranges e coerencia (kernels impares, limites positivos, intervalos [0,1]).
3. Validar combinacoes invalidas de flags/valores.
4. Emitir erro de configuracao padronizado com campo, valor e motivo.
5. Cobrir casos invalidos com testes de unidade.

**Saidas**
- Configuracoes invalidas detectadas antes do processamento pesado.
- Mensagens de erro acionaveis.

**Criterio de pronto**
- Erros de config sao deterministicos e claros.
- Testes de validacao cobrindo cenarios principais.

**Checklist**
- [x] Validacoes por secao implementadas.
- [x] Ranges e coerencia revisados.
- [x] Erros padronizados de configuracao criados.
- [x] Testes de config invalida adicionados.

---

## Fase 6 - DRY da Calibracao de Tau
**Objetivo:** remover duplicacao entre `cli.py` e `tau_cli.py`.

**Entradas**
- Fluxos de calibracao em `cli.py` e `tau_cli.py`.
- Modulo `tau.py`.

**Passos (ordem de execucao)**
1. Criar `tau_service.py` para concentrar fluxo comum de calibracao.
2. Unificar defaults compartilhados (`tau_min`, `tau_max`, objective, policy).
3. Padronizar payload de retorno para ambos os comandos.
4. Ajustar CLIs para chamar apenas service.
5. Adicionar testes de regressao cruzada (mesmo input, mesmo output).

**Saidas**
- Uma unica implementacao para regra de calibracao.
- Menos risco de divergencia funcional entre CLIs.

**Criterio de pronto**
- Nao ha logica duplicada de calibracao nas duas CLIs.
- Resultados equivalentes validados por testes.

**Checklist**
- [x] `tau_service` criado.
- [x] Defaults unificados em constantes compartilhadas.
- [x] CLIs consumindo service central.
- [x] Testes de equivalencia adicionados.

---

## Fase 7 - Resiliencia, Tratamento de Erros e IO Seguro
**Objetivo:** eliminar falhas silenciosas e melhorar degradacao controlada.

**Entradas**
- Pontos com `except Exception`.
- Funcoes de escrita/leitura de artefatos.

**Passos (ordem de execucao)**
1. Trocar capturas genericas por excecoes especificas.
2. Logar contexto minimo obrigatorio em falhas (`run_id`, etapa, arquivo, erro).
3. Validar retorno de `cv2.imwrite` e falhar explicitamente se falso.
4. Revisar politicas de fallback para manter comportamento previsivel.
5. Adicionar testes para caminhos de erro e fallback.

**Saidas**
- Menos erro silencioso.
- Diagnostico de falha mais rapido.

**Criterio de pronto**
- Nao ha `except Exception` sem justificativa + log.
- Falhas de IO sao detectadas e reportadas corretamente.

**Checklist**
- [x] `except Exception` revisados e reduzidos.
- [x] Erros com contexto estruturado implementados.
- [x] Escrita de artefatos validada.
- [x] Testes de caminhos de falha criados.

---

## Fase 8 - Testes, Qualidade e Gate de Entrega
**Objetivo:** fechar o ciclo com cobertura adequada e criterio objetivo de release.

**Entradas**
- Codigo refatorado das fases anteriores.
- Suite de testes atual.

**Passos (ordem de execucao)**
1. Expandir testes para modulos pouco cobertos (`calibration`, `io_utils`, `report`, `visualize`).
2. Cobrir cenarios de falha de config, IO e calibracao.
3. Definir meta de cobertura (ex.: >= 85% em modulos core).
4. Integrar checks automatizados na CI: testes, CVE, estilo e tipagem.
5. Publicar checklist de release com artefatos obrigatorios.

**Saidas**
- Gate de qualidade automatizado.
- Menor risco de regressao em producao.

**Criterio de pronto**
- Todos os checks obrigatorios passam na CI.
- Cobertura minima atingida nos modulos centrais.

**Checklist**
- [x] Testes adicionais implementados.
- [x] Meta de cobertura atingida.
- [x] Gates de CI configurados e verdes.
- [x] Checklist de release documentado.

---

## Plano de Logs com Loguru

## Objetivo do logging
- Rastrear cada execucao ponta a ponta.
- Facilitar debug de falhas intermitentes.
- Gerar trilha auditavel para analise de qualidade.

## Estrutura padrao de evento
- `timestamp`: data/hora UTC.
- `level`: DEBUG/INFO/WARNING/ERROR/CRITICAL.
- `run_id`: identificador unico da execucao.
- `event`: nome curto do evento (`extract.start`, `register.done`, etc.).
- `stage`: etapa funcional (`extract`, `register`, `metrics`, `export`).
- `status`: `ok`, `warning`, `failed`.
- `duration_ms`: duracao da etapa quando aplicavel.
- `details`: campos adicionais (metodo, thresholds, metricas resumidas).

## Niveis de Log e Quando Usar
- `DEBUG`: detalhes tecnicos de desenvolvimento e investigacao.
- `DEBUG`: usar para parametros internos, contagens intermediarias, valores de tuning e selecao de candidatos.
- `INFO`: marcos esperados da execucao.
- `INFO`: usar para inicio/fim de pipeline, inicio/fim de etapa, paths de artefatos, resumo de metricas finais.
- `WARNING`: degradacao recuperavel sem abortar pipeline.
- `WARNING`: usar para fallback acionado, validacao KDTree com mismatch, calibracao mm ausente.
- `ERROR`: falha de etapa que compromete resultado da execucao atual.
- `ERROR`: usar para extracao sem contorno, falha de escrita de artefato, erro de leitura de input obrigatorio.
- `CRITICAL`: falha nao recuperavel que exige interrupcao imediata.
- `CRITICAL`: usar para corrupcao de config essencial, inconsistencia estrutural de dados ou impossibilidade de continuar com seguranca.

## Sinks recomendados
- `Console`: nivel minimo `INFO` em execucao normal e `DEBUG` quando `--debug` estiver ativo.
- `Arquivo texto rotativo (run.log)`: nivel minimo `DEBUG`, com rotacao por tamanho (ex.: 10 MB) e retencao (ex.: 14 dias).
- `Arquivo estruturado (run.jsonl)`: `serialize=True` para consumo por scripts/dashboards, nivel minimo `INFO`.

## Eventos obrigatorios por etapa
- `pipeline.start` e `pipeline.end`.
- `extract.ideal.start` e `extract.ideal.end`.
- `extract.real.start` e `extract.real.end`.
- `register.candidate` para cada metodo testado.
- `register.selected`.
- `calibration.start` e `calibration.end`.
- `distance.compute.start` e `distance.compute.end`.
- `metrics.compute`.
- `artifact.write` para cada arquivo.
- `pipeline.error` com stacktrace em falhas.

## Politicas de seguranca de log
- Nunca registrar conteudo bruto de imagem.
- Nunca registrar secrets/tokens/cookies (se existirem no futuro).
- Registrar paths absolutos apenas quando necessario para suporte.
- Reduzir volume de logs em lote para evitar overhead.

## Exemplo de configuracao inicial (referencia)
```python
from pathlib import Path
import sys
from loguru import logger

def setup_logging(out_dir: Path, run_id: str, debug: bool = False):
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if debug else "INFO")
    logger.add(out_dir / "run.log", level="DEBUG", rotation="10 MB", retention="14 days")
    logger.add(out_dir / "run.jsonl", level="INFO", serialize=True, rotation="10 MB", retention="14 days")
    return logger.bind(run_id=run_id)
```

---

## Plano de Entrega por Incremento
- Incremento A: Fases 1, 2 e 3 (seguranca + observabilidade).
- Incremento B: Fases 4, 5 e 6 (arquitetura + configuracao + DRY).
- Incremento C: Fases 7 e 8 (resiliencia + testes + gate final).

## Definicao de Conclusao do Projeto
- Todas as fases marcadas como concluidas.
- CI verde com gates de seguranca e qualidade.
- Execucao do pipeline com logs estruturados e rastreaveis.
- Documentacao atualizada para onboarding e operacao.
- Checklist transversal de DRY e nomenclatura aprovado em 100% das fases.
