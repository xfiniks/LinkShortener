# URL Shortener API

A high-performance URL shortening service built with FastAPI, PostgreSQL, and Redis.

## Description

This URL Shortener API provides a robust solution for creating, managing, and tracking shortened URLs. Key features include:

- User authentication with JWT tokens
- Custom short code aliases
- URL expiration management
- Click tracking and statistics
- Caching system for popular links
- Background tasks for maintenance

## API Endpoints

### Authentication

- `POST /auth/register` - Register a new user
- `POST /auth/token` - Login and obtain JWT token

### URL Management

- `POST /links/shorten` - Create a shortened URL
- `GET /links/{short_code}` - Get information about a shortened URL
- `PUT /links/{short_code}` - Update a shortened URL
- `DELETE /links/{short_code}` - Delete a shortened URL
- `GET /links/{short_code}/stats` - Get usage statistics for a shortened URL
- `GET /links/search` - Search for shortened URLs by original URL
- `GET /{short_code}` - Redirect to the original URL

## Examples

### Create a shortened URL

```bash
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url": "https://example.com/very/long/url/that/needs/shortening"}'
```

Response:
```json
{
  "short_code": "a1b2c3d",
  "original_url": "https://example.com/very/long/url/that/needs/shortening",
  "short_url": "http://localhost:8000/a1b2c3d",
  "created_at": "2025-04-01T12:34:56.789012",
  "expires_at": null
}
```

### Create a shortened URL with custom alias

```bash
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "original_url": "https://example.com/very/long/url",
    "custom_alias": "mylink",
    "expires_at": "2025-05-01T00:00:00Z"
  }'
```

Response:
```json
{
  "short_code": "mylink",
  "original_url": "https://example.com/very/long/url",
  "short_url": "http://localhost:8000/mylink",
  "created_at": "2025-04-01T12:34:56.789012",
  "expires_at": "2025-05-01T00:00:00Z"
}
```

### Get URL statistics

```bash
curl -X GET "http://localhost:8000/links/mylink/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "short_code": "mylink",
  "original_url": "https://example.com/very/long/url",
  "created_at": "2025-04-01T12:34:56.789012",
  "expires_at": "2025-05-01T00:00:00Z",
  "click_count": 42,
  "last_accessed": "2025-04-01T13:45:12.345678",
  "recent_clicks": [
    {
      "timestamp": "2025-04-01T13:45:12.345678",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "referer": "https://search-engine.com"
    },
    ...
  ]
}
```

## Installation and Deployment

### Prerequisites

- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- Python 3.10+

### Environment Variables

Create a `.env` file in the project root with the following variables:

```
SECRET_KEY=your_secure_secret_key
BASE_URL=http://your-domain.com
DATABASE_URL=postgresql://postgres:password@db/url_shortener
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
```

### Running with Docker Compose

1. Clone this repository
2. Create the `.env` file as described above
3. Start the application:

```bash
docker-compose up -d
```

The API will be available at http://localhost:8000 with documentation at http://localhost:8000/docs

### Running Locally for Development

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start PostgreSQL and Redis (using Docker or locally)
4. Create the `.env` file with appropriate local settings
5. Run the application:

```bash
cd app
uvicorn main:app --reload
```

### Running Tests

```bash
pytest -v
```

For load testing:

```bash
locust -f locustfile.py
```

## Database Schema

### Users Table

| Column           | Type          | Description                      |
|------------------|---------------|----------------------------------|
| id               | Integer       | Primary key                      |
| username         | String(50)    | Unique username                  |
| email            | String(100)   | Unique email address             |
| hashed_password  | String(100)   | Bcrypt hashed password           |
| created_at       | DateTime      | Account creation timestamp       |
| is_active        | Boolean       | Account status                   |

### Links Table

| Column           | Type          | Description                      |
|------------------|---------------|----------------------------------|
| id               | Integer       | Primary key                      |
| short_code       | String(20)    | Unique short code for the URL    |
| original_url     | Text          | Original URL to redirect to      |
| created_at       | DateTime      | Link creation timestamp          |
| expires_at       | DateTime      | Expiration timestamp (optional)  |
| last_accessed    | DateTime      | Last access timestamp            |
| click_count      | Integer       | Number of clicks/redirects       |
| owner_id         | Integer       | Foreign key to users table       |

### Clicks Table

| Column           | Type          | Description                      |
|------------------|---------------|----------------------------------|
| id               | Integer       | Primary key                      |
| link_id          | Integer       | Foreign key to links table       |
| timestamp        | DateTime      | Click timestamp                  |
| ip_address       | String(50)    | User's IP address                |
| user_agent       | Text          | User's browser/device info       |
| referer          | Text          | Referring website                |

## Caching System

The application uses Redis for several caching mechanisms:

1. URL Caching: Popular URLs are cached for faster redirects
2. Click Buffering: Click data is buffered in Redis before batch-writing to the database
3. Statistics Tracking: Temporary counters and metrics before synchronization

## Performance Optimization

- Connection pooling for database connections
- Redis caching for frequently accessed URLs
- Background tasks for database cleanup and synchronization
- Deferred write operations for click statistics

## Project Structure

```
├── app/
│   ├── routers/
│   │   ├── auth.py             # Authentication endpoints
│   │   └── links.py            # URL management endpoints
│   ├── cache.py                # Redis cache operations
│   ├── config.py               # Application configuration
│   ├── database.py             # Database connection
│   ├── dependencies.py         # FastAPI dependencies
│   ├── json_utils.py           # JSON serialization utilities
│   ├── main.py                 # Main application entry point
│   ├── models.py               # SQLAlchemy ORM models
│   ├── schemas.py              # Pydantic schema models
│   └── utils.py                # Helper utilities
├── tests/                      # Test suite
├── docker-compose.yml          # Docker Compose configuration
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```