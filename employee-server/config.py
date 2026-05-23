import os

PHOTOS_BUCKET     = os.environ.get('PHOTOS_BUCKET', 'my-default-photos-bucket')
PHOTO_SERVICE_URL = os.environ.get('PHOTO_SERVICE_URL', 'http://photo-service:5003')

JWT_SECRET_KEY    = os.environ['JWT_SECRET_KEY']

DATABASE_HOST     = os.environ.get('DATABASE_HOST', 'mysql')
DATABASE_USER     = os.environ['DATABASE_USER']
DATABASE_PASSWORD = os.environ['DATABASE_PASSWORD']
DATABASE_DB_NAME  = os.environ.get('DATABASE_DB_NAME', 'employees')
