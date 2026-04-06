# Example Dockerfile for using Environment Forge with Docker volumes.
#
# Build:
#   docker build -t myapp .
#
# Run (with named volume):
#   docker run -v eforge_data:/eforge -e EFORGE_VAULT_PATH=/eforge myapp
#
# Pre-populate the volume:
#   eforge docker-init --copy-from .eforge --path /eforge

FROM python:3.12-slim

WORKDIR /app

# Install environment-forge
RUN pip install --no-cache-dir environment-forge

# Declare the volume mount point — secrets live here, not in /app
VOLUME /eforge

# Copy only your application code (no .eforge directory!)
COPY . .

# environment_forge.load() auto-detects /eforge
CMD ["python", "main.py"]
