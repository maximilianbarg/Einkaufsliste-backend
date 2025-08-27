from typing import Dict

import pytest
import requests
from fastapi import status

from test.test_base import TestBase, url, item_data, item_data_2


class TestGetItemsAPI(TestBase):
    @pytest.mark.parametrize("items,expected_size", [
        ([item_data], 1),
        ([item_data, item_data_2], 2),
    ])
    def test_get_collection(self, items, expected_size):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] is not None
        assert response.json()["name"] == "test_collection"
        assert len(response.json()["data"]) == expected_size

    @pytest.mark.parametrize("items,filter_string,expected_size,expected_items", [
        ([item_data, item_data_2], f"name={item_data["name"]}", 1, [item_data]),
        ([item_data, item_data_2], f"label={item_data["label"]}", 2, [item_data, item_data_2]),
    ])
    def test_get_collection_with_filter(self, items, filter_string, expected_size, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items?filter={filter_string}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] is not None
        assert response.json()["name"] == "test_collection"

        items = response.json()["data"]
        assert len(items) == expected_size

        for i, expected_item in enumerate(expected_items):
            assert items[i]["name"] == expected_item["name"]
            assert items[i]["description"] == expected_item["description"]

    @pytest.mark.parametrize("items,sort_string,expected_size,expected_items", [
        ([item_data, item_data_2], f"name=asc", 2, [item_data, item_data_2]),
        ([item_data, item_data_2], f"name=desc", 2, [item_data_2, item_data]),
    ])
    def test_get_collection_with_sort(self, items, sort_string, expected_size, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items?sort={sort_string}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] is not None
        assert response.json()["name"] == "test_collection"

        items = response.json()["data"]
        assert len(items) == expected_size

        for i, expected_item in enumerate(expected_items):
            assert items[i]["name"] == expected_item["name"]
            assert items[i]["description"] == expected_item["description"]

    @pytest.mark.parametrize("items,limit_string,limit,expected_items", [
        ([item_data, item_data_2], "1", 1, [item_data]),
        ([item_data, item_data_2], "2", 2, [item_data, item_data_2]),
    ])
    def test_get_collection_with_limit(self,items, limit_string, limit, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items?limit={limit_string}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] is not None
        assert response.json()["name"] == "test_collection"

        items = response.json()["data"]
        assert len(items) == limit

        for i, expected_item in enumerate(expected_items):
            assert items[i]["name"] == expected_item["name"]
            assert items[i]["description"] == expected_item["description"]

    @pytest.mark.parametrize("items,limit_string,limit,expected_items", [
        ([item_data, item_data_2], "1", 1, [item_data]),
        ([item_data, item_data_2], "2", 2, [item_data, item_data_2]),
    ])
    def test_get_collection_with_limit(self, items, limit_string, limit, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items?limit={limit_string}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source"] is not None
        assert response.json()["name"] == "test_collection"

        items = response.json()["data"]
        assert len(items) == limit

        for i, expected_item in enumerate(expected_items):
            assert items[i]["name"] == expected_item["name"]
            assert items[i]["description"] == expected_item["description"]