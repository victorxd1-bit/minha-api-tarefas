# conftest.py
import os
import pytest
import httpx
from httpx import ASGITransport

from main import app  # sua FastAPI

@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request):
    return request.param

@pytest.fixture
def auth_header(monkeypatch):
    token = os.getenv("API_TOKEN", "test-token")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def client(anyio_backend, request, auth_header):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # A maioria dos testes espera começar com 3 tarefas padrão.
        # EXCEÇÃO: o teste que verifica criação/listagem básica (ele mesmo cria 3).
        test_name = request.node.name  # ex.: "test_create_and_list_basic[asyncio]"
        if not test_name.startswith("test_create_and_list_basic"):
            for i in range(3):
                payload = {"title": f"Tarefa {i}", "description": "desc"}
                r = await client.post("/tasks", json=payload, headers=auth_header)
                assert r.status_code in (201, 409), r.text  # 409 se rodar duas vezes no mesmo nodeid
        yield client
