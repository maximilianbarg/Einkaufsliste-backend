from typing import Dict

import requests
from fastapi import status

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
        requests.post(f"{url}/user/delete", data=self.data)

    def authenticate(self) -> str:
        response = requests.post(f"{url}/token", data=self.data)
        return response.json().get("access_token")

    def test_create_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # when
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Collection 'test_collection' created successfully"
        assert response.json()["id"] != None

    def test_get_collection_info(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        collection_id = response.json()["id"]

        # when
        response = requests.get(f"{url}/collections/{collection_id}/info", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] == "db"
        assert response.json()["data"] != None

    def test_add_item_to_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        # when
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["id"]
        response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item_data)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Item created"
        assert response.json()["id"] != None

        self.assert_changes_event(collection_id, "created", 0, headers, item_data)

    def test_update_item_in_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["id"]
        response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item_data)

        # when
        item_id = response.json()["id"]
        item_data = {"name": "test_item_new", "description": "This is a new test item"}
        response = requests.put(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers, json=item_data)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Item updated"

        self.assert_changes_event(collection_id, "edited", 1, headers, item_data)

    def test_rename_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        collection_id = response.json()["id"]

        # when
        new_collection_name = "test_collection_new"
        response = requests.patch(f"{url}/collections/{collection_id}/rename/{new_collection_name}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] != None

    def test_share_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        collection_id = response.json()["id"]

        # when
        user_id = "test_user_shared"
        response = requests.patch(f"{url}/collections/{collection_id}/users/add/{user_id}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] != None

    def test_unshare_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        collection_id = response.json()["id"]

        user_id = "test_user_shared"
        requests.patch(f"{url}/collections/{collection_id}/users/add/{user_id}", headers=headers)

        # when
        response = requests.patch(f"{url}/collections/{collection_id}/users/remove/{user_id}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] != None

    def test_delete_item_in_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["id"]
        response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item_data)

        # when
        item_id = response.json()["id"]
        response = requests.delete(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Item deleted"

        self.assert_changes_event(collection_id, "removed", 1, headers, item_data)

    def assert_changes_event(self, collection_id: str, event: str, event_index: int, headers, item_data: Dict):
        response = requests.get(f"{url}/collections/{collection_id}/changes", headers=headers)
        deleted_event = response.json()["data"][event_index]
        assert response.status_code == status.HTTP_200_OK
        assert deleted_event["event"] == event
        deleted_item = deleted_event["item"]
        assert deleted_item["name"] == item_data["name"]
        assert deleted_item["description"] == item_data["description"]

    def test_get_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["id"]
        response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item_data)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] != None
        assert response.json()["name"] == "test_collection"
        assert response.json()["data"] != None

    def test_get_collection_changes(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["id"]
        response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item_data)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] != None
        assert response.json()["name"] == "test_collection"

        self.assert_changes_event(collection_id, "created", 0, headers, item_data)

    def test_delete_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        item_data = {"name": "test_item", "description": "This is a test item"}
        collection_id = response.json()["id"]
        response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item_data)

        # when
        response = requests.delete(f"{url}/collections/{collection_id}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Collection deleted successfully"
        assert response.json()["id"] == collection_id

    def create_user(self) -> str:
        # create user
        data = {
            "username": self.username,
            "fullname": "User One",
            "email": "user1@example.com",
            "password": self.password,
            "admin_key": "09g25e02fha9ca"
        }

        response = requests.post(f"{url}/user/sign_up", data=data)

        return response.json().get("access_token")
