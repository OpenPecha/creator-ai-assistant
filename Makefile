.PHONY: dev backend frontend install stop

# Backend port must match frontend/.env (VITE_API_BASE_URL=http://localhost:8000).
dev:
	@echo "Starting backend on :8000 and frontend on :5173 ..."
	@trap 'kill %1 %2 2>/dev/null' INT; \
	(cd backend && venv/bin/python manage.py runserver 0.0.0.0:8000 2>&1) & \
	(cd frontend && npm run dev 2>&1) & \
	wait

backend:
	cd backend && venv/bin/python manage.py runserver 0.0.0.0:8000

frontend:
	cd frontend && npm run dev

# Stop whatever is listening on the dev ports (backend 8000, frontend 5173).
stop:
	@echo "Stopping dev servers on :8000 and :5173 ..."
	@lsof -ti:8000 | xargs kill 2>/dev/null || true
	@lsof -ti:5173 | xargs kill 2>/dev/null || true
	@echo "Done."

install:
	cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
	cd frontend && npm install
