REM 현재 디렉토리를 employee_server로 변경
cd C:\project\awsTechnicalEssentails\FlaskApp\MSA_Project\employee_server
REM 가상 환경 활성화
call .venv\Scripts\activate.bat
REM Uvicorn을 사용하여 FastAPI 애플리케이션 실행
uvicorn application:app --host 0.0.0.0 --port 5002 --reload