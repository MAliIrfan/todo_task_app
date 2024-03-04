from fastapi import FastAPI
import models
import database
import todos
app = FastAPI()

models.Base.metadata.create_all(bind=database.engine)
app.include_router(todos.router)
