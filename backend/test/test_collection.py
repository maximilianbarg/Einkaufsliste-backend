import requests
import pytest

url = "http://localhost:8000"

class TestCollectionAPI:
    def setup_method(self):
        """Create a user before each test"""
        self.username = "test_user"
        self.password = "test_password"
        self.data = {"username": self.username, "password": self.password}
        self.access_token = self.create_user()

    def teardown_method(self):
        """Delete the user after each test"""
        requests.post(f"{url}/user/delete", params=self.data)  
        
    def authenticate(self) -> str:
        response = requests.post(f"{url}/token", data=self.data)
        return response.json().get("access_token")

    def test_create_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        # when
        response = requests.post(f"{url}/private/create/test_collection", headers=headers)

        # then
        assert response.status_code == 200
        assert response.json()["message"] == "Collection 'test_collection' created successfully"
        assert response.json()["collection_id"] != None

    def test_add_item_to_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/private/create/test_collection", headers=headers)

        # when
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["collection_id"]
        response = requests.post(f"{url}/private/{collection_id}/item", headers=headers, json=item_data)

        # then
        assert response.status_code == 200
        assert response.json()["message"] == "Item created"
        assert response.json()["item_id"] != None

    def test_update_item_in_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/private/create/test_collection", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["collection_id"]
        response = requests.post(f"{url}/private/{collection_id}/item", headers=headers, json=item_data)

        # when
        item_id = response.json()["item_id"]
        item_data = {"name": "test_item_new", "description": "This is a new test item"}
        response = requests.put(f"{url}/private/{collection_id}/item/{item_id}", headers=headers, json=item_data)

        # then
        assert response.status_code == 200
        assert response.json()["message"] == "Item updated"

    def test_delete_item_in_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/private/create/test_collection", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["collection_id"]
        response = requests.post(f"{url}/private/{collection_id}/item", headers=headers, json=item_data)

        # when
        item_id = response.json()["item_id"]
        response = requests.delete(f"{url}/private/{collection_id}/item/{item_id}", headers=headers)

        # then
        assert response.status_code == 200
        assert response.json()["message"] == "Item deleted"

    def test_get_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/private/create/test_collection", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["collection_id"]
        response = requests.post(f"{url}/private/{collection_id}/item", headers=headers, json=item_data)

        # when
        response = requests.get(f"{url}/private/{collection_id}/items", headers=headers)

        # then
        assert response.status_code == 200
        assert response.json()["source"] != None
        assert response.json()["name"] == "test_collection"
        assert response.json()["data"] != None

    def test_delete_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/private/create/test_collection", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["collection_id"]
        response = requests.post(f"{url}/private/{collection_id}/item", headers=headers, json=item_data)

        # when
        response = requests.delete(f"{url}/private/{collection_id}", headers=headers)

        # then
        assert response.status_code == 200
        assert response.json() == {"message": f"Collection '{collection_id}' deleted successfully"}

    def create_user(self) -> str:
        # create user
        data = {
            "username": self.username,
            "fullname": "User One",
            "email": "user1@example.com",
            "password": self.password
        }

        response = requests.post(f"{url}/user/sign_up", params=data)   

        return response.json().get("access_token")
    