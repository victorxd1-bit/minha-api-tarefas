# tests/test_tasks.py
import pytest

def _task_payload(title="Tarefa X", description="desc"):
    return {"title": title, "description": description}

@pytest.mark.anyio
async def test_ping(client):
    r = await client.get("/ping")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

@pytest.mark.anyio
async def test_create_validation_blank_title(client, auth_header):
    # somente espaços → deve falhar
    payload = _task_payload(title="   ")
    r = await client.post("/tasks", json=payload, headers=auth_header)
    assert r.status_code == 422  # pydantic valida

@pytest.mark.anyio
async def test_create_and_list_basic(client, auth_header):
    # cria 3 tarefas
    for i in range(3):
        r = await client.post("/tasks", json=_task_payload(title=f"Tarefa {i}"), headers=auth_header)
        assert r.status_code == 201
        assert r.json()["title"] == f"Tarefa {i}"

    # lista todas
    r = await client.get("/tasks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    # deve vir ordenado por created_at desc (newest) por padrão
    titles = [t["title"] for t in data]
    assert titles == ["Tarefa 2", "Tarefa 1", "Tarefa 0"]

@pytest.mark.anyio
async def test_pagination_and_sort(client):
    # pagina 2 itens a partir do 1º offset e ordena oldest
    r = await client.get("/tasks", params={"limit": 2, "offset": 1, "sort": "oldest"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    # oldest → Tarefa 0, Tarefa 1, Tarefa 2
    # com offset=1 e limit=2 → Tarefa 1, Tarefa 2
    titles = [t["title"] for t in data]
    assert titles == ["Tarefa 1", "Tarefa 2"]

@pytest.mark.anyio
async def test_update_done_and_filter(client, auth_header):
    # pega o id de uma tarefa existente
    r = await client.get("/tasks")
    first_id = r.json()[0]["id"]

    # marca como done = true
    r = await client.patch(f"/tasks/{first_id}", json={"done": True}, headers=auth_header)
    assert r.status_code == 200
    assert r.json()["done"] is True

    # filtra por done=true
    r = await client.get("/tasks", params={"done": True})
    assert r.status_code == 200
    data = r.json()
    assert any(t["id"] == first_id for t in data)

@pytest.mark.anyio
async def test_update_partial_title(client, auth_header):
    # pega uma tarefa (a segunda por exemplo)
    r = await client.get("/tasks")
    assert len(r.json()) >= 2
    second_id = r.json()[1]["id"]

    # atualiza só o title
    r = await client.patch(f"/tasks/{second_id}", json={"title": "Novo título"}, headers=auth_header)
    assert r.status_code == 200
    assert r.json()["title"] == "Novo título"

@pytest.mark.anyio
async def test_delete_and_404(client, auth_header):
    # pega uma tarefa e apaga
    r = await client.get("/tasks")
    task_id = r.json()[0]["id"]

    r = await client.delete(f"/tasks/{task_id}", headers=auth_header)
    assert r.status_code == 204

    # tentar buscá-la deve dar 404
    r = await client.get(f"/tasks/{task_id}")
    assert r.status_code == 404
