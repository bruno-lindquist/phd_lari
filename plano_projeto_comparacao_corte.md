# Plano de Projeto: Comparacao de Contorno Ideal vs Recorte Real

## 1) Resumo executivo do plano

- Construir um pipeline deterministico em Python 3.11+ com etapas separadas: extracao (ideal e real), registro, calibracao, metricas e visualizacao.
- Extrair contorno ideal (linha pontilhada) com limiarizacao + morfologia para conectar pontos + filtros geometricos para remover regua/eixos/textos.
- Extrair contorno real (silhueta escura) por segmentacao de regioes escuras + limpeza morfologica conservadora para preservar pontas finas.
- Alinhamento padrao com ORB + Homography (RANSAC), com fallbacks por eixos/regua e por template matching + ECC.
- Medir distancias ponto-curva com amostragem uniforme por comprimento de arco para evitar vies de densidade de pontos.
- Calcular MAD, STD e IPN em mm quando houver calibracao da regua de 12 cm; se nao houver, retornar em px com flag explicita.
- Definir IPN com tolerancia normalizada pelo tamanho da estrela (diagonal da bounding box do contorno ideal), com clamp para manter score entre 0 e 100.
- Gerar artefatos de diagnostico (overlay, mapa de erro, histograma) e out/report.json com parametros, qualidade do registro e versao.
- Entregar testes minimos em pytest para MAD/STD/IPN com contornos sinteticos.

## 2) Decisoes de design (com pros e contras)

### Extracao do contorno ideal (linha pontilhada)
- **Escolha default:** threshold adaptativo + closing/dilation + selecao por componente.
- **Pros:** robusto a ruido e compressao; conecta gaps do pontilhado.
- **Contras:** sensivel a kernel mal configurado.
- **Fallback:** skeletonize opcional + ajuste automatico de kernel por escala.

### Remocao de regua/eixos/textos
- **Escolha default:** Hough Lines para linhas longas + filtro por componentes (aspect ratio/area/posicao).
- **Pros:** remove interferentes estruturais comuns.
- **Contras:** pode remover parte do contorno se houver sobreposicao forte.
- **Fallback:** mascara de ROI da estrela apos registro aproximado.

### Extracao do contorno real
- **Escolha default:** segmentacao de baixo brilho (LAB/HSV) + closing + maior componente externo.
- **Pros:** simples e robusto para silhueta escura.
- **Contras:** pode incluir sombras/artefatos.
- **Fallback:** pos-filtro por convexidade/area/perimetro.

### Registro
- **Escolha default:** ORB + Homography + RANSAC.
- **Pros:** lida com rotacao, escala e perspectiva.
- **Contras:** falha com pouca textura.
- **Fallbacks:**
  1. Deteccao de eixos/regua para inferir transformacao.
  2. Template matching para aproximacao + ECC para refinamento.

### Distancia ponto-curva
- **Escolha default:** KDTree no contorno ideal reamostrado.
- **Pros:** distancia euclidiana precisa em coordenadas float.
- **Contras:** custo de construcao da arvore.
- **Fallback/apoio:** Distance Transform para mapa de erro e validacao cruzada.

### Amostragem de pontos
- **Escolha default:** reamostragem uniforme por comprimento de arco.
- **Pros:** evita vies por densidade irregular.
- **Contras:** exige implementacao adicional.

### Normalizacao do IPN
- **Escolha default:** escala pela diagonal da bounding box ideal em mm + fator de tolerancia tau.
- **Pros:** robusto ao tamanho do objeto.
- **Contras:** exige calibracao de tau.

## Definicao recomendada das metricas

Dados:
- `C_ideal`: conjunto de pontos do contorno ideal.
- `C_real`: conjunto de pontos do contorno real.
- `d(p, C_ideal) = min_q ||p - q||2`.

Metricas:
- `MAD = mean(d_i)` para `p_i` em amostras uniformes de `C_real`.
- `STD = std(d_i)`.

Normalizacao proposta:
- `S_mm = diagonal_bbox(C_ideal) * mm_per_px`
- `T_mm = tau * S_mm`, com `tau = 0.02` (configuravel)
- `IPN = clamp(0, 100 * (1 - MAD_mm / T_mm), 100)`

Justificativa:
- Normaliza por tamanho da estrela e tolerancia relativa, evitando comparacao injusta entre tamanhos.
- `clamp` evita score negativo.
- Se nao houver calibracao: calcular em px e marcar `calibration_status = "missing"`.

## 3) Pipeline passo a passo detalhado

1. **Entrada e configuracao**
- Inputs: `original.jpeg` (template) e `teste_1.jpg` (teste).
- Carregar config (YAML/JSON) com thresholds, kernels, tau e criterios de QA.
- Fixar seed e salvar config efetiva no relatorio.

2. **Pre-processamento**
- Conversao para grayscale e LAB.
- Reducao de ruido (gaussiano/bilateral leve).
- CLAHE opcional para compensar iluminacao desigual.

3. **Extracao do contorno ideal no template**
- Limiarizacao para destacar traco escuro pontilhado.
- Closing + dilatacao leve para unir pontos.
- Remocao de linhas longas (regua/eixos) com Hough.
- Remocao de texto/artefatos por area/aspect ratio.
- Selecao do componente da estrela por score geometrico.
- Skeletonize opcional para linha de 1 pixel.
- Vetorizacao do contorno fechado com `cv2.findContours`.

4. **Extracao do contorno real na imagem de teste**
- Segmentacao de silhueta escura por brilho baixo (LAB L/HSV V).
- Closing para fechar falhas e preenchimento de buracos.
- Selecionar maior componente externo (ou melhor score).
- Suavizacao leve sem perder pontas finas.

5. **Registro/alinhamento**
- Default: ORB + matching KNN + ratio test + homografia RANSAC.
- Transformar `C_real` para o espaco de `C_ideal`.
- Validar: inliers, erro de reprojecao e plausibilidade da matriz.
- Fallback 1: eixos/regua para inferir transformacao.
- Fallback 2: template matching + ECC.

6. **Calibracao px->mm (regua 12 cm)**
- Detectar segmentos horizontais/verticais da regua.
- Medir `px_120` correspondente a 120 mm.
- `mm_per_px = 120 / px_120`.
- Se houver eixo horizontal e vertical, usar estimativa robusta (mediana).
- Se nao detectavel, permitir parametro manual `mm_per_px`.

7. **Reamostragem uniforme de contornos**
- Reamostrar por comprimento de arco com passo fixo (px ou mm).
- Garantir contorno fechado e ordenacao consistente.

8. **Calculo de metricas**
- Construir KDTree com pontos de `C_ideal`.
- Para cada ponto reamostrado de `C_real`, calcular menor distancia.
- Calcular `MAD`, `STD`, conversao para mm e `IPN`.
- Complementares sugeridas: Hausdorff, P95 e bidirecional (`real->ideal` e `ideal->real`).

9. **Visualizacoes e relatorio**
- `overlay` dos contornos alinhados.
- `error_map` colorido por magnitude de erro.
- Histograma de distancias.
- Exportar `out/report.json` com metricas, status e parametros.

10. **CLI e reprodutibilidade**
- Exemplo: `python -m cut_precision.cli --template original.jpeg --test teste_1.jpg --out out`.
- Incluir versao de libs, hash de commit e configuracao no JSON.

## Estrutura sugerida de pastas/modulos

- `src/cut_precision/cli.py`
- `src/cut_precision/config.py`
- `src/cut_precision/io_utils.py`
- `src/cut_precision/preprocess.py`
- `src/cut_precision/extract.py`
- `src/cut_precision/register.py`
- `src/cut_precision/calibration.py`
- `src/cut_precision/resample.py`
- `src/cut_precision/metrics.py`
- `src/cut_precision/visualize.py`
- `src/cut_precision/report.py`
- `tests/test_metrics.py`
- `tests/test_resample.py`
- `tests/test_ipn.py`
- `out/report.json`

## Saidas esperadas

- `out/report.json` contendo:
  - `inputs`
  - `calibration` (`mm_per_px`, status, metodo)
  - `registration` (inlier_ratio, reprojection_error_px, status)
  - `metrics` (`mad_px`, `mad_mm`, `std_px`, `std_mm`, `ipn`, `scale_mm`, `tau`)
  - `diagnostics` (`hausdorff_mm`, `p95_mm`, `bidirectional_mad_mm`)
  - `params`, `version`, `timestamp`

- Visualizacoes:
  - `out/ideal_mask.png`
  - `out/real_mask.png`
  - `out/overlay.png`
  - `out/error_map.png`
  - `out/error_hist.png`

## 4) Plano de validacao

- Validar extracao do ideal com `ideal_mask` e overlay do contorno.
- Validar extracao do real com `real_mask` e overlay.
- Validar registro com `inlier_ratio` e `reprojection_error_px`.
- Criterios minimos sugeridos:
  - `inlier_ratio >= 0.25`
  - `reprojection_error_px <= 3.0`
- Validar calibracao pela consistencia entre regua horizontal e vertical.
- Validar metricas em casos sinteticos controlados:
  - Erro zero (contornos identicos).
  - Translacao conhecida.
  - Ruido conhecido.
- Se uma etapa falhar, registrar motivo e executar fallback automatico.

## 5) Checklist final de implementacao

1. Criar estrutura do projeto e `pyproject.toml` com dependencias.
2. Implementar dataclasses/resultados e loader de configuracao.
3. Implementar extracao do contorno ideal (incluindo filtros para regua/eixos/textos).
4. Implementar extracao do contorno real com limpeza conservadora.
5. Implementar registro ORB + Homography + validacao de qualidade.
6. Implementar fallbacks de registro (eixos/regua e template+ECC).
7. Implementar calibracao por regua de 12 cm + fallback manual.
8. Implementar reamostragem por comprimento de arco.
9. Implementar metricas MAD/STD/IPN com KDTree.
10. Implementar metricas complementares (Hausdorff, P95, bidirecional).
11. Implementar visualizacoes (overlay, error map, histograma).
12. Implementar geracao de `out/report.json`.
13. Implementar CLI end-to-end.
14. Criar testes `pytest` minimos para MAD/STD/IPN com contornos sinteticos.
15. Rodar testes e validar em `original.jpeg` vs `teste_1.jpg`.

