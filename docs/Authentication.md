Die Authentifizierung wird über `JWT` geregelt.

# Create User
Für die Registrierung sind die angaben:
- username
- full name
- password
- email
- admin key
notwendig. 

`username` und `password` sind am wichtigsten, da über den `username` der benutzer eindeutig ist und das `password` den Account des users schützt.

`full name` hat nur die Funktion, um den Benutzer persönlich anreden zu können.

Der `admin key` wird genutzt, um zu verhindern, das sich unbefugte registieren können.

Die `email` hat bisher noch keinen Nutzen. Diese soll aber im späteren genutzt werden können, um das `password` zurückzusetzen.

```mermaid
zenuml
    title Sign up
    @Actor App
    @ElasticBeanTalk Backend
    @Database MongoDB
    App->Backend.sign_up(username, fullname, email,password, admin_key) {
        Backend->MongoDB.get_user(username) {
            return user
        }

        if(username_not_exists) {
            Backend->MongoDB.create_user(username) {
                return user
            }
            // logged in [200]
            return JWT
        }
        else {
            // username already taken [401]
            return 
        }
    }
```

# Login
Die Authentifizierung wird über `username` und `password` geregelt. Dabei wird der `username` in der collection `users` gesucht. Das gehashte `password` wird dekodiert und geprüft. Bei erfolgreicher Authentifizierung wird ein `JWT` zurückgegeben.

```mermaid
zenuml
    title Login
    @Actor App
    @ElasticBeanTalk Backend
    @Database MongoDB
    App->Backend.login(username, password) {
        Backend->MongoDB.get_user(username) {
            return user
        }
        if(success) {
            // logged in [200]
            return JWT
        }
        else {
            // auth failed [401]
            return
        }    
    }
```

# Delete User
Um einen Account zu löschen sind `username` und `password` notwendig. Über `username` wird der zu löschende Account referenziert. Das `password` wird als Sicherheit genutzt, damit niemand unbefugtes den Account löschen kann.

Später soll dies ebenfalls über die `email` sichergestellt werden.

```mermaid
zenuml
    title Delete
    @Actor App
    @ElasticBeanTalk Backend
    @Database MongoDB
    App->Backend.delete_user(username, password) {
        Backend->MongoDB.delete_user(username) {
            return user
        }
        if(success) {
            // user deleted [200]
            return
        }
        else {
            // auth failed [401]
            return
        }    
    }
```
