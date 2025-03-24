from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
import validators

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None

class LinkBase(BaseModel):
    original_url: str = Field(..., description="Оригинальный URL для сокращения")
    
    @field_validator('original_url')
    def validate_url(cls, v):
        if not validators.url(v):
            raise ValueError("Недействительный URL")
        return v

class LinkCreate(LinkBase):
    custom_alias: Optional[str] = Field(None, min_length=3, max_length=20, 
                                       description="Пользовательский алиас для короткой ссылки")
    expires_at: Optional[datetime] = Field(None, description="Время истечения срока действия ссылки")

class LinkUpdate(BaseModel):
    original_url: Optional[str] = Field(None, description="Новый оригинальный URL")
    
    @field_validator('original_url')
    def validate_url(cls, v):
        if v is not None and not validators.url(v):
            raise ValueError("Недействительный URL")
        return v

class ClickInfo(BaseModel):
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class LinkStats(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    click_count: int
    last_accessed: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class LinkStatsDetailed(LinkStats):
    recent_clicks: List[ClickInfo] = []
    
    model_config = ConfigDict(from_attributes=True)

class LinkResponse(BaseModel):
    short_code: str
    original_url: str
    short_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class LinkSearchResponse(BaseModel):
    links: List[LinkResponse]
    count: int