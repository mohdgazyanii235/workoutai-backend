# app/main.py
from fastapi import FastAPI
from app import models, crud # Added crud import
from app.database import engine, SessionLocal # Added SessionLocal import
from app.routers import log, auth, users, workouts, templates, social, notifications, admin
import time # <-- Import time
from fastapi import FastAPI, Request # <-- Import Request
import os
from dotenv import load_dotenv
import json
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
import logging
import sys
from app.auth import auth_service # Added auth_service import


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
    
    # 1. Capture request body if it's not a GET/DELETE request
    request_body_log = {}
    if request.method not in ["GET", "DELETE"]:
        try:
            # Read the body as bytes
            body = await request.body()
            # Try to decode and parse as JSON
            request_body_log = json.loads(body.decode('utf-8'))
            
            # Re-insert the body back into the request's scope so the endpoint can read it
            request._body = body 
        except json.JSONDecodeError:
            request_body_log = {"error": "Could not decode request body as JSON"}
        except Exception as e:
            request_body_log = {"error": f"Failed to read request body: {e}"}

    # --- NEW: Log user activity to DB if authenticated ---
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = auth_service.decode_token(token)
            user_id = payload.get("sub")
            
            if user_id:
                # Create a new DB session just for this logging operation
                db = SessionLocal()
                try:
                    crud.log_app_metric(db, user_id)
                finally:
                    db.close()
        except Exception as e:
            # Don't block the request if logging fails, just log the error
            logger.error(f"Failed to log app metric: {e}")
    # -----------------------------------------------------

    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log the request details
    logger.info(
        f"Request: {request.client.host}:{request.client.port} - "
        f"{request.method} {request.url.path} "
        f"Status: {response.status_code} "
        f"Processing Time: {process_time:.4f}s "
        f"Request Body: {json.dumps(request_body_log)}" # Log the captured body
    )
    return response
app.include_router(auth.router)
app.include_router(log.router)
app.include_router(users.router)
app.include_router(workouts.router)
app.include_router(templates.router)
app.include_router(social.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

@app.get("/")
def read_root():
    return {"message": "Nice try :)"}

logger.info("Application setup complete.")