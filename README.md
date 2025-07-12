# Einkaufsliste Backend

![Tests](https://img.shields.io/github/actions/workflow/status/maximilianbarg/Einkaufsliste-backend/run-tests.yml?branch=main&label=Tests)

Ein Backend-Projekt mit [FastAPI](https://fastapi.tiangolo.com/), [Redis](https://redis.io/) und [MongoDB](https://www.mongodb.com/). Es bietet eine REST API zur Verwaltung von Collections und einen Realtime Listener, um Änderungen live zu verfolgen.

Die Anwendung ist in der In der Lage mehrere `worker` simultan laufen zu haben (vgl. `./backend/start-api.sh`), indem redis stream zur Verteilung der Live Änderungen einer Collection and den jeweiligen subscriber (Real time listener) verwendet wird. Dadurch kann je nach Auslastung die Anzahl der `worker` frei gewählt werden.   

## Features

- **REST API**: CRUD-Operationen für Collections
- **Redis Cache**: Schnelle Zwischenspeicherung von Daten
- **Redis Stream**: Schnelle Verteilung der Nachrichten an die jeweilige websocket Verbindung
- **MongoDB**: Persistente Speicherung der Collections
- **Realtime Listener**: Live-Updates bei Änderungen in Collections

## Installation

``` shell
git clone https://github.com/<username>/Einkaufsliste-backend.git
cd Einkaufsliste-backend
pip install -r requirements.txt
```

### Konfiguration
In der Datei `.env` die nötigen Attribute setzen:
```bash
nano ./backend/.env
```
``` env
MONGO_ROOT_USERNAME=<unique name>
MONGO_ROOT_PASSWORD=<unique password>
MONGO_DATABASE=<my_database>
REDIS_HOST=redis
SECRET_KEY=<random key>
ADMIN_KEY=<password to create accounts>
DEBUG=0 # 1 oder 0
```


### starten der Anwendungen
``` shell
docker compose up --build -d
```

## API Endpunkte
In `.env`-Datei `DEBUG=1` einstellen. Dann Swagger UI unter `http://localhost:8000/docs` aufrufen.
