# Deployment Checklist

## Local Backend

1. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

2. Create `.env` from `.env.example` and fill secrets locally.

3. Run preflight:

```powershell
python scripts/preflight_provider.py --provider gemini
python scripts/preflight_tools.py --smoke --include-arxiv --timeout 20
```

4. Start FastAPI:

```powershell
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

5. Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

6. Start ngrok:

```powershell
ngrok config add-authtoken <REAL_TOKEN>
ngrok http 8000
```

7. Copy the `https://...ngrok-free.app` forwarding URL. Do not commit it.

## Vercel

1. Import repository into Vercel.
2. Set Root Directory to `frontend`.
3. Use Vite framework preset.
4. Add environment variables:
   - `BACKEND_ORIGIN=https://your-ngrok-domain.ngrok-free.app`
   - `BACKEND_SHARED_SECRET=replace-with-the-same-secret-as-backend`
5. Deploy.
6. Test `https://your-app.vercel.app/api/health`.
7. Open the UI and send a chat prompt.

## Manual Notes

- The personal machine must stay on, not sleeping, with internet access.
- `uvicorn` and `ngrok` must both be running for Vercel chat to work.
- Replace `TODO_VERCEL_URL` in `artifacts/REPORT.md` after deployment.
- Replace `TODO_TEAM_NAME`, `TODO_MEMBERS`, and `TODO_TEAM_AUTHOR` with real team info before submission.

