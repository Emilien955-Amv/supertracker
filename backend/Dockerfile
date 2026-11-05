# Image du backend FastAPI.
FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE : pas de fichiers .pyc inutiles dans l'image.
# PYTHONUNBUFFERED : les journaux s'affichent immédiatement dans « docker logs ».
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# On copie d'abord UNIQUEMENT les listes de dépendances : tant qu'elles ne
# changent pas, Docker réutilise cette couche en cache et la reconstruction
# de l'image prend quelques secondes au lieu de plusieurs minutes.
COPY requirements.txt requirements-dev.txt ./

ARG INSTALL_DEV=false
RUN pip install -r requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; fi

COPY . .

# Sécurité : le serveur ne tourne pas en tant que « root ».
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
