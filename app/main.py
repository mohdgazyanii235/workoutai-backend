# app/main.py
from fastapi import FastAPI
from app import models
from app.database import engine
from app.routers import log
import os
from dotenv import load_dotenv

load_dotenv()

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(log.router)

@app.get("/")
def read_root():
    return {"message": "Workout AI Backend is running!"}