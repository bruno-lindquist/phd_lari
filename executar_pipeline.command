#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CLI_BIN="$VENV_DIR/bin/cut-precision"

TEST_IMAGE="$PROJECT_DIR/teste_1.jpg"
OUT_ROOT="$PROJECT_DIR/out"
TIMESTAMP="$("$PYTHON_BIN" - <<'PY'
from datetime import datetime
print(datetime.now().strftime("%Y_%m_%d__%H_%M_%S_%f")[:-3])
PY
)"
OUT_DIR="$OUT_ROOT/$TIMESTAMP"

TEMPLATE_CANDIDATES=(
  "$PROJECT_DIR/original.jpeg"
  "$PROJECT_DIR/original-.jpeg"
  "$PROJECT_DIR/original.jpg"
)
TEMPLATE=""
for candidate in "${TEMPLATE_CANDIDATES[@]}"; do
  if [ -f "$candidate" ]; then
    TEMPLATE="$candidate"
    break
  fi
done

echo "Projeto: $PROJECT_DIR"
echo "Template:$TEMPLATE"
echo "Teste:   $TEST_IMAGE"
echo "Saida:   $OUT_DIR"
echo

if [ -z "$TEMPLATE" ]; then
  echo "Erro: nenhum template encontrado."
  echo "Esperado um destes arquivos:"
  for candidate in "${TEMPLATE_CANDIDATES[@]}"; do
    echo "  - $candidate"
  done
  read -r -p "Pressione Enter para fechar..." _
  exit 1
fi

if [ ! -f "$TEST_IMAGE" ]; then
  echo "Erro: arquivo nao encontrado: $TEST_IMAGE"
  read -r -p "Pressione Enter para fechar..." _
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Criando ambiente virtual em $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

mkdir -p "$OUT_ROOT"

NEEDS_SETUP=0
if ! "$VENV_DIR/bin/python" -c "import cut_precision" >/dev/null 2>&1; then
  NEEDS_SETUP=1
fi
if [ ! -x "$CLI_BIN" ]; then
  NEEDS_SETUP=1
fi

if [ "$NEEDS_SETUP" -eq 1 ]; then
  echo "Instalando dependencias..."
  "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
  if [ -f "$PROJECT_DIR/requirements-dev.lock" ]; then
    "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements-dev.lock"
    "$VENV_DIR/bin/pip" install -e "$PROJECT_DIR" --no-deps
  else
    "$VENV_DIR/bin/pip" install -e "${PROJECT_DIR}[dev]"
  fi
fi

if [ ! -x "$CLI_BIN" ]; then
  echo "Erro: entrypoint nao encontrado apos instalacao: $CLI_BIN"
  read -r -p "Pressione Enter para fechar..." _
  exit 1
fi

echo
echo "Executando pipeline..."
"$CLI_BIN" \
  --template "$TEMPLATE" \
  --test "$TEST_IMAGE" \
  --out "$OUT_DIR"

echo
echo "Concluido."
echo "Relatorio: $OUT_DIR/report.json"
read -r -p "Pressione Enter para fechar..." _
