import time # 시간 측정을 위한 모듈
from fastapi import FastAPI, Request, Response, HTTPException # FastAPI 프레임워크 관련 모듈
from fastapi.middleware.cors import CORSMiddleware # CORS(교차 출처 리소스 공유) 미들웨어
import httpx # 비동기 HTTP 요청을 위한 라이브러리 (FastAPI의 비동기 특성과 호환)

app = FastAPI() # FastAPI 애플리케이션 인스턴스 생성

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용
    allow_credentials=True, # 자격 증명(쿠키, HTTP 인증 등) 허용
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

# 다운스트림 서비스(인증 서버, 직원 서버)의 URL 정의
AUTH_SERVER_URL = "http://auth-server:5001"
EMPLOYEE_SERVER_URL = "http://employee-server:5002"
PHOTO_SERVICE_URL = "http://photo-service:5003" # 사진 서비스 URL

# 비동기 요청을 위한 httpx 클라이언트 초기화
# 연결 풀링을 위해 전역 클라이언트 사용
client = httpx.AsyncClient()

@app.on_event("shutdown")
async def shutdown_event():
    # 애플리케이션 종료 시 httpx 클라이언트 연결 닫기
    await client.aclose()

# 직원 사진 요청을 위한 프록시
@app.api_route("/static/uploads/{filename:path}", methods=["GET"])
async def proxy_employee_photo_requests(filename: str, request: Request):
    """직원 사진 요청을 직원 서버로 프록시합니다."""
    url = f"{PHOTO_SERVICE_URL}/photos/{filename}" # 사진 서비스의 사진 URL 구성

    print(f"Gateway: proxy_employee_photo_requests") # 로깅
    
    # 호스트 및 Content-Length를 제외한 헤더 재구성 (httpx가 Content-Length 처리)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ["host", "content-length"]}

    try:
        # 직원 서버로 요청 전달
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            params=request.query_params,
            follow_redirects=False
        )
        
        # Content-Encoding, Content-Length, Transfer-Encoding, Connection을 제외한 응답 헤더 재구성
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        
        # 직원 서버의 응답 반환
        return Response(content=resp.content, status_code=resp.status_code, headers=response_headers)
    except httpx.RequestError as e:
        # 서비스 사용 불가 시 예외 발생
        raise HTTPException(status_code=503, detail=f"Employee photo service unavailable: {str(e)}")

# auth_server로 요청 프록시
@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_auth_requests(path: str, request: Request):
    """인증 서버로 요청을 프록시합니다."""
    url = f"{AUTH_SERVER_URL}/{path}" # 인증 서버의 URL 구성
    
    # 호스트 및 Content-Length를 제외한 헤더 재구성 (httpx가 Content-Length 처리)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ["host", "content-length"]}
    
    try:
        # 전달을 위해 요청 본문을 바이트로 읽기
        body = await request.body()
        
        # 인증 서버로 요청 전달
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body, # 바이트 본문에 content 사용
            params=request.query_params,
            follow_redirects=False
        )
        
        # Content-Encoding, Content-Length, Transfer-Encoding, Connection을 제외한 응답 헤더 재구성
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        
        # 인증 서버의 응답 반환
        return Response(content=resp.content, status_code=resp.status_code, headers=response_headers)
    except httpx.RequestError as e:
        # 서비스 사용 불가 시 예외 발생
        raise HTTPException(status_code=503, detail=f"Auth service unavailable: {str(e)}")

# employee_server로 요청 프록시
@app.api_route("/api/employee/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_employee_requests(path: str, request: Request):
    """직원 서버로 요청을 프록시합니다."""
    url = f"{EMPLOYEE_SERVER_URL}/{path}" # 직원 서버의 URL 구성
    
    # 호스트 및 Content-Length를 제외한 헤더 재구성 (httpx가 Content-Length 처리)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ["host", "content-length"]}

    start_time = time.time() # 프록시 요청 시간 측정 시작

    try:
        # 전달을 위해 요청 본문을 바이트로 읽기
        body = await request.body()
        
        # 직원 서버로 요청 전달
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body, # 바이트 본문에 content 사용
            params=request.query_params,
            follow_redirects=False
        )
        
        end_time = time.time() # 프록시 요청 시간 측정 종료
        execution_time = (end_time - start_time) * 1000 # 밀리초 단위 실행 시간
        print(f"Gateway: Proxy to Employee Server ({path}) executed in {execution_time:.2f} ms") # 실행 시간 로깅

        # Content-Encoding, Content-Length, Transfer-Encoding, Connection을 제외한 응답 헤더 재구성
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        
        # 직원 서버의 응답 반환
        return Response(content=resp.content, status_code=resp.status_code, headers=response_headers)
    except httpx.RequestError as e:
        end_time = time.time() # 오류 발생 시에도 시간 측정 종료
        execution_time = (end_time - start_time) * 1000 # 밀리초 단위 실행 시간
        print(f"Gateway: Proxy to Employee Server ({path}) failed after {execution_time:.2f} ms with error: {e}")
        # 서비스 사용 불가 시 예외 발생
        raise HTTPException(status_code=503, detail=f"Employee service unavailable: {str(e)}")

# The if __name__ == '__main__': block is removed as Uvicorn will run the app directly.
# Example command to run with Uvicorn: uvicorn app:app --host 0.0.0.0 --port 5000 --reload