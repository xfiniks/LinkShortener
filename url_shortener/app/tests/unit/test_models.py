import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError
from app.models import User, Link, Click

def test_user_model(db):
    # Create user
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Test primary key and defaults
    assert user.id is not None
    assert user.created_at is not None
    assert user.is_active is True
    
    # Test uniqueness constraint
    duplicate_user = User(
        username="testuser",
        email="another@example.com",
        hashed_password="hashed_password"
    )
    db.add(duplicate_user)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_link_model(db):
    # Create link
    link = Link(
        short_code="abc123",
        original_url="https://example.com"
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    
    # Test primary key and defaults
    assert link.id is not None
    assert link.created_at is not None
    assert link.expires_at is None
    assert link.last_accessed is None
    assert link.click_count == 0
    assert link.owner_id is None
    
    # Test uniqueness constraint
    duplicate_link = Link(
        short_code="abc123",
        original_url="https://another-example.com"
    )
    db.add(duplicate_link)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_click_model(db):
    # Create link first
    link = Link(
        short_code="abc123",
        original_url="https://example.com"
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    
    # Create click
    click = Click(
        link_id=link.id,
        ip_address="192.168.1.1",
        user_agent="Test Browser",
        referer="https://example.com"
    )
    db.add(click)
    db.commit()
    db.refresh(click)
    
    # Test primary key and defaults
    assert click.id is not None
    assert click.timestamp is not None
    assert click.link_id == link.id

def test_relationships(db):
    # Create user
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password"
    )
    db.add(user)
    db.commit()
    
    # Create link owned by user
    link = Link(
        short_code="abc123",
        original_url="https://example.com",
        owner_id=user.id
    )
    db.add(link)
    db.commit()
    
    # Create clicks for the link
    click1 = Click(
        link_id=link.id,
        ip_address="192.168.1.1"
    )
    click2 = Click(
        link_id=link.id,
        ip_address="192.168.1.2"
    )
    db.add_all([click1, click2])
    db.commit()
    
    # Test relationships
    db.refresh(user)
    db.refresh(link)
    
    assert link in user.links
    assert link.owner == user
    assert len(link.clicks) == 2
    assert click1 in link.clicks
    assert click2 in link.clicks
    assert click1.link == link
    assert click2.link == link

def test_cascade_delete(db):
    # Create link
    link = Link(
        short_code="abc123",
        original_url="https://example.com"
    )
    db.add(link)
    db.commit()
    
    # Create clicks
    click = Click(
        link_id=link.id,
        ip_address="192.168.1.1"
    )
    db.add(click)
    db.commit()
    
    # Delete link - should cascade to clicks
    db.delete(link)
    db.commit()
    
    # Verify click is also deleted
    remaining_clicks = db.query(Click).filter(Click.link_id == link.id).count()
    assert remaining_clicks == 0