# Deployment & Operations Guide

## Deployment Modes

### 1. Local Development Mode
Run services locally with fallback storage:
```bash
cp .env.example .env
make setup
make seed
make demo
make test
```

### 2. Containerized Production / Demo Mode
Launch full container stack via Docker Compose:
```bash
make start
```

Access services:
- **FeatureHub API**: `http://localhost:8000/docs`
- **DataGuard API**: `http://localhost:8001/docs`
- **FeatureHub Dashboard**: `http://localhost:8501`
- **DataGuard Dashboard**: `http://localhost:8502`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`
