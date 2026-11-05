# Image de DÉVELOPPEMENT du frontend (serveur Vite avec rechargement à chaud).
# L'image de production (fichiers statiques servis par Nginx) viendra à l'étape 5.
FROM node:22-alpine

WORKDIR /app

# Même principe que pour le backend : dépendances d'abord, pour le cache Docker.
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
