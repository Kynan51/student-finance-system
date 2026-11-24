# AI-Based Personal Finance & Budget Tracking System

A Django web app (installable as a Progressive Web App) that helps Kenyan university students record irregular income (HELB, parents/guardians, side hustles), track daily spending, plan budgets, set virtual savings goals and get honest, explainable spending forecasts.

**Stack:** Python 3.11+ · Django 5 · MySQL (SQLite for zero-setup testing) · vanilla HTML5/CSS3/JavaScript · Chart.js (charts only) · Pandas · NumPy · Scikit-learn · ReportLab · PWA (manifest + service worker)

No React, Vue, Angular, jQuery, Bootstrap or Tailwind. The frontend is plain, readable, separate HTML, CSS and JS files.

---

## 1. Quick start (about 5 minutes, no database setup)

You need **Python 3.11 or newer** ([python.org/downloads](https://www.python.org/downloads/); on Windows tick **"Add python.exe to PATH"**).

**Windows:** double-click **`run.bat`**.

**macOS / Linux:** open a terminal in this folder and run `bash run.sh`.

The script creates a virtual environment, installs the requirements, creates `.env`, sets up the database, creates a demo account and opens **http://127.0.0.1:8000**.

| Demo login | |
|---|---|
| Username | `demo` |
| Password | `DemoPass2026!` |

The demo account is filled with **synthetic** data (every description starts with `[SYNTHETIC]`). Register your own account to start from empty.

The quick start uses a local SQLite file so it runs immediately. Switch to MySQL (the project's target database) with section 2.

### Manual start (same steps as the scripts)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                 # macOS/Linux: cp .env.example .env
python manage.py migrate
python manage.py seed_demo             # optional demo data
python manage.py createsuperuser       # optional, for /admin/
python manage.py runserver
```

---

## 2. Switching to MySQL

1. Install MySQL Server 8 (or MariaDB 10.6+) and make sure it is running.
2. Create the database and user (edit the password first):
   ```bash
   mysql -u root -p < scripts/create_mysql_db.sql
   ```
3. Edit `.env`:
   ```ini
   DB_ENGINE=mysql
   DB_NAME=student_finance
   DB_USER=student_finance_user
   DB_PASSWORD=the-password-you-chose
   DB_HOST=127.0.0.1
   DB_PORT=3306
   ```
4. Run `python manage.py migrate`, then `python manage.py seed_demo` if you want demo data, then start the server.

The MySQL driver is **PyMySQL** (pure Python, so it installs on Windows without a C compiler). Verified on MariaDB 10.11: all migrations apply and the full test suite passes.

---

## 3. What the app does

| Module | Main capabilities |
|---|---|
| Accounts | Register (with consent), log in/out, password reset by email, profile with semester dates, notification preferences, change password, delete account and all data |
| Income | Add/edit/delete HELB, parents/guardian, side hustle, scholarship and other income; search, date and source filters, pagination |
| Expenses | Same CRUD plus payment method; **paste an M-Pesa SMS** to pre-fill the form; category suggested from the description |
| Categories | Built-in Kenyan student categories with keywords; add your own |
| Budgets | Monthly, semester or custom budgets; category limits; fixed obligations (rent, exam fees); utilisation vs time elapsed; warnings at a configurable threshold |
| Savings goals | Virtual goals with targets, deadlines and priority; set aside / release; corrections by reversal (full audit trail); available balance excludes allocations |
| Dashboard | Available balance, period totals, 6-month income vs expenses, category doughnut, daily spending, budget utilisation, goals, recent activity; weekly / monthly / semester / all-time filters |
| AI insights | Runway, possible shortfall before semester end, 30-day forecast with model comparison, category trends, unusual expenses, budget alerts, non-essential share; each with metrics, assumptions, reliability and date |
| Notifications | De-duplicated in-app budget and insight alerts |
| Reports | Monthly, semester or custom summaries; CSV and PDF export of your own data only |
| PWA | Installable, standalone window, offline page; private data never cached |

### Key definitions (useful for your defence)

* **Cash balance** = total income − total expenses
* **Allocated savings** = net total of savings-goal entries (virtual)
* **Available balance** = cash balance − allocated savings
* Savings allocations are **not** expenses, so they are never double-counted.

---

## 4. The AI engine (Phase 9–10)

Code lives in `ai_engine/engine/` and has no Django imports, so it can be tested on its own.

| File | Purpose |
|---|---|
| `baseline.py` | Average daily spend, recent 14-day rate, burn rate, runway, projected balance |
| `forecasting.py` | Five forecasters (historical mean, recent mean, weekday profile, linear trend, Ridge regression) and a rolling-origin backtest |
| `patterns.py` | Unusual-expense detection (robust z-score using median/MAD) and category trends |
| `categorizer.py` | Transparent keyword auto-categoriser |
| `synthetic.py` | Clearly labelled synthetic Kenyan student data generator |

**Honest model selection:** for each student the models are backtested on that student's own history. A learned model is used only if it beats the simple 14-day average by at least 5% on the same test days; otherwise the simpler method is kept. Reliability is labelled Low / Medium / High from history length and measured error.

Insights are recalculated only when the data changes (a fingerprint of the ledger), not on every page load.

Run the evaluation on synthetic students and regenerate `docs/MODEL_EVALUATION.md`:

```bash
python manage.py evaluate_models --students 30 --days 120
```

---

## 5. Tests

```bash
python manage.py test
```

75 automated tests cover registration and login, access control (one student cannot read or change another's data), CSRF, transaction CRUD and decimal arithmetic, filters and pagination, the M-Pesa parser, budget date boundaries and states, savings reconciliation and reversals, dashboard aggregates, the AI engine, insight caching and scoping, CSV/PDF exports (including CSV formula-injection protection), the PWA manifest and service worker, and security headers. Results are in `docs/TEST_REPORT.md`.

---

## 6. Project structure

```
student-finance-system/
├── config/           settings (env-driven), URLs, WSGI/ASGI
├── accounts/         custom User model, registration, login, settings, delete account
├── transactions/     categories, income, expenses, M-Pesa SMS parser
├── budgeting/        budgets, category limits, obligations, alert signals
├── savings/          virtual goals and append-only contribution ledger
├── analytics/        shared money arithmetic and the dashboard
├── ai_engine/        engine/ (pure Python ML), insights, notifications, management commands
├── reports/          report page, CSV and PDF export
├── core/             landing, PWA views, middleware, template filters
├── templates/        Django templates (base.html, one folder per module)
├── static/
│   ├── css/          base.css (tokens), layout.css, components.css
│   ├── js/           app.js, dashboard.js, forms.js, pwa-register.js
│   ├── icons/        PWA icons
│   └── vendor/       Chart.js (local copy, works offline)
├── pwa/              notes on where the PWA files live
├── scripts/          MySQL create, backup and restore scripts
├── docs/             ERD, test report, model evaluation, deployment, phase map
├── run.bat / run.sh  one-click start
├── requirements.txt
└── .env.example
```

---

## 7. Installing as an app (PWA)

Open the site in Chrome or Edge and choose **Install** from the address bar or menu (on iPhone: Safari → Share → **Add to Home Screen**). The in-app **Install app** button appears when the browser allows it. See `/install/` in the app.

Installation needs HTTPS on a real domain (`localhost` also works for testing). Offline, only the app shell and an offline notice load; saving and viewing records needs a connection, because financial data is deliberately never cached on the device.

---

## 8. Deployment

See `docs/DEPLOYMENT.md` for production settings, HTTPS, Gunicorn + Nginx, static files, backups and a deployment checklist.

---

## 9. Scope and privacy boundaries

* No connection to M-Pesa or bank APIs; data is entered manually or pasted from SMS.
* Never asks for M-Pesa PINs, bank passwords, one-time codes, phone numbers or admission numbers. Phone numbers are stripped from pasted SMS text.
* Savings goals are virtual; the app never holds or moves money.
* Forecasts are estimates from recorded data, not guarantees or financial advice.
* Use synthetic data in development; obtain informed consent before collecting real participant data.

---

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognised (Windows) | Reinstall Python and tick "Add python.exe to PATH", or run `py -3 -m venv .venv` |
| `pip install` fails on pandas / scikit-learn | Use Python 3.11–3.13 (64-bit) and upgrade pip: `python -m pip install --upgrade pip` |
| `Access denied for user` (MySQL) | Check `DB_USER` / `DB_PASSWORD` in `.env` match `scripts/create_mysql_db.sql` |
| `Unknown database 'student_finance'` | Run `scripts/create_mysql_db.sql` first |
| Port 8000 already in use | `python manage.py runserver 8001` |
| Password reset email does not arrive | In development it is printed in the terminal window running the server |
| Charts are empty | Add some expenses; charts only show your real records |
| Want to reset the demo account | `python manage.py seed_demo` (recreates it) |
