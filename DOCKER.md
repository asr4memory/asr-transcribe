# Docker Setup für asr-transcribe

## Voraussetzungen

- Docker Engine 20.10+ mit nvidia-docker2 Support
- Docker Compose 1.29+ (oder Docker Compose v2)
- NVIDIA GPU mit CUDA 13.1+ Support
- NVIDIA Container Toolkit installiert

### Installation des NVIDIA Container Toolkit

Ubuntu/Debian:
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

## Quick Start

1. **Konfiguration vorbereiten**:
```bash
cp config.example.toml config.toml
# config.toml mit Ihren Einstellungen bearbeiten
```

2. **Datenverzeichnisse erstellen**:
```bash
mkdir -p data/_input data/_output models
```

3. **Docker-Image bauen**:
```bash
docker-compose build
```

4. **Container starten**:
```bash
docker-compose up
```

## Konfiguration

### config.toml

Aktualisieren Sie die Pfade in Ihrer `config.toml` für Container-Pfade:

```toml
[system]
input_path = "/app/data/_input"
output_path = "/app/data/_output"
```

Für LLM-Modelle:
```toml
[llm]
model_path = "/app/models/your-model.gguf"
```

### GPU-Konfiguration

Standardmäßig sind alle GPUs verfügbar. Um spezifische GPU(s) zu verwenden:

```yaml
environment:
  - CUDA_VISIBLE_DEVICES=0  # Nur GPU 0 verwenden
```

### Volume Mounts

Die docker-compose.yml mounted:
- `./config.toml` → `/app/config.toml` (read-only)
- `./data/_input` → `/app/data/_input` (read-only)
- `./data/_output` → `/app/data/_output` (read-write)
- `./models` → `/app/models` (read-only, optional)

## Verwendung

### Dateien verarbeiten

1. Audio-Dateien in `./data/_input/` platzieren
2. Container starten:
```bash
docker-compose up
```
3. Verarbeitete Ausgabe erscheint in `./data/_output/`

### Einmalige Verarbeitung

```bash
docker-compose run --rm asr-transcribe
```

### Logs anzeigen

```bash
docker-compose logs -f asr-transcribe
```

### Interaktive Shell

```bash
docker-compose run --rm asr-transcribe bash
```

## Build

### Build-Argumente

Derzeit keine, können aber für Anpassungen hinzugefügt werden:

```dockerfile
ARG PYTHON_VERSION=3.12
ARG CUDA_VERSION=13.1.1
```

### Benutzerdefinierter Build

```bash
docker build -t asr-transcribe:custom .
```

## Fehlerbehebung

### GPU nicht erkannt

GPU-Verfügbarkeit prüfen:
```bash
docker-compose run --rm asr-transcribe nvidia-smi
```

### Berechtigungsprobleme

Sicherstellen, dass Datenverzeichnisse korrekte Berechtigungen haben:
```bash
chmod -R 755 data/
```

### cuDNN-Fehler

cuDNN-Symlinks verifizieren:
```bash
docker-compose run --rm asr-transcribe bash
ls -la /app/.venv/lib/python3.12/site-packages/nvidia/cudnn/lib/
```

### Out of Memory

batch_size in config.toml reduzieren:
```toml
[whisper]
batch_size = 16  # Von 28 reduzieren
```

## Performance-Optimierung

1. **GPU-Speicher**: `n_gpu_layers` in config.toml anpassen
2. **Batch-Größe**: `batch_size` für Ihre GPU anpassen
3. **Berechnungstyp**: `int8` für schnellere Verarbeitung verwenden (geringere Qualität)

## Erweiterte Verwendung

### Benutzerdefinierter Entrypoint

Ein anderes Script ausführen:
```bash
docker-compose run --rm asr-transcribe uv run python test_processing.py
```

### Entwicklungsmodus

Source-Code für Entwicklung mounten:
```yaml
volumes:
  - .:/app:rw
```

Dann nach Code-Änderungen neu bauen:
```bash
docker-compose exec asr-transcribe uv sync
```

## Produktions-Deployment

### Docker Compose verwenden

Für Produktion beachten:
1. Spezifische Image-Tags verwenden (nicht `latest`)
2. Health Checks hinzufügen
3. Log-Aggregation einrichten
4. Secrets Management für Tokens verwenden

### Beispiel Produktions docker-compose.yml

```yaml
services:
  asr-transcribe:
    image: asr-transcribe:1.1.0
    restart: always
    healthcheck:
      test: ["CMD", "test", "-f", "/app/config.toml"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Wartung

### Dependencies aktualisieren

Image nach Aktualisierung von pyproject.toml oder uv.lock neu bauen:
```bash
docker-compose build --no-cache
```

### Aufräumen

Container und Volumes entfernen:
```bash
docker-compose down -v
```

Images entfernen:
```bash
docker rmi asr-transcribe:latest
```

## Systemanforderungen

### Hardware
- NVIDIA GPU mit mindestens 8GB VRAM (empfohlen für large-v3 Modell)
- GPU mit Compute Capability >= 6.0
- Host-GPU-Treiber >= 530.30.02

### Software
- Docker Engine >= 20.10
- NVIDIA Container Toolkit
- CUDA-kompatible GPU

### Image-Größe
- Erwartete Größe: ~8-9 GB
  - Base CUDA Image: ~5 GB
  - System-Pakete: ~500 MB
  - Python-Dependencies: ~3 GB
  - Source Code: ~50 MB

## Bekannte Einschränkungen

1. **CUDA-Version**: Das Image ist für CUDA 13.1 gebaut. Wenn Ihr Host-Treiber älter ist, kann es zu Inkompatibilitäten kommen.
2. **Speicher**: LLM-Modelle können 10-20GB+ sein und sollten extern als Volume gemountet werden.
3. **Performance**: CPU-only Modus ist deutlich langsamer als GPU-beschleunigt.

## Sicherheitshinweise

1. **Read-only Volumes**: Input und Config sind read-only zur Sicherheit
2. **Keine Secrets im Image**: Config wird zur Laufzeit gemountet
3. **Log-Rotation**: Verhindert Festplattenvollauf
4. **Benutzerrechte**: Erwägen Sie, einen non-root User im Container zu verwenden

## Support und Feedback

Bei Problemen oder Fragen:
1. Prüfen Sie die Logs: `docker-compose logs -f asr-transcribe`
2. Verifizieren Sie GPU-Zugriff: `docker-compose run --rm asr-transcribe nvidia-smi`
3. Prüfen Sie die Hauptdokumentation im [README.md](README.md)

## Beispiel-Workflow

Kompletter Workflow von Anfang bis Ende:

```bash
# 1. Repository klonen und ins Verzeichnis wechseln
cd asr-transcribe

# 2. Konfiguration vorbereiten
cp config.example.toml config.toml
nano config.toml  # Pfade anpassen auf /app/data/_input und /app/data/_output

# 3. Verzeichnisse erstellen
mkdir -p data/_input data/_output models

# 4. Image bauen
docker-compose build

# 5. Audio-Datei zum Testen hinzufügen
cp /path/to/your/audio.mp3 data/_input/

# 6. Container starten und verarbeiten
docker-compose up

# 7. Ergebnisse prüfen
ls -la data/_output/

# 8. Container stoppen
docker-compose down
```

## Tipps und Tricks

### Schnellerer Build
```bash
# Build mit mehr Build-Parallelität
docker build --build-arg BUILDKIT_INLINE_CACHE=1 -t asr-transcribe .
```

### Speichernutzung überwachen
```bash
docker stats asr-transcribe
```

### Container-Ressourcen begrenzen
```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 16G
```

### Debugging
```bash
# Container mit interaktiver Shell starten
docker-compose run --rm asr-transcribe bash

# Im Container Dependencies prüfen
uv pip list

# CUDA prüfen
nvidia-smi

# Python-Version prüfen
python --version
```
