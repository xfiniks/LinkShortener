from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime, timezone

from app.database import get_db
from app.models import Link, User, Click
from app.schemas import LinkCreate, LinkResponse, LinkUpdate, LinkStats, LinkStatsDetailed, LinkSearchResponse
from app.utils import generate_short_code, build_short_url, is_expired
from app.dependencies import get_current_active_user, get_link_owner_or_admin, get_client_info
from app.cache import (
    cache_url, get_cached_url, cache_stats, get_cached_stats,
    cache_search_result, get_cached_search_result, invalidate_url_cache,
    check_and_update_popularity, is_popular_url, invalidate_stats_cache
)

router = APIRouter(tags=["links"])

# Перенаправление по короткой ссылке
@router.get("/{short_code}", include_in_schema=False)
async def redirect_to_url(
    short_code: str,
    request: Request,
    db: Session = Depends(get_db),
    client_info: dict = Depends(get_client_info)
):
    """Перенаправляет по короткой ссылке на оригинальный URL"""
    original_url = get_cached_url(short_code)
    
    if not original_url:
        link = db.query(Link).filter(Link.short_code == short_code).first()
        
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ссылка не найдена"
            )
        
        if is_expired(link.expires_at):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Срок действия ссылки истек"
            )
        
        original_url = link.original_url
        
        if is_popular_url(short_code):
            cache_url(short_code, original_url)
    
    link = db.query(Link).filter(Link.short_code == short_code).first()

    if link:
        link.click_count += 1
        link.last_accessed = datetime.now(timezone.utc)
        
        click = Click(
            link_id=link.id,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            referer=client_info.get("referer")
        )
        
        db.add(click)
        db.commit()
        
        check_and_update_popularity(short_code, link.click_count)
        
        invalidate_stats_cache(short_code)
    
    return RedirectResponse(url=original_url)

# Создание короткой ссылки
@router.post("/links/shorten", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
async def create_short_link(
    link_data: LinkCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user)
):
    """Создает короткую ссылку"""
    if link_data.custom_alias:
        existing_alias = db.query(Link).filter(
            Link.short_code == link_data.custom_alias
        ).first()
        
        if existing_alias:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользовательский алиас уже занят"
            )
        
        
        short_code = link_data.custom_alias
        
        new_link = Link(
            short_code=short_code,
            original_url=link_data.original_url,
            expires_at=link_data.expires_at,
            owner_id=current_user.id if current_user else None
        )
        
        db.add(new_link)
        db.commit()
        db.refresh(new_link)
    else:
        existing_link = db.query(Link).filter(Link.original_url == link_data.original_url).first()
        
        if existing_link:
            if existing_link.expires_at and existing_link.expires_at < datetime.now(timezone.utc):
                existing_link.expires_at = link_data.expires_at
                db.commit()
                db.refresh(existing_link)
            
            new_link = existing_link
        else:
            while True:
                short_code = generate_short_code()
                existing = db.query(Link).filter(Link.short_code == short_code).first()
                if not existing:
                    break
            
            new_link = Link(
                short_code=short_code,
                original_url=link_data.original_url,
                expires_at=link_data.expires_at,
                owner_id=current_user.id if current_user else None
            )
            
            db.add(new_link)
            db.commit()
            db.refresh(new_link)
    
    if link_data.custom_alias or is_popular_url(new_link.short_code):
        cache_url(new_link.short_code, new_link.original_url)
    
    cache_search_result(new_link.original_url, new_link.short_code)
    
    response = LinkResponse(
        short_code=new_link.short_code,
        original_url=new_link.original_url,
        short_url=build_short_url(new_link.short_code),
        created_at=new_link.created_at,
        expires_at=new_link.expires_at
    )
    
    return response

# Получение информации о ссылке
@router.get("/links/{short_code}", response_model=LinkResponse)
async def get_link_info(
    short_code: str,
    db: Session = Depends(get_db)
):
    """Получает информацию о короткой ссылке"""
    link = db.query(Link).filter(Link.short_code == short_code).first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ссылка не найдена"
        )
    
    # Проверяем срок действия
    if is_expired(link.expires_at):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Срок действия ссылки истек"
        )
    
    return LinkResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        short_url=build_short_url(link.short_code),
        created_at=link.created_at,
        expires_at=link.expires_at
    )

# Получение статистики по ссылке
@router.get("/links/{short_code}/stats", response_model=LinkStatsDetailed)
async def get_link_stats(
    short_code: str,
    db: Session = Depends(get_db)
):
    """Получает статистику использования короткой ссылки"""
    cached_stats = get_cached_stats(short_code)
    
    if cached_stats:
        return LinkStatsDetailed(**cached_stats)
    
    link = db.query(Link).filter(Link.short_code == short_code).first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ссылка не найдена"
        )
    
    recent_clicks = db.query(Click).filter(
        Click.link_id == link.id
    ).order_by(Click.timestamp.desc()).limit(10).all()
    
    stats = LinkStatsDetailed(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
        click_count=link.click_count,
        last_accessed=link.last_accessed,
        recent_clicks=recent_clicks
    )
    
    cache_stats(short_code, stats.model_dump(exclude={"recent_clicks"}))
    
    return stats

# Обновление ссылки
@router.put("/links/{short_code}", response_model=LinkResponse)
async def update_link(
    short_code: str,
    link_data: LinkUpdate,
    link: Link = Depends(get_link_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Обновляет URL для короткой ссылки"""
    if link_data.original_url:
        link.original_url = link_data.original_url
    
    db.commit()
    db.refresh(link)
    
    invalidate_url_cache(short_code)
    
    if is_popular_url(short_code):
        cache_url(short_code, link.original_url)
    
    return LinkResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        short_url=build_short_url(link.short_code),
        created_at=link.created_at,
        expires_at=link.expires_at
    )

# Удаление ссылки
@router.delete("/links/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    short_code: str,
    link: Link = Depends(get_link_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Удаляет короткую ссылку"""
    db.delete(link)
    db.commit()
    
    invalidate_url_cache(short_code)
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Поиск ссылки по оригинальному URL
@router.get("/links/search", response_model=LinkSearchResponse)
async def search_link_by_url(
    original_url: str,
    db: Session = Depends(get_db)
):
    """Ищет короткие ссылки по оригинальному URL"""
    links = db.query(Link).filter(
        Link.original_url == original_url,
        (Link.expires_at.is_(None) | (Link.expires_at > datetime.now(timezone.utc)))
    ).all()
    
    response_links = [
        LinkResponse(
            short_code=link.short_code,
            original_url=link.original_url,
            short_url=build_short_url(link.short_code),
            created_at=link.created_at,
            expires_at=link.expires_at
        ) for link in links
    ]
    
    return LinkSearchResponse(links=response_links, count=len(response_links))