FROM python:3.11.9-slim

# Evitar prompts interactivos durante apt install
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema y LibreOffice
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-common \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de la app
WORKDIR /app

# Crear los directorios para datos y logs por buenas prácticas
RUN mkdir -p /app/data /app/logs

# Copiar requirements primero (para aprovechar la cache)
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Eliminamos el archivo de configuración de desarrollo que se copió en el paso anterior.
RUN rm /app/config/config.yaml

# Luego, copiamos el archivo de configuración del contenedor y lo renombramos a config.yaml
COPY config/container_config.yaml /app/config/config.yaml

# Comando por defecto
CMD ["python", "app.py"]
