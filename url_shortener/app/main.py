from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn
import time
from datetime import datetime, timezone

from app.database import engine, Base, get_db
from app.routers import auth, links
from app.models import Link
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Запуск приложения...")
    
    with Session(engine) as db:
        expired_links = db.query(Link).filter(
            Link.expires_at < datetime.now(timezone.utc)
        ).all()
        
        for link in expired_links:
            db.delete(link)
        
        db.commit()
        print(f"Удалено {len(expired_links)} истекших ссылок")
    
    yield
    
    print("Завершение работы приложения...")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="API для сервиса сокращения ссылок",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(links.router)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    if request.url.path.startswith("/links") or request.url.path.startswith("/auth"):
        print(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
    
    return response

@app.get("/", tags=["root"])
async def root():
    return {
        "message": "URL Shortener API",
        "docs_url": "/docs",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)