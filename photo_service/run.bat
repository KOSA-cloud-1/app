cd C:\project\awsTechnicalEssentails\FlaskApp\MSA_Project\photo_service
call .venv\Scripts\activate.bat
uvicorn app:app --host 0.0.0.0 --port 5003 --reload