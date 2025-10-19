# app/main.py
from fastapi import FastAPI
from app import models
from app.database import engine
from app.routers import log, auth, users, workouts
import time # <-- Import time
from fastapi import FastAPI, Request # <-- Import Request
import os
from dotenv import load_dotenv
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
import logging
import sys


load_dotenv()

# Logging Configuration
date_format_string = "%dth %B %Y %H:%M:%S"
log_formatter = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt=date_format_string
)
log_file_handler = logging.FileHandler(os.getenv("LOG_FILE"))
log_file_handler.setFormatter(log_formatter)
log_stream_handler = logging.StreamHandler(sys.stdout)
log_stream_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_file_handler)
logger.addHandler(log_stream_handler)
logger.info("Application starting up...")

try:
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")
except Exception as e:
    logger.error(f"Error creating database tables: {e}", exc_info=True)
    raise

app = FastAPI()


# --- Request Logging Middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    # Log basic request info
    logger.info(f"Request: {request.method} {request.url.path} - From: {request.client.host}")
    
    response = await call_next(request) # Process the request
    
    process_time = (time.time() - start_time) * 1000 # Calculate duration in ms
    # Log response info
    logger.info(f"Response: {response.status_code} - Process Time: {process_time:.2f}ms")
    
    return response
# --- End Request Logging Middleware ---

app.include_router(auth.router)
app.include_router(log.router)
app.include_router(users.router)
app.include_router(workouts.router)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

@app.get("/")
def read_root():
    return {"message": "Nice try :)"}

logger.info("Application setup complete.")

