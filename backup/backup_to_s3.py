"""
Ceph → AWS S3 사진 백업 스크립트

동작 순서:
1. DB에서 backup_status=0 인 직원 목록 조회
2. Ceph에서 사진 다운로드
3. AWS S3에 업로드
4. DB backup_status=1 업데이트
"""

import os
import boto3
import mysql.connector
from botocore.exceptions import ClientError

# ── 환경변수에서 설정 읽기 (K8s Secret으로 주입됨) ───────────────

# Ceph 설정 (기존 ceph-secret에서 가져옴)
CEPH_ENDPOINT   = os.environ["S3_ENDPOINT"]
CEPH_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
CEPH_SECRET_KEY = os.environ["S3_SECRET_KEY"]
CEPH_BUCKET     = os.environ.get("S3_BUCKET", "mybucket")

# AWS S3 설정 (새로 추가할 aws-secret에서 가져옴)
AWS_ACCESS_KEY  = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_KEY  = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_BUCKET      = os.environ["AWS_S3_BUCKET"]
AWS_REGION      = os.environ.get("AWS_REGION", "ap-northeast-2")

# DB 설정 (기존 mariadb-secret에서 가져옴)
DB_HOST     = os.environ.get("DATABASE_HOST", "mysql")
DB_USER     = os.environ.get("DATABASE_USER", "root")
DB_PASSWORD = os.environ["MYSQL_ROOT_PASSWORD"]
DB_NAME     = os.environ.get("DATABASE_DB_NAME", "employees")

# ── 클라이언트 생성 ──────────────────────────────────────────────

print("=== Ceph → AWS S3 백업 시작 ===")

ceph_client = boto3.client(
    "s3",
    endpoint_url=CEPH_ENDPOINT,
    aws_access_key_id=CEPH_ACCESS_KEY,
    aws_secret_access_key=CEPH_SECRET_KEY,
)

aws_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
)

# ── AWS S3 버킷 자동 생성 ────────────────────────────────────────

try:
    aws_client.head_bucket(Bucket=AWS_BUCKET)
    print(f"AWS 버킷 '{AWS_BUCKET}' 확인 완료")
except ClientError as e:
    code = e.response["Error"]["Code"]
    if code == "404":
        print(f"AWS 버킷 '{AWS_BUCKET}' 생성 중...")
        if AWS_REGION == "us-east-1":
            aws_client.create_bucket(Bucket=AWS_BUCKET)
        else:
            aws_client.create_bucket(
                Bucket=AWS_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION}
            )
        print(f"AWS 버킷 '{AWS_BUCKET}' 생성 완료")
    else:
        raise

# ── DB 연결 ──────────────────────────────────────────────────────

conn = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)
cursor = conn.cursor()

# ── 백업 대상 조회: backup_status=0 이고 사진이 있는 직원 ────────

cursor.execute("""
    SELECT id, full_name, object_key
    FROM employee
    WHERE backup_status = 0
      AND object_key IS NOT NULL
      AND object_key != ''
""")
targets = cursor.fetchall()

print(f"백업 대상: {len(targets)}명")

if len(targets) == 0:
    print("백업할 사진이 없습니다.")
    cursor.close()
    conn.close()
    exit(0)

# ── 각 사진 백업 ─────────────────────────────────────────────────

success = 0
fail    = 0

for emp_id, full_name, object_key in targets:
    try:
        # 1. Ceph에서 사진 다운로드
        response = ceph_client.get_object(Bucket=CEPH_BUCKET, Key=object_key)
        photo_data = response["Body"].read()
        content_type = response.get("ContentType", "image/jpeg")

        # 2. AWS S3에 업로드 (같은 object_key 사용)
        aws_client.put_object(
            Bucket=AWS_BUCKET,
            Key=object_key,
            Body=photo_data,
            ContentType=content_type,
        )

        # 3. DB 업데이트: 백업 완료
        cursor.execute("""
            UPDATE employee
            SET backup_status = 1
            WHERE id = %s
        """, (emp_id,))
        conn.commit()

        print(f"  ✅ [{emp_id}] {full_name} → {object_key}")
        success += 1

    except ClientError as e:
        print(f"  ❌ [{emp_id}] {full_name} 실패 (S3 오류): {e}")
        fail += 1
    except Exception as e:
        print(f"  ❌ [{emp_id}] {full_name} 실패: {e}")
        fail += 1

# ── 최종 결과 ────────────────────────────────────────────────────

cursor.close()
conn.close()

print("")
print("=== 백업 완료 ===")
print(f"성공: {success}명 / 실패: {fail}명 / 전체: {len(targets)}명")
