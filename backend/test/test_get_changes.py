from typing import Dict

import requests
from fastapi import status

from test.test_base import TestBase, url

class TestGetChangesAPI(TestBase):
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
        assert response.json()["source"] is not None
        assert response.json()["name"] == "test_collection"

        self.assert_changes_event(collection_id, "created", 0, headers, item_data)