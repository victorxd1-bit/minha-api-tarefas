# main.py
from typing import Optional, Annotated, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import SQLModel, Field, Session, create_engine, select
from fastapi.responses import RedirectResponse


app = FastAPI()

# ===== 1) MODELO/TABELA =====
class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    done: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Esquemas de entrada/atualização (o que a API recebe)
class TaskCreate(SQLModel):
    title: str
    description: Optional[str] = None

class TaskUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    done: Optional[bool] = None

# ===== 2) BANCO/ENGINE/TABELAS =====
DATABASE_URL = "sqlite:///tasks.db"  # arquivo tasks.db na pasta do projeto
engine = create_engine(DATABASE_URL, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# ===== 3) SESSÃO POR REQUISIÇÃO =====
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# ===== 4) SAÚDE =====
@app.get("/ping")
def ping():
    return {"status": "ok"}
    
@app.get("/")  # deixa sem include_in_schema para aparecer no /docs
def root():
    return RedirectResponse(url="/docs")



# ===== 5) CRUD USANDO O BANCO =====
# Listar todas
@app.get("/tasks", response_model=List[Task])
def list_tasks(session: SessionDep):
    stmt = select(Task).order_by(Task.id)
    return session.exec(stmt).all()

# Criar
@app.post("/tasks", response_model=Task, status_code=201)
def create_task(data: TaskCreate, session: SessionDep):
    task = Task(title=data.title, description=data.description)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

# Buscar por id
@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int, session: SessionDep):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task não encontrada")
    return task

# Atualizar (parcial)
@app.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, data: TaskUpdate, session: SessionDep):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task não encontrada")

    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.done is not None:
        task.done = data.done

    session.add(task)
    session.commit()
    session.refresh(task)
    return task

# Apagar
@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, session: SessionDep):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task não encontrada")
    session.delete(task)
    session.commit()
    # 204: sem corpo

# ===== 6) CRIAR TABELAS NO STARTUP =====
@app.on_event("startup")
def on_startup():
    create_db_and_tables()





