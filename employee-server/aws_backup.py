import os
import logging
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlmodel import Session, select
from dotenv import load_dotenv

from database import engine
from models import Employee

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

load_dotenv()

# =========================
# ENV
# =========================
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_BUCKET = os.getenv("AWS_BUCKET")

S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")  # 중요

# =========================
# S3 CLIENT (AWS)
# =========================
aws_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
)

# =========================
# S3 CLIENT (CEPH)
# =========================
ceph_client = boto3.client(
    "s3",
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    endpoint_url=S3_ENDPOINT
)

# =========================
# BUCKET CHECK
# =========================
def check_bucket():
    try:
        aws_client.head_bucket(Bucket=AWS_BUCKET)
        logging.info(f"AWS bucket OK: {AWS_BUCKET}")
    except ClientError as e:
        raise Exception(f"AWS bucket error: {e}")

check_bucket()

# =========================
# MIGRATION LOGIC
# =========================
def migrate_to_s3():
    cutoff = datetime.now() - timedelta(days=7)

    with Session(engine) as session:

        stmt = select(Employee).where(
            Employee.object_key.is_not(None),
            Employee.backup_status == 0,
            Employee.last_access_time < cutoff
        )

        employees = session.exec(stmt).all()

        logging.info(f"[BACKUP] target count = {len(employees)}")

        for emp in employees:
            logging.info(f"DEBUG id={emp.id} type={type(emp.object_key)} value={emp.object_key}")
            key = emp.object_key

            if not key:
                logging.warning(f"[SKIP] id={emp.id}, object_key is None")
                continue

            key = str(key).strip()

            try:
                # =========================
                # 1. CEHP DOWNLOAD
                # =========================
                logging.info(f"[CEPH READ] id={emp.id}")

                obj = ceph_client.get_object(
                    Bucket=S3_BUCKET,
                    Key=key
                )

                data = obj["Body"].read()

                # =========================
                # 2. AWS UPLOAD
                # =========================
                logging.info(f"[AWS UPLOAD] id={emp.id}")

                aws_client.put_object(
                    Bucket=AWS_BUCKET,
                    Key=key,
                    Body=data
                )

                # =========================
                # 3. CEPH DELETE
                # =========================
                logging.info(f"[CEPH DELETE] id={emp.id}")

                ceph_client.delete_object(
                    Bucket=S3_BUCKET,
                    Key=key
                )

                # =========================
                # 4. DB UPDATE
                # =========================
                emp.object_key = f"s3://{AWS_BUCKET}/{key}"
                emp.backup_status = 1
                emp.storage_type = "s3"

                session.add(emp)

                logging.info(f"[SUCCESS] id={emp.id}")

            except Exception as e:
                logging.error(f"[FAIL] id={emp.id}, error={e}")
                continue

        session.commit()
        logging.info("[BACKUP] completed")


# =========================
# JOB
# =========================
def job():
    logging.info("backup job started")
    migrate_to_s3()
    logging.info("backup job finished")


# =========================
# MAIN
# =========================
if __name__ == "__main__":

    MODE = os.getenv("MODE", "dev")

    if MODE == "dev":
        logging.info("DEV MODE - immediate execution")
        job()

    else:
        scheduler = BlockingScheduler()

        scheduler.add_job(job, 'cron', hour=4, minute=0)

        logging.info("PROD MODE - scheduled at 04:00")

        scheduler.start()