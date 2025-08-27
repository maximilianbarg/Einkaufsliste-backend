from typing import Dict

import requests
from fastapi import status

from test.test_base import TestBase, url, item_data

class TestEditItemsAPI(TestBase):
    def test_add_item_to_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        # when
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
        collection_id = response.json()["id"]
        response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item_data)

        # when
        item_id = response.json()["id"]
        updated_item_data = {"name": "test_item_new", "description": "This is a new test item"}
        response = requests.put(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers, json=updated_item_data)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Item updated"

        self.assert_changes_event(collection_id, "edited", 1, headers, updated_item_data)

    def test_delete_item_in_collection(self):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)
        collection_id = response.json()["id"]
        response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item_data)

        # when
        item_id = response.json()["id"]
        response = requests.delete(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Item deleted"

        self.assert_changes_event(collection_id, "removed", 1, headers, item_data)