## [2026-09-18 08:45] | Task: Add Ollama models pull step to rag/docker_service.sh

### User Query
> Add Ollama models (qwen3.8:27b and bge-m3:latest) into docker_service.sh

### Changes Overview
- Updated [`rag/docker_service.sh`](file:///Users/frank/harness_template/rag/docker_service.sh) to include a model pull step (`docker exec ollama ollama pull qwen3.8:27b` and `docker exec ollama ollama pull bge-m3:latest`) following the container startup.

### Design Intent
Ensure that after the Ollama Docker container is created and started, the required models (`qwen3.8:27b` and `bge-m3:latest`) are automatically pulled into the container volume so they are ready for inference and embedding tasks.

### Files Modified
- `rag/docker_service.sh`
