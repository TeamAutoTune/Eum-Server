# FastAPI Backend (Eum Server)

## Location

This backend has been moved to the sibling folder:

`../eum-server`

## Quick Start

```bash
cd eum-server
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment

Create `.env` from `.env.example` inside `eum-server`.

## API Groups

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/auth/me`

- `POST /api/chat/rooms/direct`
- `GET /api/chat/rooms`
- `GET /api/chat/rooms/{room_id}/messages`
- `POST /api/chat/rooms/{room_id}/messages`

- `GET /api/home/reviews`
- `GET /api/home/promotions`
- `POST /api/home/reviews` (dev)
- `POST /api/home/promotions` (dev)
