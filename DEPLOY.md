# 배포 가이드

## 아키텍처

```
[Vercel] Next.js 프론트엔드
    |
    v (API 호출)
[Railway] FastAPI 백엔드 + FFmpeg
    |
    v (저장)
[Local/S3] 생성된 비디오
```

---

## 로컬 개발 환경

### 1. 백엔드 API 서버 시작
```bash
cd gongmae-video-generator
pip install -r requirements.txt
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### 2. 프론트엔드 개발 서버 시작
```bash
cd web
npm install
cp .env.local.example .env.local
npm run dev
```

### 3. 접속 주소
- 프론트엔드: http://localhost:3000
- 백엔드 API: http://localhost:8000
- API 문서: http://localhost:8000/docs

---

## Railway 배포 (백엔드)

### 방법 1: Railway CLI 사용

```bash
# 1. Railway CLI 설치
npm install -g @railway/cli

# 2. 로그인
railway login

# 3. 프로젝트 초기화 (루트 디렉토리에서)
cd gongmae-video-generator
railway init

# 4. 배포
railway up

# 5. 배포된 URL 확인
railway domain
```

### 방법 2: GitHub 연동 (추천)

1. GitHub에 레포지토리 푸시
2. [Railway 대시보드](https://railway.app) 접속
3. "New Project" > "Deploy from GitHub repo" 선택
4. 레포지토리 연결
5. 자동 배포 완료

### Railway 환경변수 설정

Railway 대시보드 > Variables 탭에서 설정:

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 키 (LLM 사용시) | 선택 |
| `NAVER_CLIENT_ID` | 네이버 TTS API ID | 선택 |
| `NAVER_CLIENT_SECRET` | 네이버 TTS API Secret | 선택 |
| `FRONTEND_URL` | Vercel 배포 URL (CORS용) | 선택 |

---

## Vercel 배포 (프론트엔드)

### 방법 1: Vercel CLI 사용

```bash
# 1. Vercel CLI 설치
npm install -g vercel

# 2. 로그인
vercel login

# 3. web 폴더에서 배포
cd web
vercel

# 4. 프로덕션 배포
vercel --prod
```

### 방법 2: GitHub 연동 (추천)

1. [Vercel 대시보드](https://vercel.com) 접속
2. "Add New" > "Project" 선택
3. GitHub 레포지토리 연결
4. **Root Directory**를 `web`으로 설정
5. "Deploy" 클릭

### Vercel 환경변수 설정

Vercel 대시보드 > Settings > Environment Variables:

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `NEXT_PUBLIC_API_URL` | Railway 백엔드 URL | `https://your-project.railway.app` |

---

## 배포 순서 (처음 배포시)

1. **Railway 먼저 배포** → 백엔드 URL 획득
2. **Vercel 환경변수에 Railway URL 설정**
3. **Vercel 배포**
4. (선택) Railway 환경변수에 Vercel URL 설정 (CORS 강화용)

---

## API 엔드포인트

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|-------------|
| GET | `/` | 헬스 체크 |
| POST | `/api/jobs` | 비디오 생성 작업 생성 |
| GET | `/api/jobs/{id}` | 작업 상태 조회 |
| GET | `/api/jobs` | 모든 작업 목록 |
| DELETE | `/api/jobs/{id}` | 작업 삭제 |
| GET | `/api/videos/{filename}` | 비디오 다운로드 |
| GET | `/api/properties` | 매물 목록 조회 |
| POST | `/api/properties` | 매물 데이터 업로드 |
| GET | `/api/template` | JSON 템플릿 조회 |

---

## 비용 예상

### Railway (백엔드)
- 무료 티어: 월 $5 크레딧
- 비디오 생성: 비디오당 약 30분
- 예상: 무료 티어로 월 ~30개 비디오

### Vercel (프론트엔드)
- 무료 티어: 100GB 대역폭
- Hobby 플랜으로 충분

---

## 문제 해결

### 비디오 생성 실패
1. Railway 로그 확인: `railway logs`
2. FFmpeg 설치 확인 (Dockerfile에 포함)
3. 메모리 사용량 확인 (비디오 처리에 ~1GB 필요)

### CORS 오류
1. `NEXT_PUBLIC_API_URL`이 올바른지 확인
2. Railway URL이 HTTPS 사용중인지 확인
3. `api/server.py`의 CORS 설정 확인
4. Railway에 `FRONTEND_URL` 환경변수 설정

### 느린 비디오 생성
- zoompan 효과로 인해 비디오 생성에 약 30분 소요
- 프로덕션에서는 백그라운드 작업 + 웹훅 사용 권장
