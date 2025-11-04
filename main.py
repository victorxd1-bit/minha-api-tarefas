from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter
from typing import Generator, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, field_validator
from sqlmodel import Field, SQLModel, Session, create_engine, select


# ------------------------------------------------------------------------------
# Env & Logging config
# ------------------------------------------------------------------------------
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_JSON = os.getenv("LOG_JSON", "false").lower() == "true"
SLOW_MS = int(os.getenv("LOG_SLOW_MS", "500"))

# Reconfigura o Loguru: um único sink em stdout
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    enqueue=True,
    backtrace=False,
    diagnose=False,
    serialize=LOG_JSON,
)
logger.bind(component="bootstrap").info(
    "Logger configurado", level=LOG_LEVEL, json=LOG_JSON
)

# ------------------------------------------------------------------------------
# Config & app
# ------------------------------------------------------------------------------
API_TOKEN = os.getenv("API_TOKEN", "test-token")
DB_PATH = os.getenv("DB_PATH", "tasks.db")

app = FastAPI(title="Tasks API")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
logger.bind(component="db").info("Conectando ao banco", db_path=DB_PATH, url=f"sqlite:///{DB_PATH}")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    if engine is None:
        raise RuntimeError("Engine not initialized yet.")
    with Session(engine) as session:
        yield session


# ------------------------------------------------------------------------------
# Modelos
# ------------------------------------------------------------------------------
class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = "desc"
    done: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskCreate(BaseModel):
    title: str | None = None
    description: str | None = None
    done: bool | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank_if_provided(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("title cannot be blank")
        return v.strip()


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    done: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def title_if_present_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("title must not be blank")
        return v.strip() if isinstance(v, str) else v


class TaskRead(BaseModel):
    id: int
    title: str
    description: str
    done: bool
    created_at: datetime


# ------------------------------------------------------------------------------
# Cria as tabelas
# ------------------------------------------------------------------------------
SQLModel.metadata.create_all(engine)


# ------------------------------------------------------------------------------
# App lifecycle & middlewares
# ------------------------------------------------------------------------------
@app.on_event("startup")
def _on_startup():
    logger.bind(component="app").info("API iniciando...", name=app.title, version="v1")


@app.on_event("shutdown")
def _on_shutdown():
    logger.bind(component="app").info("API finalizando...")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.bind(component="http").exception(
            "Unhandled error",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            client=str(request.client.host if request.client else None),
        )
        raise

    duration_ms = (perf_counter() - start) * 1000
    bind = logger.bind(
        component="http",
        method=request.method,
        path=request.url.path,
        query=str(request.url.query),
        status=response.status_code,
        ms=round(duration_ms, 2),
        client=str(request.client.host if request.client else None),
    )
    if duration_ms > SLOW_MS:
        bind.warning("slow request")
    else:
        bind.info("request")

    return response


# ------------------------------------------------------------------------------
# Exception handlers
# ------------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.bind(component="http").warning(
        "HTTPException",
        status=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.bind(component="http").warning(
        "ValidationError",
        errors=exc.errors(),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# ------------------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------------------
def require_bearer_token(request: Request) -> None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = auth.removeprefix("Bearer ").strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ------------------------------------------------------------------------------
# Rotas
# ------------------------------------------------------------------------------
@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.post(
    "/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_bearer_token)],
)
def create_task(payload: TaskCreate):
    with get_session() as session:
        task = Task(
            title=payload.title,
            description=payload.description.strip() if payload.description else "desc",
            done=bool(payload.done) if payload.done is not None else False,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


@app.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    limit: int = 3,           # padrão alinhado com o teste
    offset: int = 0,
    sort: str = "newest",     # "oldest" | "newest"
    done: Optional[bool] = None,
):
    with get_session() as session:
        query = select(Task)
        if done is not None:
            query = query.where(Task.done == done)

        if sort == "oldest":
            query = query.order_by(Task.created_at.asc(), Task.id.asc())
        else:
            query = query.order_by(Task.created_at.desc(), Task.id.desc())

        rows = session.exec(query.offset(offset).limit(limit)).all()
        return rows


@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: int):
    with get_session() as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task


@app.patch(
    "/tasks/{task_id}",
    response_model=TaskRead,
    dependencies=[Depends(require_bearer_token)],
)
def update_task(task_id: int, payload: TaskUpdate):
    with get_session() as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        if payload.title is not None:
            task.title = payload.title
        if payload.description is not None:
            task.description = payload.description
        if payload.done is not None:
            task.done = payload.done

        session.add(task)
        session.commit()
        session.refresh(task)
        return task


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_bearer_token)],
)
def delete_task(task_id: int):
    with get_session() as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        session.delete(task)
        session.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
