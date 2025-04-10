import requests
from fastapi import status

url = "http://localhost:8000"

def test_read_main():
    response = requests.get(f"{url}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Einkaufsliste Backend is running!"}