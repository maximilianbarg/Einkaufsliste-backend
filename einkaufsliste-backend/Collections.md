## ids für collections
- welches Verfahren
- wie lang?
- was für Zeichen?

## Namensschema

`id` _ `private-oder-shared` _ `Verwendungszweck`

**Bsp.:** 
- `0123abc456def_private_notes` -> private Notizen von user mit user id 
- `0123abc456def_private_tasks` -> private tasks von user mit user id 
- `0223abc456def_shared_tasks` -> geteilte tasks mit der id 

>[!important]
>alle privaten Collections beginnen mit der **user id** diese ist eindeutig dem user zugeordnet. Bei den geteilten Collections wird eine neue **id** erstellt und inter der privaten Liste des user gespeichert

## Collections Diagram

```mermaid
erDiagram
    USER
    SHARED_COLLECTIONS {
        list collection_infos
    }
    SHARED_COLLECTION
    USER_SHARED_COLLECTIONS {
        list collection_ids
    }

    USER ||--o{ USER_SHARED_COLLECTIONS : "references id"
    SHARED_COLLECTIONS ||--|{ SHARED_COLLECTION : "referenced by id of collection"
    SHARED_COLLECTIONS ||--o{ USER : "references user_id"
```

## Role
### Mögliche Rollen:
#### admin
##### permissions:
- verwalten
- lesen 
- schreiben
#### user
##### permissions:
- lesen
- schreiben

```mermaid
classDiagram
	direction LR

	class Role {
        +role : string
        +admin : bool
        +read : bool
        +write : bool
    }
```

## User
```mermaid
classDiagram
	direction LR
    class User {
        +id : string
        +name : string
        +username: string
        +role : Role
        +notes : string
        +tasks : string
        +shared : list of string
    }
    
	class Role
    Role *-- User
```

## Collection Info
```mermaid
classDiagram
	direction LR
    class User
    
    class CollectionInfo {
        +id : string
        +Users : List of User
        +owner : User
    }

    User *-- Collection
```


## Collection
Die Collection hat eine **id** als Namen. Die Informationen zu Benutzer und Eigentümer Anzu
```mermaid
classDiagram
	direction LR
    class User
    
    class Collection {
	    +name : string
        +data : json
    }

    User *-- Collection
```

## Collection erstellen

## Collection löschen

## Collection entfernen

## Item zu Collection hinzufügen

## Item aus Collection aktualisieren

## Item aus Collection entfernen