apiVersion: v1
kind: Secret
metadata:
  name: mariadb-secret
type: Opaque
data:
  MYSQL_ROOT_PASSWORD: a29zYTEwMDQ=    # kosa1004 (base64)
  MYSQL_DATABASE: ZW1wbG95ZWVz         # employees (base64)

---

apiVersion: v1
kind: Secret
metadata:
  name: ceph-secret
type: Opaque
data:
  S3_ENDPOINT: aHR0cDovLzEwLjEwLjEwLjExOjc0ODA=   # http://10.10.10.11:7480

  S3_ACCESS_KEY: QUdWT1JUVldUSFc2V0FXVVlFVVE=     
  S3_SECRET_KEY: a3QwY1l4bkJLbU1FRWxjZXRVQ0o4TmFaUFdEZUF6M201UXFBenhyQg==

  #AWS_ACCESS_KEY_ID: QUdWT1JUVldUSFc2V0FXVVlFVVE=     
  #AWS_SECRET_ACCESS_KEY: a3QwY1l4bkJLbU1FRWxjZXRVQ0o4TmFaUFdEZUF6M201UXFBenhyQg==

  S3_BUCKET: bXlidWNrZXQ=                          # mybucket
