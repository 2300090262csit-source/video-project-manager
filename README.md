# Video Project Manager

A full stack web app for video editors to organize footage, tag clips, search, and track edit versions.

## Features
- JWT authentication (signup, login, per-user data isolation)
- Create and delete projects
- Upload video, audio, and image clips with a 500 MB limit and file-type validation
- Tag clips and filter by tag
- Search clips by filename
- Version history notes for each clip
- Automated tests with pytest

## Tech Stack
- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic v2, PyJWT, bcrypt
- **Frontend:** React 18, Vite
- **Database:** SQLite for development, PostgreSQL supported via `DATABASE_URL`

## Run locally

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional, edit values
uvicorn app.main:app --reload
```
API docs: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
App: http://localhost:5173

### Tests
```bash
cd backend
pytest -q
```

## Project structure
```
backend/
  app/
    main.py        # app setup, CORS, routes mount
    routers.py     # all API endpoints
    models.py      # SQLAlchemy models
    schemas.py     # Pydantic request/response models
    auth.py        # password hashing, JWT, current user dependency
    database.py    # engine and session
  tests/test_api.py
frontend/
  src/App.jsx      # auth, projects, clip upload, tags, versions
```

## Roadmap
- Date range filter for clips
- Video thumbnails with FFmpeg
- Deploy backend on Render and frontend on Vercel

## Author
Vivek, B.Tech CS & IT
