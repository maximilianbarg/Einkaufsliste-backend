import asyncio
import pytest
import aiohttp
import requests
import json
from fastapi import status
import time

url = "http://localhost:8000"
uri = "ws://localhost:8000/sockets/connect"
username2 = "test_websocket_user"
username1 = "test_websocket_user_2"
password = "test_password"


delay = 0.3

async def create_user(username: str, password: str) -> str:
    # Create user via POST request
    data = {
            "username": username,
            "fullname": "User One",
            "email": "user1@example.com",
            "password": password,
            "admin_key": "09g25e02fha9ca"
        }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{url}/user/sign_up", data=data) as response:
            # Warten auf die Antwort und den JSON-Inhalt extrahieren
            response_data = await response.json()  # Dies gibt ein Dictionary zurück
            return response_data.get("access_token")

def delete_user(username: str, password: str):
    data = {"username": username, "password": password}
    # Teardown after tests (delete user)
    requests.post(f"{url}/user/delete", data=data)


@pytest.mark.asyncio
async def test_websocket_connection_create_item():
    # given
    access_token_user_1 = await create_user(username1, password)
    access_token_user_2 = await create_user(username2, password)

    headers2 = {"Authorization": f"Bearer {access_token_user_2}"}
    headers1 = {"Authorization": f"Bearer {access_token_user_1}"}
    response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers2)
    item_data = {"name": "test_item", "description": "This is a test item"}

    response_data = response.json()
    collection_id = response_data.get("id")

    # when
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(uri, headers=headers2) as websocket:
            async def subscribe_user():
                post_url = f"{url}/sockets/channel/{collection_id}/subscribe"
                async with session.post(post_url, headers=headers2) as response:
                    assert response.status == status.HTTP_200_OK
                    
                time.sleep(delay)

            async def create_item():
                post_url = f"{url}/collections/{collection_id}/item"
                async with session.post(post_url, headers=headers1, json=item_data) as response:
                    assert response.status == status.HTTP_200_OK

            # Starte Task parallel
            await asyncio.create_task(subscribe_user())
            await asyncio.create_task(create_item())

            async for msg in websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close cmd':
                        await websocket.close()
                        break
                    else:
                        #await websocket.send_str(msg.data + '/answer')
                        event_response = msg.data
                        await websocket.close()
                        await session.close()
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

    # then
    data = json.loads(event_response)

    assert data["event"] == "created"
    assert data["item"] != None

    delete_user(username1, password)
    delete_user(username2, password)

#asyncio.run(test_websocket_connection_create_item())

@pytest.mark.asyncio
async def test_websocket_connection_edit_item():
    # given
    access_token_user_1 = await create_user(username1, password)
    access_token_user_2 = await create_user(username2, password)

    headers2 = {"Authorization": f"Bearer {access_token_user_2}"}
    headers1 = {"Authorization": f"Bearer {access_token_user_1}"}
    response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers2)
    item_data = {"name": "test_item", "description": "This is a test item"}

    response_data = response.json()
    collection_id = response_data.get("id")

    response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers2, json=item_data)
    response_data = response.json()
    item_id = response_data.get("id")

    item_data = {"name": "test_item_edited", "description": "This is a test item"}

    # when
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(uri, headers=headers2) as websocket:
            async def subscribe_user():
                post_url = f"{url}/sockets/channel/{collection_id}/subscribe"
                async with session.post(post_url, headers=headers2) as response:
                    assert response.status == status.HTTP_200_OK
                    
                time.sleep(delay)

            async def edit_item():
                post_url = f"{url}/collections/{collection_id}/item/{item_id}"
                async with session.put(post_url, headers=headers1, json=item_data) as response:
                    assert response.status == status.HTTP_200_OK

            # Starte Task parallel
            await asyncio.create_task(subscribe_user())
            await asyncio.create_task(edit_item())

            async for msg in websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close cmd':
                        await websocket.close()
                        break
                    else:
                        #await websocket.send_str(msg.data + '/answer')
                        event_response = msg.data
                        await websocket.close()
                        await session.close()
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

    # then
    data = json.loads(event_response)

    assert data["event"] == "edited"
    assert data["item"] != None

    delete_user(username1, password)
    delete_user(username2, password)

#asyncio.run(test_websocket_connection_edit_item())

@pytest.mark.asyncio
async def test_websocket_connection_remove_item():
    # given
    access_token_user_1 = await create_user(username1, password)
    access_token_user_2 = await create_user(username2, password)

    headers2 = {"Authorization": f"Bearer {access_token_user_2}"}
    headers1 = {"Authorization": f"Bearer {access_token_user_1}"}
    response = requests.post(f"{url}/collections/create/test_collection/test", headers=headers2)
    item_data = {"name": "test_item", "description": "This is a test item"}

    response_data = response.json()
    collection_id = response_data.get("id")

    response = requests.post(f"{url}/collections/{collection_id}/item", headers=headers2, json=item_data)
    response_data = response.json()
    item_id = response_data.get("id")

    # when
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(uri, headers=headers2) as websocket:
            async def subscribe_user():
                post_url = f"{url}/sockets/channel/{collection_id}/subscribe"
                async with session.post(post_url, headers=headers2) as response:
                    assert response.status == status.HTTP_200_OK

                time.sleep(delay)

            async def edit_item():
                post_url = f"{url}/collections/{collection_id}/item/{item_id}"
                async with session.delete(post_url, headers=headers1) as response:
                    assert response.status == status.HTTP_200_OK

            # Starte Task parallel
            await asyncio.create_task(subscribe_user())
            await asyncio.create_task(edit_item())

            async for msg in websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close cmd':
                        await websocket.close()
                        break
                    else:
                        #await websocket.send_str(msg.data + '/answer')
                        event_response = msg.data
                        await websocket.close()
                        await session.close()
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

    # then
    data = json.loads(event_response)

    assert data["event"] == "removed"
    assert data["id"] != None

    delete_user(username1, password)
    delete_user(username2, password)