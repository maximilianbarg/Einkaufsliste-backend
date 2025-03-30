import requests

url = "http://localhost:8000"

def authenticate() -> str:
    data = {"username": "user1", "password": "password1"}
    response = requests.post(f"{url}/token", data=data)
    return response.json().get("access_token")


def test_create_collection():
    access_token = create_user()
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.post(f"{url}/private/create/test_collection", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"message": "Collection 'test_collection' created successfully"}

def test_add_item_to_collection():
    access_token = authenticate()
    headers = {"Authorization": f"Bearer {access_token}"}

    requests.post(f"{url}/private/create/test_collection", headers=headers)

    item_data = {"name": "test_item", "description": "This is a test item"}

    response = requests.post(f"{url}/private/test_collection/item", headers=headers, json=item_data)

    assert response.status_code == 200
    assert response.json()["message"] == "Item created"
    assert response.json()["item_id"] != None


def test_delete_collection():
    access_token = authenticate()
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.delete(f"{url}/private/test_collection", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"message": "Collection 'test_collection' deleted successfully"}

    delete_user()


def create_user() -> str:
    # create user
    data = {
        "username": "user1",
        "fullname": "User One",
        "email": "user1@example.com",
        "password": "password1"
    }

    response = requests.post(f"{url}/user/sign_up", params=data)   

    return response.json().get("access_token")

def delete_user():
    data = {
        "username": "user1",
        "password": "password1"
    }

    response = requests.post(f"{url}/user/delete", params=data)  