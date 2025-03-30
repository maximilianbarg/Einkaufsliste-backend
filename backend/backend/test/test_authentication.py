import requests

url = "http://localhost:8000"

def test_sign_up():
    data = {
        "username": "user1",
        "fullname": "User One",
        "email": "user1@example.com",
        "password": "password1"
    }

    response = requests.post(f"{url}/user/sign_up", params=data)

    assert response.status_code == 200
    assert "access_token" in response.json()

def test_auth_succeed():
    data = {"username": "user1", "password": "password1"}

    response = requests.post(f"{url}/token", data=data)  

    assert response.status_code == 200
    assert "access_token" in response.json()

def test_auth_failed():
    data = {"username": "user", "password": "password"}

    response = requests.post(f"{url}/token", data=data)  

    assert response.status_code == 401

def test_sign_up_duplicate():
    data = {
        "username": "user1",
        "fullname": "User One",
        "email": "user1@example.com",
        "password": "password1"
    }

    response = requests.post(f"{url}/user/sign_up", params=data)  

    assert response.status_code == 403

def test_delete_user():
    data = {
        "username": "user1",
        "password": "password1"
    }

    response = requests.post(f"{url}/user/delete", params=data)  

    assert response.status_code == 200
    assert response.json()["message"] == "user deleted"