# Deploying to EC2

The same code runs locally and in production — only `.env` values differ. This
guide sets up the backend with **gunicorn + nginx** and serves the built React
frontend as static files.

## 0. Provision
- An EC2 instance (Ubuntu 22.04+), ports 80/443 open.
- A domain (optional but recommended for HTTPS).
- Python 3.12+, Node 20+, nginx installed.

## 1. Get the code + source content
```bash
git clone <this-repo> /opt/creator-ai-assistant
git clone <bodhisattvacharyavatara-rails> /opt/bodhisattvacharyavatara-rails
```
Keep the rails clone updated with `git pull` whenever the source content changes.

## 2. Backend
```bash
cd /opt/creator-ai-assistant/backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env
```
Edit `.env` for production:
```
ENV=production
DJANGO_SECRET_KEY=<long-random-string>
DJANGO_DEBUG=false
ALLOWED_HOSTS=your-domain.com,<ec2-public-dns>
CORS_ALLOWED_ORIGINS=https://your-domain.com
RAILS_REPO_PATH=/opt/bodhisattvacharyavatara-rails
GEMINI_API_KEY=<your-key>
```
Then:
```bash
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --no-input
venv/bin/python manage.py check_content   # sanity-check content access
```

## 3. gunicorn (systemd)
`/etc/systemd/system/creator-ai.service`:
```ini
[Unit]
Description=Creator AI Assistant (gunicorn)
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/creator-ai-assistant/backend
EnvironmentFile=/opt/creator-ai-assistant/backend/.env
ExecStart=/opt/creator-ai-assistant/backend/venv/bin/gunicorn \
    config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now creator-ai
```

## 4. Frontend build
```bash
cd /opt/creator-ai-assistant/frontend
npm ci
echo "VITE_API_BASE_URL=https://your-domain.com" > .env
npm run build           # outputs dist/
```

## 5. nginx
`/etc/nginx/sites-available/creator-ai`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # React SPA
    root /opt/creator-ai-assistant/frontend/dist;
    index index.html;
    location / { try_files $uri /index.html; }

    # API -> gunicorn
    location /api/    { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }
    location /admin/  { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }

    # Generated audio + Django static
    location /media/  { alias /opt/creator-ai-assistant/backend/media/; }
    location /static/ { alias /opt/creator-ai-assistant/backend/staticfiles/; }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/creator-ai /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 6. HTTPS
```bash
sudo certbot --nginx -d your-domain.com
```
With HTTPS on, `SECURE_PROXY_SSL_HEADER` (already set when `ENV=production`) lets
Django trust nginx's `X-Forwarded-Proto`.

## Notes / future
- Generated audio is written to `backend/media/audio/` and served by nginx. For
  scale, move to S3 + a storage backend later.
- Restart the backend (`systemctl restart creator-ai`) after pulling new source
  content to clear the in-memory day cache, or add a cache-bust endpoint.
