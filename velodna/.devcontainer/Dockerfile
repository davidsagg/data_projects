# .devcontainer/Dockerfile
FROM python:3.11-slim
 
RUN apt-get update && apt-get install -y \
    git curl build-essential libssl-dev \
    && rm -rf /var/lib/apt/lists/*
 
RUN pip install uv
 
WORKDIR /workspace

