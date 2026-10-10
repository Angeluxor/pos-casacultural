# ---------- Etapa 1: build del bundle de Vite ----------
FROM node:24-alpine AS build
WORKDIR /app

# Instala dependencias respetando el lockfile
COPY package*.json ./
RUN npm ci

# Copia el código y compila.
# VITE_API_URL se incrusta en tiempo de BUILD y debe ser accesible desde el navegador.
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---------- Etapa 2: servir los estáticos con nginx ----------
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
