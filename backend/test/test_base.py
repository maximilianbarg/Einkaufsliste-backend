import time
from typing import Dict

import requests
from fastapi import status

url = "http://localhost:8000"
test_item_1 = {"name": "test_item", "description": "test item", "label": "red"}
test_item_2 = {"name": "test_item2", "description": "test item", "label": "red"}
test_item_3 = {"name": "test_item3", "description": "test item", "label": "green"}
test_item_4 = {"name": "test_item4", "description": "test item", "label": "green"}

red_labeled_items = [test_item_1, test_item_2]
green_labeled_items = [test_item_3, test_item_4]
all_items = red_labeled_items + green_labeled_items

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
        time.sleep(0.1)

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

        change_event = response.json()["data"][event_index]
        assert response.status_code == status.HTTP_200_OK
        assert change_event["event"] == event
        assert change_event["timestamp"] is not None

        changed_item = change_event["item"]
        assert changed_item["name"] == item_data["name"]
        assert changed_item["description"] == item_data["description"]
        assert changed_item["label"] == item_data["label"]