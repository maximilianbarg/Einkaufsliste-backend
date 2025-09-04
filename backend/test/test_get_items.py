import time

import pytest
import requests
from fastapi import status

from .test_base import TestBase, url, test_item_1, test_item_2, red_labeled_items, all_items, green_labeled_items, \
    test_item_3, test_item_4


class TestGetItemsAPI(TestBase):
    @pytest.mark.parametrize("items,expected_size", [
        ([test_item_1], 1),
        (red_labeled_items, 2),
        (all_items, 4),
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

        json_response = response.json()
        assert json_response["source"] is not None
        assert json_response["name"] == "test_collection"
        assert len(json_response["data"]) == expected_size

    @pytest.mark.parametrize("items,filter_string,expected_size,expected_items", [
        (all_items, f"name={test_item_1["name"]}", 1, [test_item_1]),
        (all_items, f"label={test_item_1["label"]}", 2, red_labeled_items),
        (all_items, f"label={test_item_3["label"]}", 2, green_labeled_items),
        (all_items, f"description={test_item_1["description"]}", 4, all_items),
    ])
    def test_get_collection_with_filter(self, items, filter_string, expected_size, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection_{expected_size}/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items?filter={filter_string}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK

        json_response = response.json()
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection_{expected_size}"

        items = json_response["data"]
        assert len(items) == expected_size

        for i, expected_item in enumerate(expected_items):
            assert items[i]["name"] == expected_item["name"]
            assert items[i]["description"] == expected_item["description"]

    @pytest.mark.parametrize("items,sort_string,expected_size,expected_items", [
        (red_labeled_items, f"name=asc", 2, red_labeled_items),
        (red_labeled_items, f"name=desc", 2, [test_item_2, test_item_1]),
        (all_items, f"label=asc,name=asc", 4, [test_item_3, test_item_4, test_item_1, test_item_2]),
    ])
    def test_get_collection_with_sort(self, items, sort_string, expected_size, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection_{expected_size}/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items?sort={sort_string}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK

        json_response = response.json()
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection_{expected_size}"

        items = json_response["data"]
        assert len(items) == expected_size

        for i, expected_item in enumerate(expected_items):
            assert items[i]["name"] == expected_item["name"]
            assert items[i]["description"] == expected_item["description"]

    @pytest.mark.parametrize("items,limit_string,limit,expected_items", [
        (red_labeled_items, "1", 1, [test_item_1]),
        (all_items, "2", 2, red_labeled_items),
        (all_items, "3", 3, [test_item_1, test_item_2, test_item_3]),
        (all_items, "4", 4, all_items),
    ])
    def test_get_collection_with_limit(self, items, limit_string, limit, expected_items):
        # given
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(f"{url}/collections/create/test_collection_{limit}/test", headers=headers)

        collection_id = response.json()["id"]

        for item in items:
            requests.post(f"{url}/collections/{collection_id}/item", headers=headers, json=item)

        # when
        response = requests.get(f"{url}/collections/{collection_id}/items?limit={limit_string}", headers=headers)

        # then
        assert response.status_code == status.HTTP_200_OK

        json_response = response.json()
        assert json_response["source"] is not None
        assert json_response["name"] == f"test_collection_{limit}"

        items = json_response["data"]
        assert len(items) == limit

        for i, expected_item in enumerate(expected_items):
            assert items[i]["name"] == expected_item["name"]
            assert items[i]["description"] == expected_item["description"]