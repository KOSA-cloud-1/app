import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# .env 로드
load_dotenv()

app = FastAPI()

# =========================================================
# Ceph RGW(S3 API) 설정
# =========================================================
# 중요 : example.env.tmp 파일을 참고하여 .env 파일에 S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY 값을 설정해야 합니다.

S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET", "mybucket")

# boto3 S3 Client 생성
s3_client = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
)

# =========================================================
# AWS S3 (백업용) 설정
# =========================================================
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

aws_s3_client = None
if AWS_ACCESS_KEY and AWS_SECRET_KEY:
    aws_s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
    )

def get_s3_client_and_key(object_key: str):
    """
    object_key가 s3:// 로 시작하면 AWS S3용 클라이언트와 버킷/키를 반환,
    그렇지 않으면 Ceph S3용 클라이언트와 기본 버킷/키를 반환합니다.
    """
    if object_key.startswith("s3://"):
        if not aws_s3_client:
            raise HTTPException(
                status_code=500,
                detail="AWS S3 client is not configured (missing credentials)"
            )
        # s3://bucket-name/object-key 형식 파싱
        # 예: s3://my-backup-bucket/photos/uuid.jpg
        parts = object_key[5:].split("/", 1)
        if len(parts) == 2:
            bucket_name = parts[0]
            real_key = parts[1]
            return aws_s3_client, bucket_name, real_key
    
    return s3_client, S3_BUCKET, object_key

# =========================================================
# Bucket 자동 생성
# =========================================================

def create_bucket_if_not_exists():
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET)
        print(f"Bucket '{S3_BUCKET}' already exists.")
    except ClientError:
        print(f"Creating bucket '{S3_BUCKET}'...")
        s3_client.create_bucket(Bucket=S3_BUCKET)

create_bucket_if_not_exists()

# =========================================================
# 업로드
# =========================================================

@app.post("/upload")
async def upload_photo(file: UploadFile = File(...)):
    """
    파일 업로드 후 object_key 반환 (기본적으로 Ceph S3에 업로드)
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected"
        )

    # 확장자 추출
    file_extension = (
        file.filename.split(".")[-1]
        if "." in file.filename
        else "bin"
    )

    # UUID 기반 object_key 생성
    object_key = f"{uuid.uuid4()}.{file_extension}"

    try:
        # Ceph S3 업로드
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET,
            object_key,
            ExtraArgs={
                "ContentType": file.content_type
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not upload file: {e}"
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "Upload success",
            "object_key": object_key,
            "url": f"/photos/{object_key}"
        }
    )

# =========================================================
# 다운로드 / 조회
# =========================================================

@app.get("/photos/{object_key:path}")
async def get_photo(object_key: str):
    """
    Presigned URL 생성 후 Redirect
    """
    target_client, bucket, key = get_s3_client_and_key(object_key)

    try:
        # 파일 존재 확인
        target_client.head_object(
            Bucket=bucket,
            Key=key
        )

    except ClientError:
        raise HTTPException(
            status_code=404,
            detail=f"Photo not found: {object_key}"
        )

    try:
        # Presigned URL 생성
        presigned_url = target_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key
            },
            ExpiresIn=3600
        )

        return RedirectResponse(url=presigned_url)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not generate URL: {e}"
        )

# =========================================================
# 삭제
# =========================================================

@app.delete("/photos/{object_key:path}")
async def delete_photo(object_key: str):
    target_client, bucket, key = get_s3_client_and_key(object_key)

    try:
        # 존재 여부 확인
        target_client.head_object(
            Bucket=bucket,
            Key=key
        )

    except ClientError:
        raise HTTPException(
            status_code=404,
            detail=f"Photo not found: {object_key}"
        )

    try:
        target_client.delete_object(
            Bucket=bucket,
            Key=key
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not delete file: {e}"
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"Photo {object_key} deleted."
        }
    )

# =========================================================
# 파일 목록 조회
# =========================================================

@app.get("/photos")
async def list_photos():

    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET
        )

        files = []

        if "Contents" in response:
            for obj in response["Contents"]:
                files.append({
                    "object_key": obj["Key"],
                    "size": obj["Size"]
                })

        return {
            "bucket": S3_BUCKET,
            "count": len(files),
            "files": files
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )