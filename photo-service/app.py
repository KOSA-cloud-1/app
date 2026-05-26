import os
import time
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
)
import asyncio
# from diffusers import StableDiffusionImg2ImgPipeline
# import torch

# .env 로드
load_dotenv()

app = FastAPI()

# FastAPI HTTP 계측: /upload, /photos/*, /photos/ai/* 등 photo-service 전체 API의
# 요청수/상태코드/지연시간을 http_request_duration_seconds_* 로 노출한다.
# profile_image_* 커스텀 메트릭과 같은 registry를 사용하므로 /metrics 에 함께 나온다.
Instrumentator().instrument(app).expose(app)

# =========================================================
# Prometheus 메트릭 
# =========================================================
# AI 이미지 변환(/photos/ai/{object_key}) 처리 흐름을 계측한다. Prometheus가 /metrics 를 scrape 한다.
PROFILE_IMAGE_REQUESTS = Counter(
    "profile_image_requests_total", "AI 이미지 변환 요청 수"
)
PROFILE_IMAGE_SUCCESS = Counter(
    "profile_image_success_total", "AI 이미지 변환 성공 수"
)
PROFILE_IMAGE_FAILED = Counter(
    "profile_image_failed_total", "AI 이미지 변환 실패 수(429 거부 포함)"
)
PROFILE_IMAGE_PROCESSING_SECONDS = Histogram(
    "profile_image_processing_seconds",
    "AI 이미지 변환 소요 시간(초)",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),  # AI 변환은 길어서 버킷 확장. _bucket → P95
)
PROFILE_IMAGE_ACTIVE_JOBS = Gauge(
    "profile_image_active_jobs", "현재 변환 처리 중인 작업 수(세마포어 점유)"
)
PROFILE_IMAGE_QUEUE_DEPTH = Gauge(
    "profile_image_queue_depth", "세마포어 획득 대기 중인 변환 작업 수"
)

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
    (단순 S3 업로드. profile_image_* 메트릭은 AI 변환 엔드포인트에서 계측한다.)
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

# pipe = None
DUMMY_MODEL = None
@app.on_event("startup")
async def load_model():
    # global pipe
    global DUMMY_MODEL
    print("AI 모델 로딩 중...")
    # pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
    #     "nitrosocke/Ghibli-Diffusion"
    # )
    # pipe.to("cuda")
    DUMMY_MODEL = bytearray(1536 * 1024 * 1024)  # 실제 모델이 없으므로 메모리 점유 시뮬레이션용 더미 데이터 1.5GB 
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

    # 예시용 딜레이 (AI 변환 처리 시뮬레이션)
    await asyncio.sleep(3)

    print(f"converted_{object_key}: AI 이미지 변환 완료 (mock)")

    # 실제 AI 모델이 없으므로 가짜(mock) 결과를 하드코딩해 반환한다.
    # (FastAPI가 JSON으로 직렬화하므로 dict/str 등 직렬화 가능한 값이어야 한다.)
    return {
        "converted_object_key": f"converted_{object_key}",
        "status": "done",
        "mock": True,
    }

# 변환 API
@app.get("/photos/ai/{object_key}")
async def convert_employee_image(object_key: str):

    # 메트릭: 변환 요청 수
    PROFILE_IMAGE_REQUESTS.inc()

    # 동시 처리 한도가 꽉 차면 즉시 429 (실패로 집계)
    if semaphore.locked() == 0:
        PROFILE_IMAGE_FAILED.inc()
        raise HTTPException(
            status_code=429,
            detail="서버가 바쁩니다. 잠시 후 다시 시도해주세요."
        )

    # 세마포어 대기열 진입(queue_depth +1). 획득 전 취소돼도 finally에서 보정.
    PROFILE_IMAGE_QUEUE_DEPTH.inc()
    acquired = False
    start = None
    try:
        await semaphore.acquire()
        acquired = True
        PROFILE_IMAGE_QUEUE_DEPTH.dec()      # 대기 종료
        PROFILE_IMAGE_ACTIVE_JOBS.inc()      # 처리 시작
        start = time.perf_counter()

        print(f"AI 이미지 변환 요청 : {object_key}")

        # AI 변환 수행
        result = await run_ai_model(object_key)

        PROFILE_IMAGE_SUCCESS.inc()
        return {
            "success": True,
            "message": "AI image converted successfully",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        PROFILE_IMAGE_FAILED.inc()
        raise HTTPException(
            status_code=500,
            detail=f"AI conversion failed: {str(e)}"
        )

    finally:
        if acquired:
            PROFILE_IMAGE_ACTIVE_JOBS.dec()
            if start is not None:
                PROFILE_IMAGE_PROCESSING_SECONDS.observe(time.perf_counter() - start)
            semaphore.release()
        else:
            # 세마포어 미획득(대기 중 취소 등) → 대기열 카운트 보정
            PROFILE_IMAGE_QUEUE_DEPTH.dec()




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


