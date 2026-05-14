"중앙 설정"
import os # 운영체제 기능(환경 변수 등)을 위한 모듈

# 사진 버킷 이름 (환경 변수에서 가져오거나 기본값 사용)
PHOTOS_BUCKET = os.environ['PHOTOS_BUCKET'] if 'PHOTOS_BUCKET' in os.environ else 'my-default-photos-bucket'
# 사진 저장 폴더 (로컬 파일 시스템 사용 시)
# PHOTOS_FOLDER = 'photos' # 더 이상 사용되지 않음
# Flask 애플리케이션의 비밀 키
FLASK_SECRET = "something-random"
# JWT 서명에 사용되는 비밀 키
JWT_SECRET_KEY = 'your-super-secret-key-change-it'

# 사진 서비스 URL
PHOTO_SERVICE_URL = os.environ.get('PHOTO_SERVICE_URL', 'http://photo-service:5003')

# 데이터베이스 호스트 (환경 변수에서 가져오거나 기본값 사용)
#DATABASE_HOST = os.environ['DATABASE_HOST'] if 'DATABASE_HOST' in os.environ else None
# 데이터베이스 사용자 (환경 변수에서 가져오거나 기본값 사용)
#DATABASE_USER = os.environ['DATABASE_USER'] if 'DATABASE_USER' in os.environ else None
# 데이터베이스 비밀번호 (환경 변수에서 가져오거나 기본값 사용)
#DATABASE_PASSWORD = os.environ['DATABASE_PASSWORD'] if 'DATABASE_PASSWORD' in os.environ else None
# 데이터베이스 이름 (환경 변수에서 가져오거나 기본값 사용)
#DATABASE_DB_NAME = os.environ['DATABASE_DB_NAME'] if 'DATABASE_DB_NAME' in os.environ else None
DATABASE_HOST = "mysql" # 데이터베이스 호스트
DATABASE_USER = "root" # 데이터베이스 사용자
DATABASE_PASSWORD = "kosa1004" # 데이터베이스 비밀번호
DATABASE_DB_NAME = "employees" # 데이터베이스 이름
