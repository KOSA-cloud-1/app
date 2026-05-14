CREATE DATABASE IF NOT EXISTS employees;
use employees

CREATE TABLE IF NOT EXISTS employee (
  id int not null auto_increment primary key,
  object_key nvarchar(80),
  full_name nvarchar(200) not null,
  location nvarchar(200) not null,
  job_title nvarchar(200) not null,
  badges nvarchar(200) not null,
  created_datetime DATETIME DEFAULT now(),
  storage_type NVARCHAR(50) DEFAULT 'ceph' NULL COMMENT 'ceph/aws',
  backup_status TINYINT(1) DEFAULT 0 COMMENT 'backup 여부',
  upload_time DATETIME NULL COMMENT '업로드 시간',
  last_access_time DATETIME DEFAULT now() COMMENT '마지막 접근'
);
