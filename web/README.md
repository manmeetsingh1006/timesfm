# TimesFM Web Prototype

Run locally:

```bash
cd web
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to `http://127.0.0.1:8000`.
The app expects the FastAPI backend at `http://127.0.0.1:8000` (see `server/app.py`).
