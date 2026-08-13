#!/bin/bash
set -e

source .env

echo "Pulling ${LLM_MODEL}..."
docker compose exec ollama ollama pull "${LLM_MODEL}"

echo "Pulling ${EMBEDDING_MODEL}..."
docker compose exec ollama ollama pull "${EMBEDDING_MODEL}"

echo "Done. Installed models:"
docker compose exec ollama ollama list