import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import create_access_token, get_current_user, hash_password, verify_password
from .database import get_db

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".jpg", ".png"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

os.makedirs(UPLOAD_DIR, exist_ok=True)
router = APIRouter(prefix="/api")


# ---------- helpers ----------

def get_owned_project(project_id: int, user: models.User, db: Session) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(404, "Project not found")
    return project


def get_owned_clip(clip_id: int, user: models.User, db: Session) -> models.Clip:
    clip = db.get(models.Clip, clip_id)
    if clip is None or clip.project.owner_id != user.id:
        raise HTTPException(404, "Clip not found")
    return clip


# ---------- auth ----------

@router.post("/auth/signup", response_model=schemas.Token, status_code=201)
def signup(data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=data.email).first():
        raise HTTPException(409, "Email already registered")
    user = models.User(email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return schemas.Token(access_token=create_access_token(user.id))


@router.post("/auth/login", response_model=schemas.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=form.username).first()
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return schemas.Token(access_token=create_access_token(user.id))


# ---------- projects ----------

@router.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Project)
        .filter_by(owner_id=user.id)
        .order_by(models.Project.created_at.desc())
        .all()
    )


@router.post("/projects", response_model=schemas.ProjectOut, status_code=201)
def create_project(
    data: schemas.ProjectCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = models.Project(name=data.name, description=data.description, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    for clip in project.clips:
        if os.path.exists(clip.stored_path):
            os.remove(clip.stored_path)
    db.delete(project)
    db.commit()


# ---------- clips ----------

@router.post("/projects/{project_id}/clips", response_model=schemas.ClipOut, status_code=201)
async def upload_clip(
    project_id: int,
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_owned_project(project_id, user, db)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext or 'none'}")

    stored_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    size = 0
    with open(stored_path, "wb") as out:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                break
            out.write(chunk)

    if size > MAX_UPLOAD_BYTES:
        os.remove(stored_path)
        raise HTTPException(413, "File too large (max 500 MB)")

    clip = models.Clip(
        filename=file.filename,
        stored_path=stored_path,
        size_bytes=size,
        project_id=project.id,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


@router.get("/projects/{project_id}/clips", response_model=list[schemas.ClipOut])
def list_clips(
    project_id: int,
    q: str | None = Query(None, description="Search by filename"),
    tag: str | None = Query(None, description="Filter by tag name"),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_owned_project(project_id, user, db)
    query = db.query(models.Clip).filter(models.Clip.project_id == project.id)
    if q:
        query = query.filter(models.Clip.filename.ilike(f"%{q}%"))
    if tag:
        query = query.filter(models.Clip.tags.any(models.Tag.name == tag.strip().lower()))
    return query.order_by(models.Clip.uploaded_at.desc()).all()


@router.get("/clips/{clip_id}/file")
def download_clip(clip_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    clip = get_owned_clip(clip_id, user, db)
    return FileResponse(clip.stored_path, filename=clip.filename)


@router.delete("/clips/{clip_id}", status_code=204)
def delete_clip(clip_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    clip = get_owned_clip(clip_id, user, db)
    if os.path.exists(clip.stored_path):
        os.remove(clip.stored_path)
    db.delete(clip)
    db.commit()


# ---------- tags ----------

@router.post("/clips/{clip_id}/tags", response_model=schemas.ClipOut)
def add_tag(
    clip_id: int,
    data: schemas.TagCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clip = get_owned_clip(clip_id, user, db)
    name = data.name.strip().lower()
    tag = db.query(models.Tag).filter_by(name=name).first() or models.Tag(name=name)
    if tag not in clip.tags:
        clip.tags.append(tag)
    db.commit()
    db.refresh(clip)
    return clip


# ---------- edit versions ----------

@router.post("/clips/{clip_id}/versions", response_model=schemas.VersionOut, status_code=201)
def add_version(
    clip_id: int,
    data: schemas.VersionCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clip = get_owned_clip(clip_id, user, db)
    version = models.Version(number=len(clip.versions) + 1, note=data.note, clip_id=clip.id)
    db.add(version)
    db.commit()
    db.refresh(version)
    return version
