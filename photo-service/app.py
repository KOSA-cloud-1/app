import os
import time
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse, Response
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
import asyncio
# from diffusers import StableDiffusionImg2ImgPipeline
# import torch

# .env 로드
load_dotenv()

app = FastAPI()

# =========================================================
# Prometheus 메트릭 
# =========================================================
# 업로드 처리 흐름을 계측한다. Prometheus가 /metrics 를 주기적으로 scrape 한다.
PROFILE_IMAGE_REQUESTS = Counter(
    "profile_image_requests_total", "이미지 처리(업로드) 요청 수"
)
PROFILE_IMAGE_SUCCESS = Counter(
    "profile_image_success_total", "이미지 처리 성공 수"
)
PROFILE_IMAGE_FAILED = Counter(
    "profile_image_failed_total", "이미지 처리 실패 수"
)
PROFILE_IMAGE_PROCESSING_SECONDS = Histogram(
    "profile_image_processing_seconds",
    "이미지 처리 소요 시간(초)",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10),  # _bucket 생성 → P95 계산용
)
PROFILE_IMAGE_ACTIVE_JOBS = Gauge(
    "profile_image_active_jobs", "현재 처리 중인 작업 수"
)
PROFILE_IMAGE_QUEUE_DEPTH = Gauge(
    "profile_image_queue_depth", "대기 중인 이미지 처리 작업 수"
)
# photo-service는 내부 작업 큐가 없으므로 dashboard 계약을 위해 0으로 노출한다.
PROFILE_IMAGE_QUEUE_DEPTH.set(0)


@app.get("/metrics")
def metrics():
    """Prometheus scrape 대상 엔드포인트."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

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

    # 메트릭: 요청 수 증가 + 처리 중 작업 수 증가, 처리시간 측정 시작
    PROFILE_IMAGE_REQUESTS.inc()
    PROFILE_IMAGE_ACTIVE_JOBS.inc()
    start = time.perf_counter()

    try:
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

        PROFILE_IMAGE_SUCCESS.inc()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Upload success",
                "object_key": object_key,
                "url": f"/photos/{object_key}"
            }
        )

    except Exception:
        # 4xx/5xx 등 모든 예외를 실패로 집계 후 그대로 전달
        PROFILE_IMAGE_FAILED.inc()
        raise

    finally:
        PROFILE_IMAGE_ACTIVE_JOBS.dec()
        PROFILE_IMAGE_PROCESSING_SECONDS.observe(time.perf_counter() - start)

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

# pipe = None
@app.on_event("startup")
async def load_model():
    # global pipe
    print("AI 모델 로딩 중...")
    # pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
    #     "nitrosocke/Ghibli-Diffusion"
    # )
    # pipe.to("cuda")
    print("AI 모델 로딩 완료!")



# 최대 동시 처리 개수 제한
semaphore = asyncio.Semaphore(10)



# 실제 AI 모델 처리 함수
async def run_ai_model(object_key: str):

    # # 이미지 로드 + 리사이즈
    # init_image = Image.open(f"/static/{object_key}").convert("RGB")
    # init_image = init_image.resize((512, 512))

    # image = pipe(
    #     prompt="""
    #     ghibli style, Studio Ghibli, Miyazaki,
    #     anime character,
    #     soft watercolor illustration,
    #     pastel colors, warm soft lighting,
    #     dreamy atmosphere,
    #     best quality, masterpiece, highly detailed
    #     """,
    #     negative_prompt="""
    #     photorealistic, 3d render, blurry,
    #     ugly face, deformed face, disfigured,
    #     asymmetrical face, cross eyed,
    #     bad eyes, creepy eyes, dead eyes,
    #     scary, horror, dark, gloomy,
    #     bad anatomy, extra limbs, mutation,
    #     lowres, low quality, worst quality,
    #     text, watermark, signature,
    #     noise, grain
    #     """,
    #     image=init_image,
    #     strength=0.35,
    #     guidance_scale=7,
    #     num_inference_steps=50   # 30 → 40 디테일 향상
    #     ).images[0]

    # image.save(f"/static/result/{object_key}")

    # 예시용 딜레이
    await asyncio.sleep(3)


    return {
        print(f"converted_{object_key}: AI 이미지 변환을 진행중입니다.")
    }

# 변환 API
@app.get("/photos/ai/{object_key}")
async def convert_employee_image(object_key: str):

    if semaphore.locked() and semaphore._value == 0:
        raise HTTPException(
            status_code=429,
            detail="서버가 바쁩니다. 잠시 후 다시 시도해주세요."
        )

    async with semaphore:

        try:
            print(f"AI 이미지 변환 요청 : {object_key}")

            # AI 변환 수행
            result = await run_ai_model(object_key)

            return {
                "success": True,
                "message": "AI image converted successfully",
                "data": result
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"AI conversion failed: {str(e)}"
            )

@app.get("/photo-service/health")
def health_check():
    """
    Docker HEALTHCHECK를 위한 간단한 엔드포인트.
    성공적으로 응답하면 'ok' 상태를 반환합니다.
    """
    return {"status": "health ok"}


@app.get("/photo-service/ready")
def ready_check():
    """
    Docker HEALTHCHECK를 위한 간단한 엔드포인트.
    성공적으로 응답하면 'ok' 상태를 반환합니다.
    """
    return {"status": "ready ok"}



