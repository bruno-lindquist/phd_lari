#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
FULL_CLEAN=0

if [ "${1:-}" = "--full" ]; then
  FULL_CLEAN=1
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo "Uso: $(basename "$0") [--full]"
  echo
  echo "Limpeza padrao:"
  echo "  - out/"
  echo "  - .pytest_cache/"
  echo "  - .mypy_cache/"
  echo "  - .ruff_cache/"
  echo "  - __pycache__/ e *.pyc (fora de .venv)"
  echo "  - .coverage"
  echo
  echo "Opcional:"
  echo "  --full  tambem remove .venv/"
  exit 0
fi

echo "Projeto: $PROJECT_DIR"
echo "Modo: $( [ "$FULL_CLEAN" -eq 1 ] && echo 'full' || echo 'padrao' )"
echo

clean_dir_contents() {
  local dir_path="$1"
  if [ -d "$dir_path" ]; then
    find "$dir_path" -mindepth 1 -delete
    rmdir "$dir_path" 2>/dev/null || true
    echo "[ok] removido: ${dir_path#$PROJECT_DIR/}"
  fi
}

# Limpeza de artefatos/caches de execucao.
clean_dir_contents "$PROJECT_DIR/out"
clean_dir_contents "$PROJECT_DIR/.pytest_cache"
clean_dir_contents "$PROJECT_DIR/.mypy_cache"
clean_dir_contents "$PROJECT_DIR/.ruff_cache"

# Remove pycache e pyc fora do ambiente virtual.
find "$PROJECT_DIR" -path "$PROJECT_DIR/.venv" -prune -o -type d -name "__pycache__" -print0 |
while IFS= read -r -d '' cache_dir; do
  find "$cache_dir" -mindepth 1 -delete
  rmdir "$cache_dir" 2>/dev/null || true
  echo "[ok] removido: ${cache_dir#$PROJECT_DIR/}"
done

find "$PROJECT_DIR" -path "$PROJECT_DIR/.venv" -prune -o -type f -name "*.pyc" -delete

if [ -f "$PROJECT_DIR/.coverage" ]; then
  unlink "$PROJECT_DIR/.coverage"
  echo "[ok] removido: .coverage"
fi

if [ "$FULL_CLEAN" -eq 1 ]; then
  clean_dir_contents "$PROJECT_DIR/.venv"
fi

echo
echo "Limpeza concluida."
