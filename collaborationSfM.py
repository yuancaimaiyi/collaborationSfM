from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form  # 添加 Form 导入
from sqlmodel import SQLModel, Session, create_engine, select, Field
from celery import Celery
import subprocess
import os
import shutil
import uuid
from typing import Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 应用实例
app = FastAPI(title="ColabSfM API", description="A collaborative SfM service using COLMAP")

# 项目根目录
BASE_DIR = "projects"

# Celery 配置，使用 Redis 作为消息代理
celery_app = Celery("collaborationSfM", broker="redis://localhost:6380/0")

# SQLite 数据库配置，用于存储上传记录
sqlite_url = f"sqlite:///{BASE_DIR}/tasks.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

# 数据模型：记录每次上传的文件信息
class Upload(SQLModel, table=True):
    id: int = Field(primary_key=True)
    filename: str
    user_id: str
    region_name: str

def create_db_and_tables():
    logger.info("Creating projects directory...")
    os.makedirs(BASE_DIR, exist_ok=True)
    logger.info(f"Directory created or exists: {BASE_DIR}")
    logger.info(f"Creating database at: {sqlite_url}")
    SQLModel.metadata.create_all(engine)
    logger.info("Database creation attempted.")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

def get_session():
    with Session(engine) as session:
        yield session

@celery_app.task
def run_feature_extraction(database_path: str, image_dir: str):
    logger.info(f"Running feature extraction: database={database_path}, images={image_dir}")
    subprocess.run([
        "/home/yuancaimaiyi/文档/wayz/vismap/hera-vismap/vismap/build1/src/exe/colmap", "feature_extractor",
        "--database_path", database_path,
        "--image_path", image_dir,
        "--type", "0",
    ], check=True)

@celery_app.task
def run_reconstruction(database_path: str, image_dir: str, sparse_dir: str):
    logger.info(f"Running exhaustive matcher: database={database_path}")
    subprocess.run([
        "/home/yuancaimaiyi/文档/wayz/vismap/hera-vismap/vismap/build1/src/exe/colmap", "exhaustive_matcher",
        "--database_path", database_path
    ], check=True)
    logger.info(f"Running mapper: database={database_path}, images={image_dir}, output={sparse_dir}")
    subprocess.run([
        "/home/yuancaimaiyi/文档/wayz/vismap/hera-vismap/vismap/build1/src/exe/colmap", "mapper",
        "--database_path", database_path,
        "--image_path", image_dir,
        "--output_path", sparse_dir
    ], check=True)

@app.post("/create_region/", response_model=dict)
async def create_region(region_name: str):
    region_dir = f"{BASE_DIR}/{region_name}"
    image_dir = f"{region_dir}/images"
    sparse_dir = f"{region_dir}/sparse"
    database_path = f"{region_dir}/database.db"
    logger.info(f"Creating region: {region_dir}")
    os.makedirs(image_dir, exist_ok=True)
    os.makedirs(sparse_dir, exist_ok=True)
    logger.info(f"Region initialized: images={image_dir}, sparse={sparse_dir}")
    return {"region_name": region_name, "message": "Region initialized"}

@app.post("/upload_images/{region_name}/", response_model=dict)
async def upload_images(
    region_name: str,
    files: list[UploadFile] = File(...),
    user_id: str = Form(default="unknown"),  # 修改为 Form
    session: Session = Depends(get_session)
):
    region_dir = f"{BASE_DIR}/{region_name}"
    image_dir = f"{region_dir}/images"
    database_path = f"{region_dir}/database.db"
    logger.info(f"Checking if region exists: {image_dir}")
    if not os.path.exists(image_dir):
        logger.error(f"Region not found: {image_dir}")
        raise HTTPException(status_code=404, detail="Region not found, please create it first")

    try:
        session.exec(select(Upload))
        logger.info("Upload table exists")
    except Exception as e:
        logger.error(f"Upload table check failed: {str(e)}")
        SQLModel.metadata.create_all(engine)
        logger.info("Upload table recreated")

    try:
        for file in files:
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            file_path = f"{image_dir}/{unique_filename}"
            logger.info(f"Saving file to: {file_path}")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            upload = Upload(filename=unique_filename, user_id=user_id, region_name=region_name)
            logger.info(f"Adding upload record: {upload.dict()}")
            session.add(upload)
        logger.info("Committing to database")
        session.commit()
        logger.info("Commit successful")
    except Exception as e:
        logger.error(f"Database commit failed: {str(e)}")
        raise

    logger.info("Triggering feature extraction")
    run_feature_extraction.delay(database_path, image_dir)
    return {"region_name": region_name, "message": "Images uploaded, feature extraction started in background"}

@app.post("/upload_folder/{region_name}/", response_model=dict)
async def upload_folder(
    region_name: str,
    files: list[UploadFile] = File(...),
    user_id: str = Form(default="unknown"),  #  Form
    session: Session = Depends(get_session)
):
    region_dir = f"{BASE_DIR}/{region_name}"
    image_dir = f"{region_dir}/images"
    database_path = f"{region_dir}/database.db"
    logger.info(f"Checking if region exists: {image_dir}")
    if not os.path.exists(image_dir):
        logger.error(f"Region not found: {image_dir}")
        raise HTTPException(status_code=404, detail="Region not found, please create it first")

    try:
        session.exec(select(Upload))
        logger.info("Upload table exists")
    except Exception as e:
        logger.error(f"Upload table check failed: {str(e)}")
        SQLModel.metadata.create_all(engine)
        logger.info("Upload table recreated")

    try:
        for file in files:
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            file_path = f"{image_dir}/{unique_filename}"
            logger.info(f"Saving file to: {file_path}")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            upload = Upload(filename=unique_filename, user_id=user_id, region_name=region_name)
            logger.info(f"Adding upload record: {upload.dict()}")
            session.add(upload)
        logger.info("Committing to database")
        session.commit()
        logger.info("Commit successful")
    except Exception as e:
        logger.error(f"Database commit failed: {str(e)}")
        raise

    logger.info("Triggering feature extraction")
    run_feature_extraction.delay(database_path, image_dir)
    return {"region_name": region_name, "message": "Folder uploaded, feature extraction started in background"}

# /upload_zip/ 接口
@app.post("/upload_zip/{region_name}/", response_model=dict)
async def upload_zip(
    region_name: str,
    zip_file: UploadFile = File(...),
    user_id: str = Form(default="unknown"),  #  Form
    session: Session = Depends(get_session)
):
    """上传 ZIP 文件并解压到指定区域，支持子目录中的文件"""
    region_dir = f"{BASE_DIR}/{region_name}"
    image_dir = f"{region_dir}/images"
    database_path = f"{region_dir}/database.db"
    logger.info(f"Checking if region exists: {image_dir}")
    if not os.path.exists(image_dir):
        logger.error(f"Region not found: {image_dir}")
        raise HTTPException(status_code=404, detail="Region not found, please create it first")

    try:
        session.exec(select(Upload))
        logger.info("Upload table exists")
    except Exception as e:
        logger.error(f"Upload table check failed: {str(e)}")
        SQLModel.metadata.create_all(engine)
        logger.info("Upload table recreated")

    zip_path = f"{region_dir}/{zip_file.filename}"
    logger.info(f"Saving ZIP file to: {zip_path}")
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(zip_file.file, buffer)
    logger.info(f"Unpacking ZIP to: {image_dir}")
    shutil.unpack_archive(zip_path, image_dir)
    logger.info(f"Files after unpacking: {os.listdir(image_dir)}")

    try:
        for root, _, files in os.walk(image_dir):
            for filename in files:
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    original_path = os.path.join(root, filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    target_path = f"{image_dir}/{unique_filename}"
                    logger.info(f"Moving file from {original_path} to {target_path}")
                    shutil.move(original_path, target_path)
                    upload = Upload(filename=unique_filename, user_id=user_id, region_name=region_name)
                    logger.info(f"Adding upload record: {upload.dict()}")
                    session.add(upload)
        logger.info("Committing to database")
        session.commit()
        logger.info("Commit successful")
    except Exception as e:
        logger.error(f"Database commit failed: {str(e)}")
        raise

    for root, dirs, files in os.walk(image_dir, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):
                os.rmdir(dir_path)

    logger.info("Triggering feature extraction")
    run_feature_extraction.delay(database_path, image_dir)
    os.remove(zip_path)
    return {"region_name": region_name, "message": "ZIP uploaded, feature extraction started in background"}

@app.post("/reconstruct/{region_name}/", response_model=dict)
async def reconstruct(region_name: str, session: Session = Depends(get_session)):
    region_dir = f"{BASE_DIR}/{region_name}"
    image_dir = f"{region_dir}/images"
    sparse_dir = f"{region_dir}/sparse"
    database_path = f"{region_dir}/database.db"
    logger.info(f"Checking if region exists: {image_dir}")
    if not os.path.exists(image_dir):
        logger.error(f"Region not found: {image_dir}")
        raise HTTPException(status_code=404, detail="Region not found")

    logger.info("Triggering reconstruction")
    run_reconstruction.delay(database_path, image_dir, sparse_dir)
    return {"region_name": region_name, "message": "Reconstruction started in background", "output_dir": sparse_dir}

@app.get("/uploads/{region_name}/", response_model=list[dict])
async def get_uploads(region_name: str, session: Session = Depends(get_session)):
    logger.info(f"Querying uploads for region: {region_name}")
    uploads = session.exec(select(Upload).where(Upload.region_name == region_name)).all()
    logger.info(f"Found {len(uploads)} records for {region_name}")
    return [{"filename": u.filename, "user_id": u.user_id, "region_name": u.region_name} for u in uploads]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)