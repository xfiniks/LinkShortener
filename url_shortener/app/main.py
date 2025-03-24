from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time
import asyncio
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.database import engine, Base, get_db, SessionLocal
from app.routers import auth, links
from app.models import Link, Click
from app.config import settings
from app.cache import (
    get_links_to_sync, get_buffered_clicks, get_buffered_last_access,
    reset_buffered_stats, get_and_clear_click_details, cache_url, invalidate_url_cache,
    get_cached_url
)
from app.utils import is_expired


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом приложения"""
    print("Запуск приложения...")
    
    with SessionLocal() as db:
        expired_links = db.query(Link).filter(
            Link.expires_at < datetime.now(timezone.utc)
        ).all()
        
        for link in expired_links:
            invalidate_url_cache(link.short_code)
            reset_buffered_stats(link.short_code)
            db.delete(link)
        
        db.commit()
        print(f"Удалено {len(expired_links)} истекших ссылок")
    
    cleanup_task = asyncio.create_task(periodically_cleanup_expired_links())
    sync_task = asyncio.create_task(periodically_sync_stats())
    
    app.state.background_tasks = {
        "cleanup": cleanup_task,
        "sync": sync_task
    }
    
    yield
    
    print("Завершение работы приложения...")
    
    for name, task in app.state.background_tasks.items():
        if not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                print(f"Задача {name} остановлена")


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


async def periodically_cleanup_expired_links():
    """Периодически удаляет ссылки с истекшим сроком действия"""
    while True:
        try:
            await asyncio.sleep(86400)  # 24 часа
            
            print(f"Запуск плановой очистки истекших ссылок ({datetime.now(timezone.utc)})")
            with SessionLocal() as db:
                expired_links = db.query(Link).filter(
                    Link.expires_at < datetime.now(timezone.utc)
                ).all()
                
                if not expired_links:
                    print("Истекших ссылок не найдено")
                    continue
                
                for link in expired_links:
                    invalidate_url_cache(link.short_code)
                    reset_buffered_stats(link.short_code)
                    db.delete(link)
                
                db.commit()
                print(f"Удалено {len(expired_links)} истекших ссылок")
                
        except asyncio.CancelledError:
            print("Задача очистки истекших ссылок отменена")
            break
        except Exception as e:
            print(f"Ошибка при очистке истекших ссылок: {e}")
            await asyncio.sleep(3600)


async def periodically_sync_stats():
    """Периодически синхронизирует статистику из Redis в БД"""
    while True:
        try:
            await asyncio.sleep(300)
            sync_stats_with_db()
        except asyncio.CancelledError:
            print("Задача синхронизации статистики отменена")
            break
        except Exception as e:
            print(f"Ошибка при синхронизации статистики: {e}")
            await asyncio.sleep(60)  # Повторная попытка через минуту


def sync_stats_with_db():
    """Синхронизирует статистику из Redis в базу данных"""
    links_to_sync = get_links_to_sync()
    if not links_to_sync:
        return
        
    print(f"Синхронизация статистики для {len(links_to_sync)} ссылок")
    
    db = SessionLocal()
    try:
        for short_code in links_to_sync:
            clicks = get_buffered_clicks(short_code)
            last_access = get_buffered_last_access(short_code)
            
            if clicks <= 0:
                reset_buffered_stats(short_code)
                continue
                
            link = db.query(Link).filter(Link.short_code == short_code).first()
            if not link:
                reset_buffered_stats(short_code)
                invalidate_url_cache(short_code)
                continue
            
            if is_expired(link.expires_at):
                reset_buffered_stats(short_code)
                invalidate_url_cache(short_code)
                continue
            
            link.click_count += clicks
            if last_access:
                link.last_accessed = last_access
            
            click_details = get_and_clear_click_details(short_code)
            for detail in click_details:
                try:
                    click = Click(
                        link_id=link.id,
                        timestamp=datetime.fromisoformat(detail.get("timestamp", "")),
                        ip_address=detail.get("ip_address", ""),
                        user_agent=detail.get("user_agent", ""),
                        referer=detail.get("referer", "")
                    )
                    db.add(click)
                except Exception as e:
                    print(f"Ошибка при добавлении клика: {e}")
            
            reset_buffered_stats(short_code)
            
            if link.click_count >= settings.POPULAR_URL_THRESHOLD and not get_cached_url(short_code):
                expire = None
                if link.expires_at:
                    now = datetime.now(timezone.utc)
                    if link.expires_at > now:
                        expire = int((link.expires_at - now).total_seconds())
                
                cache_url(short_code, link.original_url, expire)
        
        db.commit()
        print("Синхронизация завершена успешно")
    except Exception as e:
        db.rollback()
        print(f"Ошибка при синхронизации: {e}")
    finally:
        db.close()


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