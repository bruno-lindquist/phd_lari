# Plano de Projeto: Comparação de Contorno Ideal vs Recorte Real

## 1) Resumo executivo do plano

- Construir um pipeline determinístico em Python 3.11+ com etapas separadas: extração (ideal e real), registro, calibração, métricas e visualização.
- Extrair contorno ideal (linha pontilhada) com limiarização + morfologia para conectar pontos + filtros geométricos para remover régua/eixos/textos.
- Extrair contorno real (silhueta escura) por segmentação de regiões escuras + limpeza morfológica conservadora para preservar pontas finas.
- Alinhamento padrão com ORB + Homography (RANSAC), com fallbacks por eixos/régua e por template matching + ECC.
- Medir distâncias ponto-curva com amostragem uniforme por comprimento de arco para evitar viés de densidade de pontos.
- **Cálculo de distâncias (padrão): Distance Transform** gerado a partir do contorno ideal, lendo a distância no mapa para cada ponto do contorno real.
- **Validação cruzada (opcional): KDTree** no contorno ideal reamostrado para “double-check” e detecção de falhas de extração/registro.
- Calcular MAD, STD e IPN em mm quando houver calibração pela régua de 12 cm; se não houver, retornar em px com flag explícita.
- Definir IPN com tolerância normalizada pelo tamanho da estrela (diagonal da bounding box do contorno ideal), com clamp para manter score entre 0 e 100.
- Gerar artefatos de diagnóstico (overlay, mapa de erro, histograma) e `out/report.json` com parâmetros, qualidade do registro e versão.
- Entregar testes mínimos em pytest para MAD/STD/IPN com contornos sintéticos.

---

## 2) Decisões de design (com prós e contras)

### Extração do contorno ideal (linha pontilhada)
- **Escolha default:** threshold adaptativo + closing/dilation + seleção por componente.
- **Prós:** robusto a ruído e compressão; conecta gaps do pontilhado.
- **Contras:** sensível a kernel mal configurado.
- **Fallback:** skeletonize opcional + ajuste automático de kernel por escala.

### Remoção de régua/eixos/textos
- **Escolha default:** Hough Lines para linhas longas + filtro por componentes (aspect ratio/área/posição).
- **Prós:** remove interferentes estruturais comuns.
- **Contras:** pode remover parte do contorno se houver sobreposição forte.
- **Fallback:** máscara de ROI da estrela após registro aproximado.

### Extração do contorno real
- **Escolha default:** segmentação de baixo brilho (LAB/HSV) + closing + maior componente externo.
- **Prós:** simples e robusto para silhueta escura.
- **Contras:** pode incluir sombras/artefatos.
- **Fallback:** pós-filtro por convexidade/área/perímetro.

### Registro
- **Escolha default:** ORB + Homography + RANSAC.
- **Prós:** lida com rotação, escala e perspectiva.
- **Contras:** falha com pouca textura.
- **Fallbacks:**
  1. Detecção de eixos/régua para inferir transformação.
  2. Template matching para aproximação + ECC para refinamento.

### Distância ponto-curva (métrica principal)
- **Escolha default:** **Distance Transform** a partir do contorno ideal.
- **Prós:** extremamente rápido; gera mapa de erro; simples de aplicar após alinhamento; permite ler distâncias diretamente em pixels.
- **Contras:** discretização em grade de pixels (mitigável com interpolação bilinear).
- **Validação/backup:** **KDTree** no contorno ideal reamostrado.
- **Uso recomendado do KDTree:** detectar inconsistências (ex.: DT vs KDTree divergem muito) e depurar falhas de extração/registro.

### Amostragem de pontos
- **Escolha default:** reamostragem uniforme por comprimento de arco.
- **Prós:** evita viés por densidade irregular.
- **Contras:** exige implementação adicional.

### Normalização do IPN
- **Escolha default:** escala pela diagonal da bounding box ideal (em px ou mm) + fator de tolerância `tau`.
- **Prós:** robusto ao tamanho do objeto; comparável entre amostras com escalas diferentes.
- **Contras:** exige calibrar `tau` (tolerância relativa).

---

## 3) Definição recomendada das métricas

### Notação
- `C_ideal`: contorno ideal (ordenado, fechado, no espaço do template).
- `C_real`: contorno real (ordenado, fechado, já alinhado para o espaço do template).
- `p_i`: i-ésimo ponto amostrado uniformemente em `C_real`.

### Distância ponto-a-contorno (duas formas)
1) **Distance Transform (padrão)**
- Crie um mapa `D(x,y)` que retorna a distância Euclidiana (L2) do pixel (x,y) ao contorno ideal.
- Para cada ponto `p_i = (x_i, y_i)` (geralmente float após homografia), compute `d_i = bilinear_sample(D, x_i, y_i)`.

2) **KDTree (validação/backup)**
- `d_i = min_{q em C_ideal} ||p_i - q||_2`

### MAD (Mean Absolute Distance)
- `MAD = mean(d_i)` para `p_i` em amostras uniformes de `C_real`.
- Unidade: px (ou mm se calibrado).

### STD (Variabilidade do corte)
- `STD = std(d_i)`
- Interpretação: STD baixo = corte uniforme; STD alto = irregularidade (mesmo se MAD for baixo).

### Normalização proposta (IPN)
- `S = diagonal_bbox(C_ideal)` (em px)  
- Se houver calibração: `S_mm = S_px * mm_per_px`
- `T = tau * S` (tolerância absoluta, em px ou mm)
- Fórmula:
  - `IPN = clamp(0, 100 * (1 - MAD / T), 100)`
- Default sugerido: `tau = 0.02` (configurável)
  - Ex.: tolerância de 2% do “tamanho” da estrela (pela diagonal da bounding box).

### Regras de robustez
- Se `T` for muito pequeno (ex.: contorno inválido), marcar `metrics_status="invalid_scale"`.
- Se não houver calibração, calcular tudo em px e marcar `calibration_status="missing"`.

### Complementares recomendadas (diagnóstico)
- `P95 = percentile(d_i, 95)` (sensível a “pontos ruins” sem ser tão extremo quanto Hausdorff)
- Hausdorff (opcional): pior caso (sensível a outliers)
- Bidirecional (opcional): calcular também ideal→real para capturar “subcorte” vs “sobrecorte”.

---

## 4) Pipeline passo a passo detalhado

### 1. Entrada e configuração
- Inputs: `original.jpeg` (template) e `teste_1.jpg` (teste).
- Carregar config (YAML/JSON) com thresholds, kernels, `tau` e critérios de QA.
- Fixar seed e salvar config efetiva no relatório.

### 2. Pré-processamento
- Conversão para grayscale e LAB.
- Redução de ruído (gaussiano/bilateral leve).
- CLAHE opcional para compensar iluminação desigual.

### 3. Extração do contorno ideal no template (linha pontilhada)
- Limiarização para destacar traço pontilhado.
- Closing + dilatação leve para unir pontos.
- Remoção de linhas longas (régua/eixos) com Hough.
- Remoção de texto/artefatos por área/aspect ratio.
- Seleção do componente da estrela por score geométrico (área, circularidade/elongação, centralidade).
- Skeletonize opcional para reduzir a espessura a 1px.
- Vetorização do contorno fechado com `cv2.findContours`.

### 4. Extração do contorno real na imagem de teste (silhueta)
- Segmentação de silhueta escura por brilho baixo (LAB L / HSV V).
- Closing para fechar falhas e preenchimento de buracos.
- Selecionar maior componente externo (ou melhor score geométrico).
- Suavização leve sem perder pontas finas (evitar “alisar demais”).

### 5. Registro/alinhamento
- Default: ORB + matching KNN + ratio test + homografia RANSAC.
- Transformar `C_real` para o espaço de `C_ideal`.
- Validar: `inlier_ratio`, erro de reprojeção e plausibilidade da matriz.
- Fallback 1: eixos/régua para inferir transformação.
- Fallback 2: template matching + ECC.

### 6. Calibração px->mm (régua 12 cm)
- Detectar segmentos horizontais/verticais da régua.
- Medir `px_120` correspondente a 120 mm.
- `mm_per_px = 120 / px_120`.
- Se houver eixo horizontal e vertical, usar estimativa robusta (mediana).
- Se não detectável, permitir parâmetro manual `mm_per_px`.

### 7. Reamostragem uniforme de contornos
- Reamostrar por comprimento de arco com passo fixo (px ou mm):
  - `step_px` default: 1.0–2.0 px (configurável)
  - ou `n_points` default: 800–1500 (configurável)
- Garantir contorno fechado e ordenação consistente.

### 8. Cálculo de métricas (padrão: Distance Transform)
**8.1 Construção do mapa de distância (a partir do ideal)**
- Criar uma imagem `mask` do tamanho do template (1 canal, uint8).
- Preencher com 255 (não-zero) e desenhar o contorno ideal em 0 (zero) com espessura 1–2 px.
- Calcular:
  - `D = cv2.distanceTransform(mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)`
- Interpretação: `D[y, x]` = distância (px) do ponto (x,y) até o contorno ideal.

**8.2 Distâncias no contorno real**
- Para cada ponto `p_i` do contorno real (float após homografia), obter `d_i`:
  - `d_i = bilinear_sample(D, x_i, y_i)` (recomendado)
  - fallback simples: arredondar e ler `D[round(y_i), round(x_i)]`

**8.3 Agregação**
- Calcular `MAD`, `STD`, `P95`, etc.
- Converter para mm se `mm_per_px` disponível.
- Calcular `IPN` com `tau`.

**8.4 Validação cruzada (opcional): KDTree**
- Reamostrar `C_ideal` e construir KDTree.
- Calcular `MAD_kd` e comparar:
  - Se `abs(MAD_dt - MAD_kd) > eps` (ex.: > 1–2 px), marcar `distance_validation="mismatch"` e salvar debug.

### 9. Visualizações e relatório
- `overlay`: contornos alinhados (ideal vs real).
- `error_map`: pontos do contorno real coloridos por magnitude do erro (`d_i`).
- `error_hist`: histograma de `d_i`.
- (Opcional) salvar `dist_map.png` (visualização do `D`).
- Exportar:
  - `out/report.json` com métricas, status, parâmetros e QA.
  - `out/distances.csv` com `{idx, x, y, d_px, d_mm?}` para auditoria.

### 10. CLI e reprodutibilidade
- Exemplo:
  - `python -m cut_precision.cli --template original.jpeg --test teste_1.jpg --out out --config config.yaml --debug`
- Incluir versão de libs, hash de commit e configuração no JSON.

---

## 5) Estrutura sugerida de pastas/módulos

- `src/cut_precision/cli.py`
- `src/cut_precision/config.py`
- `src/cut_precision/io_utils.py`
- `src/cut_precision/preprocess.py`
- `src/cut_precision/extract.py`
- `src/cut_precision/register.py`
- `src/cut_precision/calibration.py`
- `src/cut_precision/resample.py`
- `src/cut_precision/distance.py`  ← (novo) DT + bilinear sampling + validação KDTree
- `src/cut_precision/metrics.py`
- `src/cut_precision/visualize.py`
- `src/cut_precision/report.py`
- `tests/test_metrics.py`
- `tests/test_resample.py`
- `tests/test_ipn.py`
- `tests/test_distance_transform.py` (opcional, mas recomendado)
- `out/report.json`

---

## 6) Saídas esperadas

- `out/report.json` contendo:
  - `inputs`
  - `calibration` (`mm_per_px`, `status`, `method`)
  - `registration` (`inlier_ratio`, `reprojection_error_px`, `status`)
  - `metrics` (`mad_px`, `mad_mm?`, `std_px`, `std_mm?`, `p95_px`, `p95_mm?`, `ipn`, `scale_px`, `scale_mm?`, `tau`)
  - `distance_method` (`primary="distance_transform"`, `validation="kdtree"`, `validation_status`)
  - `params`, `version`, `timestamp`

- Visualizações:
  - `out/ideal_mask.png`
  - `out/real_mask.png`
  - `out/overlay.png`
  - `out/error_map.png`
  - `out/error_hist.png`
  - `out/dist_map.png` (opcional)
  - `out/distances.csv`

---

## 7) Plano de validação

- Validar extração do ideal com `ideal_mask` e overlay do contorno.
- Validar extração do real com `real_mask` e overlay.
- Validar registro com `inlier_ratio` e `reprojection_error_px`.
- Critérios mínimos sugeridos:
  - `inlier_ratio >= 0.25`
  - `reprojection_error_px <= 3.0`
- Validar calibração pela consistência entre régua horizontal e vertical (se ambas detectadas).
- Validar métricas em casos sintéticos controlados:
  - Erro zero (contornos idênticos).
  - Translação conhecida.
  - Ruído conhecido.
- Validar DT vs KDTree:
  - Diferença pequena esperada; divergência grande sugere extração/registro incorretos.
- Se uma etapa falhar, registrar motivo e executar fallback automático, sempre refletindo no `report.json`.

---

## 8) Checklist final de implementação

1. Criar estrutura do projeto e `pyproject.toml` com dependências.
2. Implementar dataclasses/resultados e loader de configuração.
3. Implementar extração do contorno ideal (incluindo filtros para régua/eixos/textos).
4. Implementar extração do contorno real com limpeza conservadora.
5. Implementar registro ORB + Homography + validação de qualidade.
6. Implementar fallbacks de registro (eixos/régua e template+ECC).
7. Implementar calibração por régua de 12 cm + fallback manual.
8. Implementar reamostragem por comprimento de arco.
9. Implementar **Distance Transform** como método padrão de distância + bilinear sampling.
10. Implementar **KDTree** como validação/backup (e log de divergência DT vs KD).
11. Implementar métricas MAD/STD/IPN + P95 (recomendado) e opcionais (Hausdorff, bidirecional).
12. Implementar visualizações (overlay, error map, histograma) e `distances.csv`.
13. Implementar geração de `out/report.json` (com QA e status de cada etapa).
14. Implementar CLI end-to-end.
15. Criar testes `pytest` mínimos para MAD/STD/IPN com contornos sintéticos.
16. Rodar testes e validar em `original.jpeg` vs `teste_1.jpg`.

