# Action Gate

A voice approval gate. GPT-Live-1 holds the conversation. Before any action is treated as done, Jev on OpenRouter scores whether it is risky and irreversible. Python then allows it, asks a person, or blocks it.

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Put `OPENAI_API_KEY` and `OPENROUTER_API_KEY` in `backend/.env`.

```powershell
cd frontend
npm install
```

## Run

In one terminal:

```powershell
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

In another:

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173, start the call, and say one of the four lines on the screen.
