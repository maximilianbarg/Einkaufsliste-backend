# build image
# docker build -t einkaufsliste_backend . 

# Basis-Image mit Python
FROM python:3.13-slim

# Arbeitsverzeichnis im Container setzen
WORKDIR /code

# Abhängigkeiten hinzufügen
COPY requirements.txt /code/requirements.txt

# Installieren der Python-Bibliotheken
RUN pip install --no-cache-dir -r /code/requirements.txt

# Application Code kopieren
COPY ./app /code/app

# Startbefehl für das Backend

ENV DEBUG=${DEBUG}

COPY ./start-api.sh /code/start-api.sh
RUN chmod +x /code/start-api.sh

ENTRYPOINT ["/code/start-api.sh"]