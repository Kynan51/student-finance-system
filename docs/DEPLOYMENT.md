# Deployment guide (Phase 12)

This guide deploys to an Ubuntu server (e.g. AWS EC2 free tier or any VPS) with MySQL, Gunicorn, Nginx and a free Let's Encrypt HTTPS certificate. HTTPS is required for the PWA to be installable.

## 1. Production environment variables (`.env` on the server)

```ini
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_ALLOWED_HOSTS=yourdomain.co.ke,www.yourdomain.co.ke
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.co.ke,https://www.yourdomain.co.ke

DB_ENGINE=mysql
DB_NAME=student_finance
DB_USER=student_finance_user
DB_PASSWORD=<strong password>
DB_HOST=127.0.0.1
DB_PORT=3306

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_HOST_USER=<user>
EMAIL_HOST_PASSWORD=<app password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Student Finance <no-reply@yourdomain.co.ke>
```

With `DJANGO_DEBUG=False` the settings automatically enable: HTTPS redirect, secure session and CSRF cookies, HSTS (1 year), the proxy SSL header and WhiteNoise with hashed, compressed static files. The app refuses to start without a secret key.

Never commit `.env` (it is in `.gitignore`).

## 2. Server setup

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip mysql-server nginx certbot python3-certbot-nginx git
sudo mysql < scripts/create_mysql_db.sql        # edit the password first

git clone <your-repo-url> /srv/student-finance && cd /srv/student-finance
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
nano .env                                       # paste the values above
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py check --deploy
```

Do **not** run `seed_demo` on a production server unless you want a public demo account.

## 3. Gunicorn service

`/etc/systemd/system/student-finance.service`:

```ini
[Unit]
Description=Student Finance (Gunicorn)
After=network.target mysql.service

[Service]
User=www-data
WorkingDirectory=/srv/student-finance
EnvironmentFile=/srv/student-finance/.env
ExecStart=/srv/student-finance/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 3 --timeout 60
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R www-data:www-data /srv/student-finance
sudo systemctl daemon-reload && sudo systemctl enable --now student-finance
```

## 4. Nginx and HTTPS

`/etc/nginx/sites-available/student-finance`:

```nginx
server {
    listen 80;
    server_name yourdomain.co.ke www.yourdomain.co.ke;
    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/student-finance /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d yourdomain.co.ke -d www.yourdomain.co.ke
```

WhiteNoise serves static files through Gunicorn, so Nginx needs no static block.

## 5. Platform-as-a-service alternative (e.g. Render)

* Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
* Start command: `gunicorn config.wsgi:application`
* Add the environment variables from section 1 in the dashboard, using the managed MySQL credentials.

## 6. Backups

```bash
chmod +x scripts/*.sh
scripts/backup_mysql.sh                         # writes backups/student_finance_YYYYmmdd_HHMM.sql.gz
crontab -e                                      # daily at 02:15:
15 2 * * * /srv/student-finance/scripts/backup_mysql.sh >> /srv/student-finance/backups/backup.log 2>&1
```

* Keeps the 14 most recent backups; files are `chmod 600`.
* Copy backups off the server (e.g. to encrypted cloud storage) regularly.
* **Test restoration** on a copy of the database at least once: `scripts/restore_mysql.sh backups/<file>.sql.gz`.

## 7. Updating the app

```bash
cd /srv/student-finance && git pull
source .venv/bin/activate && pip install -r requirements.txt
python manage.py migrate && python manage.py collectstatic --noinput
sudo systemctl restart student-finance
```

When CSS/JS change, bump `PWA_CACHE_VERSION` in `core/views.py` so installed apps refresh their cached app shell.

## 8. Go-live checklist

- [ ] `DJANGO_DEBUG=False` and a unique `DJANGO_SECRET_KEY`
- [ ] `python manage.py check --deploy` shows no errors
- [ ] HTTPS certificate active; HTTP redirects to HTTPS
- [ ] Database user has access to `student_finance` only
- [ ] SMTP email works (try a password reset)
- [ ] Daily backups scheduled and one restore tested
- [ ] PWA installs on Android Chrome and iPhone Safari; offline page appears in airplane mode
- [ ] Logging out and pressing Back does not show private pages (no-store headers)
- [ ] Consent wording reviewed for real participants (Kenya Data Protection Act)
- [ ] Optional: set `SECURE_HSTS_PRELOAD = True` only after confirming every subdomain serves HTTPS
