.PHONY: dev backend frontend install

dev:
	@echo "Starting backend on :8001 and frontend on :5173 ..."
	@trap 'kill %1 %2 2>/dev/null' INT; \
	(cd backend && venv/bin/python manage.py runserver 0.0.0.0:8001 2>&1) & \
	(cd frontend && npm run dev 2>&1) & \
	wait

backend:
	cd backend && venv/bin/python manage.py runserver 0.0.0.0:8001

frontend:
	cd frontend && npm run dev

install:
	cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
	cd frontend && npm install
