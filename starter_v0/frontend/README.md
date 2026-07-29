# Research Agent Frontend

Vite React UI for the Day 04 Research Agent.

Local development:

```powershell
npm install
npm run dev
```

Set local server-side proxy variables in `frontend/.env`:

```env
BACKEND_ORIGIN=http://127.0.0.1:8000
BACKEND_SHARED_SECRET=replace-with-the-same-secret-as-backend
```

Vercel deployment uses `frontend/api/chat.ts` and `frontend/api/health.ts`.
Configure Vercel environment variables without `VITE_` prefixes:

```env
BACKEND_ORIGIN=https://your-ngrok-domain.ngrok-free.app
BACKEND_SHARED_SECRET=replace-with-the-same-secret-as-backend
```

