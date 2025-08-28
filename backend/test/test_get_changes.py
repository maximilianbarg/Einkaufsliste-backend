import time
from typing import Dict

import pytest
import requests
from fastapi import status

from test.test_base import TestBase, url, test_item_1, all_items, red_labeled_items, green_labeled_items


class TestGetChangesAPI(TestBase):
    @pytest.mark.parametrize("items,expected_items", [
        ([test_item_1], [test_item_1]),
        (red_labeled_items, red_labeled_items),
        (all_items, all_items),
    ])
    def test_get_collection_changes(self, items, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] is not None
        assert response.json()["name"] == f"test_collection"

        for i, expected_item in enumerate(expected_items):
            self.assert_changes_event(collection_id, "created", i, headers, expected_item)