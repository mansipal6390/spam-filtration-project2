# Spam Filtration — Analyzer

A small FastAPI app that classifies messages as `spam`, `safe`, or `promotional`.

Features:
- A simple rule-based prefilter for common spam phrases.
- Optional Groq model-based classification if you provide a `GROQ_API_KEY`.
- A minimal frontend served from `index.html`.

Getting started (Windows PowerShell):

```powershell
cd "e:\New folder\spamfilteration"
python -m pip install -r requirements.txt
# Optionally: copy .env.example to .env and set GROQ_API_KEY
# cp .env.example .env  (or create .env manually)
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open the UI at: http://127.0.0.1:8000

Theme toggling:
- The UI supports both light and dark themes. Use the theme button in the top-right header to toggle between light and dark modes.
- The chosen preference is saved in your browser (localStorage) and will persist across reloads.

History & Chart:
- The History panel shows a list of previous analyses and a stacked chart of confidences for recent analyses.
- Use the 'Seed sample' button to add sample history entries for testing the chart and UI.

Notes:
- If you see `Error loading ASGI app: Could not import module 'main'`, ensure you ran uvicorn from the project folder:
  - `cd 'e:\New folder\spamfilteration'` then run uvicorn, or use `--app-dir` to specify the folder.
- If you see port errors like `[WinError 10048]`, kill other python/uvicorn processes that are using the port or switch to a free port:
  - `Get-Process python` and `Stop-Process -Id <PID> -Force` (PowerShell), or change port `--port 8001`.
- If you don't set `GROQ_API_KEY`, the app will use rule-based detection and return a 503 JSON error when the model is needed.

Testing the `/classify` endpoint (example, PowerShell):

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/classify' -Method POST -ContentType 'application/json' -Body '{"text":"Congratulations, you won a free prize! Click here to claim your prize now"}' | ConvertTo-Json -Depth 5
```

If you'd like, I can also add a small `run.ps1` script to start the server or include a troubleshooting script that ensures no port conflicts.
