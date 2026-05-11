import os # 운영체제 기능(파일 경로 등)을 위한 모듈
import jwt # JWT(JSON Web Token) 처리를 위한 라이브러리 (PyJWT)
import time # 시간 측정을 위한 모듈
from typing import List, Optional # 타입 힌트를 위한 모듈
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status # FastAPI 프레임워크 관련 모듈
from fastapi.middleware.cors import CORSMiddleware # CORS(교차 출처 리소스 공유) 미들웨어
from fastapi.responses import JSONResponse # JSON 응답을 위한 모듈
from fastapi.routing import APIRoute # API 라우팅을 위한 모듈
from fastapi.staticfiles import StaticFiles # 정적 파일 제공을 위한 모듈
from pydantic import BaseModel # 데이터 유효성 검사를 위한 Pydantic 모델
from fastapi.security import OAuth2PasswordBearer # OAuth2 Bearer 토큰 인증을 위한 모듈
from datetime import datetime
import httpx # 비동기 HTTP 요청을 위한 라이브러리

import config # 애플리케이션 설정
import util # 유틸리티 함수
import database # 데이터베이스 관련 함수
from models import Employee, EmployeePublic, EmployeesListResponse # 데이터 모델 정의

# Need a Pydantic model for receiving form data for create/update
# Employee model is already a Pydantic model, so we don't need a separate one for JSON
# For form data, we use individual Form(...) dependencies

# Override default JSON encoder for FastAPI if needed later, e.g., for datetime
# from datetime import datetime
# app.json_encoders = {datetime: lambda dt: dt.isoformat()}


app = FastAPI() # FastAPI 애플리케이션 인스턴스 생성

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용
    allow_credentials=True, # 자격 증명(쿠키, HTTP 인증 등) 허용
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

# JWT 인증 의존성 설정
# 이 SECRET_KEY는 auth_server의 키와 일치해야 합니다.
SECRET_KEY = config.JWT_SECRET_KEY
ALGORITHM = "HS256" # JWT 서명 알고리즘

# OAuth2PasswordBearer는 주로 Swagger UI/OpenAPI 스펙에 사용되지만, 토큰 추출에도 사용될 수 있습니다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # tokenUrl은 Swagger UI용이며, 실제 토큰은 Authorization 헤더에서 가져옵니다.

# httpx 클라이언트 초기화
client = httpx.AsyncClient()

@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # 자격 증명 예외 정의
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # oauth2_scheme는 "Bearer TOKEN"을 추출하므로, token 변수는 이미 원시 토큰입니다.
    
    try:
        # JWT 토큰 디코딩 및 유효성 검사
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("user") # 페이로드에서 사용자 이름 추출
        if username is None:
            raise credentials_exception # 사용자 이름이 없으면 예외 발생
        # 단순화를 위해 사용자 이름만 반환합니다.
        # 실제 앱에서는 DB에서 사용자 세부 정보를 가져올 수 있습니다.
        return username
    except jwt.ExpiredSignatureError: # 토큰 만료 예외 처리
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError: # 기타 JWT 오류 처리
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# FastAPI는 마운트되지 않는 한 url_for를 직접 사용하지 않습니다.
# 대신 수동으로 URL을 구성하거나 프론트엔드가 직접 경로를 알도록 합니다.
# Flask의 url_for와의 일관성을 위해 이를 에뮬레이트하려고 합니다.
def get_photo_url_for_fastapi(object_key: str):
    # 게이트웨이가 프록시할 수 있는 상대 URL 반환
    return f"/uploads/{object_key}"


@app.on_event("startup")
async def on_startup():
    """앱 시작 시 데이터베이스 테이블이 생성되도록 합니다."""
    database.create_db_and_tables()

@app.get("/employees", response_model=EmployeesListResponse)
async def get_employees(current_user: str = Depends(get_current_user)):
    """모든 직원의 목록을 JSON 배열로 반환합니다."""
    start_time = time.time() # 시간 측정 시작

    employees: List[Employee] = database.list_employees() # 데이터베이스에서 직원 목록 로드
    
    employees_public_data = []
    for employee in employees:
        emp_public = EmployeePublic.from_orm(employee) # SQLModel을 EmployeePublic으로 변환
        if employee.object_key: # 사진 키가 있으면 사진 URL 설정
            emp_public.photo_url = get_photo_url_for_fastapi(employee.object_key)
        employees_public_data.append(emp_public)
    
    end_time = time.time() # 시간 측정 종료
    execution_time = (end_time - start_time) * 1000 # 밀리초 단위 실행 시간
    print(f"Employee Server: get_employees executed in {execution_time:.2f} ms") # 실행 시간 로깅

    return employees_public_data # 목록 직접 반환

@app.get("/employee/{employee_id}", response_model=EmployeePublic, responses={404: {"description": "Employee not found"}})
async def get_employee(employee_id: int, current_user: str = Depends(get_current_user)):
    """단일 직원의 데이터를 JSON으로 반환합니다."""
    employee: Optional[Employee] = database.load_employee(employee_id) # 직원 ID로 직원 로드
    if employee:
        emp_public = EmployeePublic.from_orm(employee) # SQLModel을 EmployeePublic으로 변환
        if employee.object_key: # 사진 키가 있으면 사진 URL 설정
            emp_public.photo_url = get_photo_url_for_fastapi(employee.object_key)
        return emp_public
    raise HTTPException(status_code=404, detail="Employee not found") # 직원을 찾을 수 없으면 404 반환

@app.post("/employee", response_model=Employee, responses={400: {"detail": "Missing required fields"}, 500: {"detail": "Could not save image"}})
async def save_employee(
    full_name: str = Form(...), # 직원 전체 이름 (필수)
    location: str = Form(...), # 직원 위치 (필수)
    job_title: str = Form(...), # 직원 직책 (필수)
    badges: str = Form(""), # 직원 배지 (선택 사항, 기본값 빈 문자열)
    employee_id: Optional[int] = Form(None), # 직원 ID (선택 사항, 새 직원의 경우 None)
    photo: Optional[UploadFile] = File(None), # 직원 사진 파일 (선택 사항)
    current_user: str = Depends(get_current_user) # 현재 인증된 사용자
):
    """직원을 생성하거나 업데이트합니다. multipart/form-data를 처리합니다."""
    # FastAPI는 Form(...)을 통해 필수 필드에 대한 유효성 검사를 처리합니다.

    key = None
    if photo and photo.filename != '': # 사진 파일이 제공되면
        # util.resize_image를 위해 파일과 유사한 객체를 직접 읽습니다.
        image_bytes = util.resize_image(photo.file, (120, 160)) # 이미지 크기 조정
        if image_bytes:
            try:
                # 사진 서비스로 파일 업로드
                files = {'file': (photo.filename, image_bytes, photo.content_type)}
                response = await client.post(f"{config.PHOTO_SERVICE_URL}/upload", files=files)
                response.raise_for_status() # HTTP 오류 발생 시 예외 발생
                upload_result = response.json()
                key = upload_result.get("object_key") # 사진 서비스에서 반환된 object_key 저장
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Photo service unavailable: {e}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Could not upload image to photo service: {e}")

    employee_data = Employee(
        id=employee_id, # employee_id는 선택 사항이며 새 직원의 경우 None입니다.
        object_key=key, # 사진 파일 이름 (객체 키)
        full_name=full_name,
        location=location,
        job_title=job_title,
        badges=badges,
        storage_type="ceph",   # 기본값 (원하면 aws로 변경)
        backup_status=0,
        upload_time=datetime.now() if key else None,
        last_access_time=datetime.now()        
    )

    if employee_id: # 기존 직원 업데이트
        # 새 사진이 업로드되면 이전 사진을 삭제합니다.
        if key:
            old_employee: Optional[Employee] = database.load_employee(employee_id) # 이전 직원 정보 로드
            if old_employee and old_employee.object_key: # 이전 사진이 있으면
                try:
                    # 사진 서비스에 이전 사진 삭제 요청
                    await client.delete(f"{config.PHOTO_SERVICE_URL}/photos/{old_employee.object_key}")
                except httpx.RequestError as e:
                    print(f"Error deleting old photo from photo service: {e}") # 오류 로깅 (계속 진행)
                except Exception as e:
                    print(f"Error deleting old photo from photo service: {e}") # 오류 로깅 (계속 진행)
        
        updated_employee = database.update_employee(employee_id, employee_data) # 직원 정보 업데이트
        if updated_employee:
            return updated_employee # FastAPI는 모델을 자동으로 JSON으로 변환합니다.
        raise HTTPException(status_code=404, detail="Employee not found for update") # 업데이트할 직원을 찾을 수 없으면 404 반환
    
    else: # 새 직원 생성
        new_employee = database.add_employee(employee_data) # 새 직원 추가
        return new_employee # FastAPI는 모델을 자동으로 JSON으로 변환합니다.

@app.delete("/employee/{employee_id}", responses={404: {"description": "Employee not found"}, 200: {"description": "Employee deleted"}})
async def delete_employee_route(employee_id: int, current_user: str = Depends(get_current_user)):
    """직원과 해당 사진을 삭제합니다."""
    employee: Optional[Employee] = database.load_employee(employee_id) # 직원 ID로 직원 로드
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found") # 직원을 찾을 수 없으면 404 반환

    # 사진 파일이 있으면 사진 서비스에서 삭제
    if employee.object_key:
        try:
            await client.delete(f"{config.PHOTO_SERVICE_URL}/photos/{employee.object_key}")
        except httpx.RequestError as e:
            print(f"Error deleting photo from photo service: {e}") # 오류 로깅 (계속 진행)
        except Exception as e:
            print(f"Error deleting photo from photo service: {e}") # 오류 로깅 (계속 진행)

    database.delete_employee(employee_id) # 데이터베이스에서 직원 삭제
    return JSONResponse(status_code=status.HTTP_200_OK, content={"success": True, "message": f"Employee {employee_id} deleted."}) # 성공 응답 반환

# The if __name__ == "__main__": block is removed as Uvicorn will run the app directly.
# Example command to run with Uvicorn: uvicorn application:app --host 0.0.0.0 --port 5002 --reload