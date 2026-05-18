import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
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
    파일 업로드 후 object_key 반환
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

@app.get("/photos/{object_key}")
async def get_photo(object_key: str):
    """
    Ceph에서 이미지를 서버 측에서 가져와 스트리밍 응답으로 반환
    (브라우저가 내부망 Ceph에 직접 접속하지 않아도 됨)
    """

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=object_key)
        content_type = response.get("ContentType", "image/jpeg")
        return StreamingResponse(response["Body"], media_type=content_type)

    except ClientError:
        raise HTTPException(
            status_code=404,
            detail="Photo not found"
        )

# =========================================================
# 삭제
# =========================================================

@app.delete("/photos/{object_key}")
async def delete_photo(object_key: str):

    try:
        # 존재 여부 확인
        s3_client.head_object(
            Bucket=S3_BUCKET,
            Key=object_key
        )

    except ClientError:
        raise HTTPException(
            status_code=404,
            detail="Photo not found"
        )

    try:
        s3_client.delete_object(
            Bucket=S3_BUCKET,
            Key=object_key
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