# build image
# docker build -t einkaufsliste_backend . 

# Basis-Image mit Python
FROM python:3.13-slim


# Arbeitsverzeichnis im Container setzen
WORKDIR /code

RUN ls /code

RUN ls .

# Umgebungsvariable DEBUG laden
ARG DEBUG
ENV DEBUG=${DEBUG}

# Abhängigkeiten-Dateien in das Image kopieren
COPY requirements.dev.txt /code/requirements.dev.txt
COPY requirements.prod.txt /code/requirements.prod.txt

# Bedingung zur Auswahl der richtigen requirements-Datei
RUN echo "DEBUG=$DEBUG" && \
    if [ $DEBUG -eq 1 ]; then \
        echo "DEBUG mode: using dev requirements"; \
        cp /code/requirements.dev.txt /code/requirements.txt; \
    else \
        echo "PROD mode: using prod requirements"; \
        cp /code/requirements.prod.txt /code/requirements.txt; \
    fi

# Installieren der Python-Bibliotheken
RUN pip install --no-cache-dir -r /code/requirements.txt

# Application Code kopieren
COPY ./app /code/app

# Startbefehl für das Backend

COPY ./start-api.sh /code/start-api.sh
RUN chmod +x /code/start-api.sh

ENTRYPOINT ["/code/start-api.sh"]