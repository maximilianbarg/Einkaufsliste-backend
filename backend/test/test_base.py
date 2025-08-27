from typing import Dict

import requests
from fastapi import status

url = "http://localhost:8000"
item_data = {"name": "test_item", "description": "This is a test item", "label": "red"}
item_data_2 = {"name": "test_item2", "description": "This is a test item too", "label": "red"}

class TestBase:

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

    def assert_changes_event(self, collection_id: str, event: str, event_index: int, headers, item_data: Dict):
        response = requests.get(f"{url}/collections/{collection_id}/changes", headers=headers)
        deleted_event = response.json()["data"][event_index]
        assert response.status_code == status.HTTP_200_OK
        assert deleted_event["event"] == event
        deleted_item = deleted_event["item"]
        assert deleted_item["name"] == item_data["name"]
        assert deleted_item["description"] == item_data["description"]