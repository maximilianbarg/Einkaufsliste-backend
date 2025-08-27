from typing import Dict

import requests
from fastapi import status

from test.test_base import TestBase, url

class TestCollectionAPI(TestBase):

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