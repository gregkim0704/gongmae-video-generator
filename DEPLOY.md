# Deployment Guide

## Architecture

```
[Vercel] Next.js Frontend
    |
    v (API calls)
[Railway] FastAPI Backend + FFmpeg
    |
    v (stores)
[Local/S3] Generated Videos
```

## Local Development

### 1. Start Backend API Server
```bash
cd gongmae-video-generator
pip install -r requirements.txt
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start Frontend Dev Server
```bash
cd web
npm install
npm run dev
```

### 3. Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Railway Deployment (Backend)

### 1. Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

### 2. Create New Project
```bash
cd gongmae-video-generator
railway init
```

### 3. Deploy
```bash
railway up
```

### 4. Get Public URL
```bash
railway open
```

### 5. Environment Variables (Railway Dashboard)
- `ANTHROPIC_API_KEY` - For production LLM calls
- `NAVER_CLIENT_ID` - For production TTS (optional)
- `NAVER_CLIENT_SECRET` - For production TTS (optional)

---

## Vercel Deployment (Frontend)

### 1. Install Vercel CLI
```bash
npm install -g vercel
vercel login
```

### 2. Deploy Frontend
```bash
cd web
vercel
```

### 3. Set Environment Variables (Vercel Dashboard)
- `NEXT_PUBLIC_API_URL` - Railway backend URL (e.g., https://your-app.railway.app)

### 4. Production Deploy
```bash
vercel --prod
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/api/jobs` | Create video generation job |
| GET | `/api/jobs/{id}` | Get job status |
| GET | `/api/jobs` | List all jobs |
| DELETE | `/api/jobs/{id}` | Delete a job |
| GET | `/api/videos/{filename}` | Download video |
| GET | `/api/properties` | List properties |
| POST | `/api/properties` | Upload property data |
| GET | `/api/template` | Get JSON template |

---

## Costs Estimate

### Railway (Backend)
- Free tier: 500 hours/month
- Video generation: ~30 min per video
- Estimated: ~1000 videos/month on free tier

### Vercel (Frontend)
- Free tier: 100GB bandwidth
- Hobby plan should be sufficient

---

## Troubleshooting

### Video generation fails
1. Check Railway logs: `railway logs`
2. Verify FFmpeg is installed in container
3. Check memory usage (video processing needs ~1GB)

### CORS errors
1. Verify `NEXT_PUBLIC_API_URL` is correct
2. Check Railway URL is using HTTPS
3. Verify CORS settings in `api/server.py`

### Slow video generation
- Video generation takes ~30 minutes due to zoompan effects
- Consider using background jobs with webhooks for production
