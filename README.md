# app — AI 프로필 이미지 변환 서비스

사내 임직원의 프로필 이미지를 업로드받아 **AI 스타일 프로필 이미지로 변환**하는 서비스의
애플리케이션 모노레포다. 각 서비스는 컨테이너 이미지로 빌드되어 Kubernetes(GitOps)로 배포된다.

- 배포 매니페스트: [`KOSA-cloud-1/k8s-manifests`](https://github.com/KOSA-cloud-1/k8s-manifests) (ArgoCD 동기화)
- 이미지 레지스트리: Docker Hub `kosa1team/*`

## 레포지토리 구조

```text
app/
├── gateway/              # API 게이트웨이 (서비스 입구 프록시)        :5000
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── auth-server/          # 인증 (JWT 발급/검증, admin 로그인)          :5001
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── employee-server/      # 직원/프로필 CRUD + DB + photo-service 호출  :5002
│   ├── Dockerfile
│   ├── application.py
│   ├── database.py / models.py / config.py / util.py
│   ├── database_create_tables.sql
│   └── requirements.txt
├── photo-service/        # AI 프로필 이미지 변환 (핵심 워크로드)       :5003
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── frontend/             # 프론트엔드 정적 리소스 (HTML/JS/CSS)
│   ├── index.html / app.js / style.css
│   └── no_photo.png
├── nginx/                # frontend 정적 리소스를 서빙하는 nginx        :80
│   ├── Dockerfile        #  (이미지명: frontend, 빌드 컨텍스트 = repo 루트)
│   └── nginx.conf
├── backup/               # DB/스토리지 → S3 백업 (CronJob)
│   ├── Dockerfile
│   └── backup_to_s3.py
└── .github/workflows/
    └── deploy.yml        # CI: 이미지 빌드·push + k8s-manifests overlay 태그 갱신
```

## 서비스 요약

| 디렉터리 | 역할 | 포트 | 이미지 | 비고 |
|---|---|---|---|---|
| `gateway` | 서비스 입구 프록시/라우팅 | 5000 | `kosa1team/gateway` | HPA(min2/max4) |
| `auth-server` | JWT 인증, admin 로그인 | 5001 | `kosa1team/auth-server` | |
| `employee-server` | 직원/프로필 CRUD, DB 연동 | 5002 | `kosa1team/employee-server` | Galera DB·photo-service 호출 |
| `photo-service` | AI 프로필 이미지 변환 | 5003 | `kosa1team/photo-service` | 핵심 워크로드, HPA(메모리 기준) |
| `nginx`(+`frontend`) | 프론트 정적 서빙 | 80 | `kosa1team/frontend` | `nginx/Dockerfile`, 컨텍스트=repo 루트 |
| `backup` | DB/스토리지 S3 백업 | - | `kosa1team/backup` | CronJob |

요청 흐름: **client → ingress → gateway(5000) → auth/employee → employee → photo-service(5003)**,
프론트는 `nginx`(80)가 서빙한다.

## 빌드 / 배포 (GitOps)

이미지 빌드·배포는 [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)이 자동 처리한다.

```text
app repo push
  ├─ dev  push ──▶ 이미지 빌드/push(:<sha>) ──▶ k8s-manifests apps/overlays/dev  의
  │                                              images[].newName/newTag 갱신 → ArgoCD → apps-dev(개발)
  └─ main push ──▶ 이미지 빌드/push(:<sha>) ──▶ k8s-manifests apps/overlays/prod 의
                                                 images[].newName/newTag 갱신 → ArgoCD → apps(운영)
```

- 이미지 레지스트리/계정은 매니페스트에 하드코딩하지 않고, CI가 `DOCKERHUB_USERNAME` 시크릿을
  overlay `images[].newName` 으로 주입한다(태그는 커밋 SHA).
- 필요한 시크릿: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `MANIFEST_REPO_TOKEN`.

## 브랜치 전략 (Git Flow)

| 브랜치 | 용도 |
|---|---|
| `main` | 운영 릴리즈 (prod) |
| `dev` | 통합 (develop) |
| `feature/*` | 기능 개발 — `dev`에서 따서 `dev`로 머지 |
| `release/*` | 릴리즈 준비 — `dev`에서 따서 `main`(+`dev`)으로 머지 |
| `hotfix/*` | 긴급 수정 — `main`에서 따서 `main`(+`dev`)으로 머지 |
