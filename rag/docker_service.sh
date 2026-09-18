#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo " Creating Docker Volumes (if not exist)   "
echo "=========================================="
docker volume create es_data
docker volume create pgvector_data
docker volume create ollama

echo "=========================================="
echo " 1. Launching Elasticsearch               "
echo "=========================================="
docker run -d \
  --name elasticsearch \
  --restart always \
  -p 9200:9200 \
  -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms2g -Xmx2g" \
  -v es_data:/usr/share/elasticsearch/data \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.0

echo "=========================================="
echo " 2. Launching Harness Postgres (pgvector) "
echo "=========================================="
docker run -d \
  --name harness-postgres \
  --restart always \
  -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=agents \
  -v pgvector_data:/var/lib/postgresql/data \
  pgvector/pgvector:pg16

echo "=========================================="
echo " 3. Launching vLLM Reranker               "
echo "=========================================="
docker run -d \
  --gpus all \
  --name vllm-reranker \
  --ipc=host \
  -p 8000:8000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:latest \
  BAAI/bge-reranker-v2-m3 \
  --runner pooling \
  --host 0.0.0.0 \
  --port 8000

echo "=========================================="
echo " 4. Launching Ollama                      "
echo "=========================================="
docker run -d \
  --gpus all \
  --name ollama \
  --restart always \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama

echo "=========================================="
echo " 5. Pulling Ollama Models                 "
echo "=========================================="
echo "Waiting for Ollama service to start..."
sleep 3
docker exec ollama ollama pull qwen3.8:27b
docker exec ollama ollama pull bge-m3:latest

echo "=========================================="
echo " All containers launched successfully!    "
echo "=========================================="

