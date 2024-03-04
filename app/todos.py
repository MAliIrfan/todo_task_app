from typing import Annotated
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from fastapi import APIRouter, Depends, HTTPException, Path,UploadFile, File
from starlette import status
import models
import database
import base64
import json
import redis
# from .auth import get_current_user
import logging

# Create a logger instance
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a file handler for logging
handler = logging.FileHandler('api_logs.log')
handler.setLevel(logging.INFO)

# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(handler)

router = APIRouter()
Todos = models.Todos
SessionLocal = database.SessionLocal

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def load_cached_report(report_name):
    report_data = redis_client.get(report_name)
    if report_data:
        return json.loads(report_data)
    return None

def save_report_to_cache(report_name, data):
    redis_client.setex(report_name, 900, json.dumps(data))  # Expire after 900 seconds (15 minutes)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
# user_dependency = Annotated[dict, Depends(get_current_user)]


class TodoRequest(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=3, max_length=100)
    priority: int = Field(gt=0, lt=6)
    complete: bool

@router.get("/healthy")
def health_check():
    logger.info('Health check endpoint called.')
    return {'status': 'Healthy'}


@router.get("/", status_code=status.HTTP_200_OK)
async def read_all(db: db_dependency):
    logger.info('Read all todos endpoint called.')
    record = db.query(Todos).all()
    for i in record:
        if i.file:
            file_data_base64 = base64.b64encode(i.file).decode("utf-8")
            i.file = file_data_base64

    logger.info('Read all todos endpoint successfully executed.')
    return record


@router.get("/todo/{todo_id}", status_code=status.HTTP_200_OK)
async def read_todo( db: db_dependency, todo_id: int = Path(gt=0)):
    logger.info(f'Read todo with ID {todo_id} endpoint called.')

    todo_model = db.query(Todos).filter(Todos.id == todo_id).first()
    if todo_model is not None:
    #     return todo_model
        if todo_model.file:
            file_data_base64 = base64.b64encode(todo_model.file).decode("utf-8")
            todo_model.file = file_data_base64
        logger.info(f'Read todo with ID {todo_id} endpoint successfully executed.')
        return todo_model
    logger.info(f'Todo with ID {todo_id} not found.')
    raise HTTPException(status_code=404, detail='Todo not found.')


@router.post("/todo", status_code=status.HTTP_201_CREATED)
async def create_todo(db: db_dependency,
                      todo_request: TodoRequest):
    logger.info('Create todo endpoint called.')
    # if user is None:
    #     raise HTTPException(status_code=401, detail='Authentication Failed')
    data = todo_request.model_dump()
    todo_exist = db.query(Todos).filter(Todos.title == data["title"]).first()
    if todo_exist:
        logger.info('tsak with title found')
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Todo item already exists")
    else:
        todo_model = Todos(**todo_request.model_dump())

        db.add(todo_model)
        db.commit()
        logger.info('Create todo endpoint successfully executed.')


@router.put("/todo/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_todo(db: db_dependency,
                      todo_request: TodoRequest,
                      todo_id: int = Path(gt=0)):
    logger.info(f'Update todo with ID {todo_id} endpoint called.')


    todo_model = db.query(Todos).filter(Todos.id == todo_id).first()
    if todo_model is None:
        logger.info(f'Todo with ID {todo_id} not found.')
        raise HTTPException(status_code=404, detail='Todo not found.')

    todo_model.title = todo_request.title
    todo_model.description = todo_request.description
    todo_model.priority = todo_request.priority
    todo_model.complete = todo_request.complete

    db.add(todo_model)
    db.commit()
    logger.info(f'Update todo with ID {todo_id} endpoint successfully executed.')


@router.delete("/todo/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(db: db_dependency, todo_id: int = Path(gt=0)):
    logger.info(f'Delete todo with ID {todo_id} endpoint called.')

    todo_model = db.query(Todos).filter(Todos.id == todo_id).first()
    if todo_model is None:
        logger.info(f'Todo with ID {todo_id} not found.')
        raise HTTPException(status_code=404, detail='Todo not found.')
    db.query(Todos).filter(Todos.id == todo_id).delete()

    db.commit()
    logger.info(f'Delete todo with ID {todo_id} endpoint successfully executed.')


@router.post("/todos/{todo_id}/upload_file/")
async def upload_file(todo_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    logger.info(f'Upload file for todo with ID {todo_id} endpoint called.')
    todo = db.query(Todos).filter(Todos.id == todo_id).first()
    if not todo:
        return {"error": "Todo not found"}

    contents = await file.read()
    todo.file = contents
    db.commit()
    logger.info(f'Upload file for todo with ID {todo_id} endpoint successfully executed.')
    return {"filename": file.filename, "status": "uploaded"}

@router.get("/tasks/count")
def get_task_counts(db: Session = Depends(get_db)):
    logger.info('Get task counts endpoint called.')
    cached_report = load_cached_report("tasks-count")
    if cached_report:
        return cached_report
    total_tasks = db.query(Todos).count()
    completed_tasks = db.query(Todos).filter(Todos.complete == True).count()
    remaining_tasks = total_tasks - completed_tasks
    res = {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "remaining_tasks": remaining_tasks
    }
    save_report_to_cache("tasks-count", res)
    logger.info('Get task counts endpoint successfully executed.')
    return res


# Endpoint to get the average number of tasks completed per day
@router.get("/tasks/average-per-day")
def get_avg_tasks_per_day(db: Session = Depends(get_db)):
    logger.info('Get average tasks per day endpoint called.')
    cached_report = load_cached_report("average_tasks_per_day")
    if cached_report:
        return cached_report
    avg_tasks = db.query(func.count(Todos.id).label("task_count"), cast(Todos.completed_at, Date).label("completed_at"))\
        .group_by(cast(Todos.completed_at, Date)).order_by(func.count(Todos.id).desc()).all()
    if not avg_tasks:
        logger.info('No tasks found.')
        return {"average_tasks_per_day": 0}
    total_days = len(avg_tasks)
    total_tasks = sum(task.task_count for task in avg_tasks)
    res = {"average_tasks_per_day": total_tasks / total_days}
    save_report_to_cache("average_tasks_per_day", res)
    logger.info('Get average tasks per day endpoint successfully executed.')
    return res

# Endpoint to get the date with the maximum number of tasks completed in a single day
@router.get("/tasks/max-tasks-single-day")
def get_max_tasks_single_day(db: Session = Depends(get_db)):
    logger.info('Get date with max tasks in a single day endpoint called.')
    cached_report = load_cached_report("max-tasks-single-day")
    if cached_report:
        return cached_report
    max_tasks_day = db.query(func.count(Todos.id).label("task_count"), cast(Todos.completed_at, Date).label("completed_at"))\
        .group_by(cast(Todos.completed_at, Date)).order_by(func.count(Todos.id).desc()).first()
    if not max_tasks_day:
        logger.info('No tasks found.')
        return {"max_tasks_single_day": None}
    res = {"max_tasks_single_day": max_tasks_day.completed_at}
    save_report_to_cache("max-tasks-single-day", res)
    logger.info('Get date with max tasks in a single day endpoint successfully executed.')
    return res

# Endpoint to get the date(s) with the maximum number of tasks added on a particular day
@router.get("/tasks/max-tasks-added-day")
def get_max_tasks_added_day(db: Session = Depends(get_db)):
    logger.info('Get date with max tasks added in a single day endpoint called.')
    cached_report = load_cached_report("max_tasks_added_day")
    if cached_report:
        return cached_report
    max_tasks_added_day = db.query(func.count(Todos.id).label("task_count"), cast(Todos.created_at, Date).label("created_at"))\
        .group_by(cast(Todos.created_at, Date)).order_by(func.count(Todos.id).desc()).first()
    if not max_tasks_added_day:
        logger.info('No tasks found.')
        return {"max_tasks_added_day": None}
    max_task_count = max_tasks_added_day.task_count
    max_task_dates = [task.created_at for task in db.query(Todos).filter(cast(Todos.created_at, Date) == max_tasks_added_day.created_at).all()]
    res = {"max_tasks_added_day": {"date": max_task_dates, "task_count": max_task_count}}
    save_report_to_cache("max_tasks_added_day", res)
    return res












