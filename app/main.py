# app/main.py
from fastapi import FastAPI
from app import models
from app.database import engine
from app.routers import log, auth, users, workouts
import os
from dotenv import load_dotenv
import uvicorn
from starlette.middleware.sessions import SessionMiddleware


load_dotenv()

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth.router)
app.include_router(log.router)
app.include_router(users.router)
app.include_router(workouts.router)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

@app.get("/")
def read_root():
    return {"message": "Workout AI Backend is running!"}

