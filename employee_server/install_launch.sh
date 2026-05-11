#!/bin/bash -ex
yum -y install python3
pip3 install -r requirements.txt
yum -y install stress
export DATABASE_DB_NAME=employees
cat database_create_tables.sql | \
mysql -h localhost -u root -p
FLASK_APP=application.py /usr/local/bin/flask run --host=0.0.0.0 --port=80

