# Country Rebel SIS - Backend

FastAPI backend for the Country Music Story Intelligence System.

## Setup

1. **Install Dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

3. **Database Setup**
   ```bash
   # Make sure PostgreSQL is running
   # Create database: country_rebel_sis
   
   # Run migrations
   alembic upgrade head
   ```

4. **Run the Application**
   ```bash
   python main.py
   ```

## API Documentation

- **Development**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## Key Features

- **REST API**: Complete API for stories, alerts, trends, competitors, and briefs
- **WebSocket**: Real-time updates for dashboard
- **Background Jobs**: Automated RSS ingestion, story processing, and alert generation
- **Data Processing**: Story clustering, impact scoring, and competitor monitoring

## Configuration

Key environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `AWARIO_API_KEY`: Awario API key (optional)
- `GOOGLE_TRENDS_API_KEY`: Google Trends API key (optional)
- `OPENAI_API_KEY`: OpenAI API key (optional)
- `SLACK_WEBHOOK_URL`: Slack webhook for alerts (optional)

## Background Jobs

The system runs several background jobs:

- **RSS Ingestion**: Every 15 minutes
- **Item Processing**: Every 5 minutes
- **Story Scoring**: Every 10 minutes
- **Alert Generation**: Every 2 minutes
- **Competitor Monitoring**: Every 15 minutes
- **Brief Generation**: At 6:00 AM and 7:00 PM

## Database Schema

See `shared/Database_Schema.md` for complete schema documentation.

## API Endpoints

See `shared/API_Contract.md` for complete API documentation.

## Development

- **Linting**: `black . && isort .`
- **Type Checking**: `mypy .`
- **Testing**: `pytest`
