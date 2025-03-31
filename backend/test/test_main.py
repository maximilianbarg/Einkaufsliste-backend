import requests

url = "http://localhost:8000"

def test_read_main():
    response = requests.get(f"{url}/")
    assert response.status_code == 200
    assert response.json() == {"message": "Einkaufsliste Backend is running!"}