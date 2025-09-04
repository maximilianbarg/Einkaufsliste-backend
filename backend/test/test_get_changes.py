import time
from datetime import datetime, UTC

import pytest
import requests
from fastapi import status

from .test_base import TestBase, url, test_item_1, all_items, red_labeled_items


class TestGetChangesAPI(TestBase):
    @pytest.mark.parametrize("items,expected_items", [
        ([test_item_1], [test_item_1]),
        (red_labeled_items, red_labeled_items),
        (all_items, all_items),
    ])
    def test_get_collection_changes_created_items(self, items, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes", headers=headers)

        # then
        json_response = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection"

        for i, expected_item in enumerate(expected_items):
            self.assert_changes_event(collection_id, "created", i, headers, expected_item)

    @pytest.mark.parametrize("items", [
        ([test_item_1]),
        red_labeled_items,
        all_items,
    ])
    def test_get_collection_changes_edited_items(self, items):
        # given
        updated_items = []
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for i, item in enumerate(items):
            response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

            item_id = response.json()["id"]

            updated_item_data = item.copy()
            updated_item_data["name"] = f"new_name_{i}"
            updated_items.append(updated_item_data)

            requests.put(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers,
                                    json=updated_item_data)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes", headers=headers)

        # then
        json_response = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection"

        for i, expected_item in enumerate(items):
            self.assert_changes_event(collection_id, "created", i, headers, expected_item, filter_string="event=created")

        for i, expected_item in enumerate(updated_items):
            self.assert_changes_event(collection_id, "edited", i, headers, expected_item, filter_string="event=edited")

    @pytest.mark.parametrize("items", [
        ([test_item_1]),
        red_labeled_items,
        all_items,
    ])
    def test_get_collection_changes_removed_items(self, items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for i, item in enumerate(items):
            response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

            item_id = response.json()["id"]
            requests.delete(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes", headers=headers)

        # then
        json_response = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection"

        for i, expected_item in enumerate(items):
            self.assert_changes_event(collection_id, "created", i, headers, expected_item,
                                      filter_string="event=created")

        for i, expected_item in enumerate(items):
            self.assert_changes_event(collection_id, "removed", i, headers, expected_item, filter_string="event=removed")

    @pytest.mark.parametrize("items,expected_size", [
        ([test_item_1], 0),
    ])
    def test_get_collection_changes_only_last_modifications_created_edited_removed(self, items, expected_size):
        # given
        updated_items = []
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for i, item in enumerate(items):
            # create
            response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

            item_id = response.json()["id"]

            # edit
            updated_item_data = item.copy()
            updated_item_data["name"] = f"new_name_{i}"
            updated_items.append(updated_item_data)

            requests.put(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers,
                         json=updated_item_data)

            # remove
            requests.delete(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes?history=false", headers=headers)

        # then
        json_response = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection"
        assert len(json_response["data"]) == expected_size



    @pytest.mark.parametrize("items,expected_size", [
        ([test_item_1], 2),
    ])
    def test_get_collection_changes_only_last_modifications_created_edited_edited(self, items, expected_size):
        # given
        updated_items = []
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for i, item in enumerate(items):
            # create
            response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

            item_id = response.json()["id"]

            # edit
            updated_item_data = item.copy()
            updated_item_data["name"] = f"new_name_{i}"

            requests.put(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers,
                         json=updated_item_data)

            # edit
            updated_item_data_2 = item.copy()
            updated_item_data_2["name"] = f"new_name_{i*10}"
            updated_items.append(updated_item_data_2)

            requests.put(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers,
                         json=updated_item_data_2)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes?history=false", headers=headers)

        # then
        json_response = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection"
        assert len(json_response["data"]) == expected_size

        for i, expected_item in enumerate(items):
            self.assert_changes_event(collection_id, "created", i, headers, expected_item,
                                      filter_string="event=created")

        for i, expected_item in enumerate(updated_items):
            self.assert_changes_event(collection_id, "edited", i, headers, expected_item,
                                      filter_string="event=edited")

    @pytest.mark.parametrize("items,expected_size", [
        ([test_item_1], 1),
    ])
    def test_get_collection_changes_only_last_modifications_created(self, items, expected_size):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for i, item in enumerate(items):
            # create
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes?history=false", headers=headers)

        # then
        json_response = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection"
        assert len(json_response["data"]) == expected_size

        for i, expected_item in enumerate(items):
            self.assert_changes_event(collection_id, "created", i, headers, expected_item,
                                      filter_string="event=created")

    @pytest.mark.parametrize("items,expected_size", [
        ([test_item_1], 1),
    ])
    def test_get_collection_changes_only_last_modifications_edited(self, items, expected_size):
        # given
        updated_items = []
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        timestamp = ""

        for i, item in enumerate(items):
            # create
            response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

            item_id = response.json()["id"]

            response = requests.get(f"{url}/collections/{collection_id}/info", headers=headers)
            timestamp = response.json()["data"]["last_modified"]

            # edit
            updated_item_data = item.copy()
            updated_item_data["name"] = f"new_name_{i}"
            updated_items.append(updated_item_data)

            requests.put(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers,
                         json=updated_item_data)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes?filter=timestamp>{timestamp}&history=false", headers=headers)

        # then
        json_response = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection"
        assert len(json_response["data"]) == expected_size

        for i, expected_item in enumerate(updated_items):
            self.assert_changes_event(collection_id, "edited", i, headers, expected_item,
                                      filter_string="event=edited")

    @pytest.mark.parametrize("items,expected_size", [
        ([test_item_1], 1),
    ])
    def test_get_collection_changes_only_last_modifications_edited_removed(self, items, expected_size):
        # given
        updated_items = []
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        timestamp = ""

        for i, item in enumerate(items):
            # create
            response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

            item_id = response.json()["id"]

            response = requests.get(f"{url}/collections/{collection_id}/info", headers=headers)
            timestamp = response.json()["data"]["last_modified"]

            # edit
            updated_item_data = item.copy()
            updated_item_data["name"] = f"new_name_{i}"
            updated_items.append(updated_item_data)

            requests.put(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers,
                         json=updated_item_data)

            # remove
            requests.delete(f"{url}/collections/{collection_id}/item/{item_id}", headers=headers)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/changes?filter=timestamp>{timestamp}&history=false", headers=headers)

        # then
        json_response = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection"
        assert len(json_response["data"]) == expected_size

        for i, expected_item in enumerate(updated_items):
            self.assert_changes_event(collection_id, "removed", i, headers, expected_item,
                                      filter_string="event=removed")