# API de Tarefas (FastAPI + SQLModel + SQLite)

API REST simples para gerenciar tarefas (to-do). Feita para estudo e portfólio.

## Tecnologias
- Python 3.10+ • FastAPI • SQLModel/SQLAlchemy • SQLite • Uvicorn

## Como rodar
~~~bash
py -m pip install -U fastapi uvicorn[standard] sqlmodel
py -m uvicorn main:app --reload
~~~

## Endpoints
- POST /tasks – cria tarefa  
- GET /tasks – lista tarefas  
- GET /tasks/{id} – busca por id  
- PATCH /tasks/{id} – atualiza campos (ex.: `done`)  
- DELETE /tasks/{id} – remove

## Acesse (local)
- Docs interativas (Swagger): http://127.0.0.1:8000/docs  
- Saúde (ping): http://127.0.0.1:8000/ping

- ## Acesse (produção)
- Docs: https://minha-api-tarefas.onrender.com/docs
- Ping: https://minha-api-tarefas.onrender.com/ping

