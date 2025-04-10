import requests
from fastapi import status

url = "http://localhost:8000"

def test_sign_up():
    data = {
        "username": "test_user",
        "fullname": "User One",
        "email": "user1@example.com",
        "password": "test_password",
        "admin_key": "09g25e02fha9ca"
    }

    response = requests.post(f"{url}/user/sign_up", params=data)

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()

def test_auth_succeed():
    data = {"username": "test_user", "password": "test_password"}

    response = requests.post(f"{url}/token", data=data)  

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()

def test_auth_failed():
    data = {"username": "user", "password": "password"}

    response = requests.post(f"{url}/token", data=data)  

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_sign_up_duplicate():
    data = {
        "username": "test_user",
        "fullname": "User One",
        "email": "user1@example.com",
        "password": "test_password",
        "admin_key": "09g25e02fha9ca"
    }

    response = requests.post(f"{url}/user/sign_up", params=data)  

    assert response.status_code == status.HTTP_409_CONFLICT

def test_delete_user():
    data = {
        "username": "test_user",
        "password": "test_password"
    }

    response = requests.post(f"{url}/user/delete", params=data)  

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "user deleted"