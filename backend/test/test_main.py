import requests
from fastapi import status

from .test_base import url

def test_read_main():
    response = requests.get(f"{url}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Einkaufsliste Backend is running!"}