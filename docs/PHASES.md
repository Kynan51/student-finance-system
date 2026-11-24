# Roadmap phase map

Where each of the 12 roadmap phases is implemented, and how to check it.

| Phase | Deliverable | Main files | How to verify |
|---|---|---|---|
| 1. Setup | Runnable Django project, MySQL-ready, env config, README | `config/`, `requirements.txt`, `.env.example`, `.gitignore`, `run.bat`, `run.sh` | `python manage.py check`; run the app |
| 2. Database | ERD, schema, models, migrations | `*/models.py`, `*/migrations/`, `docs/ERD.md` | `python manage.py migrate`; open `/admin/` |
| 3. Frontend | Responsive vanilla HTML/CSS/JS design system | `templates/`, `static/css/*.css`, `static/js/app.js` | Resize the browser; tab through with the keyboard |
| 4. Authentication | Register, login, logout, reset, profile, ownership | `accounts/` | `python manage.py test accounts` |
| 5. Income & expenses | CRUD, filters, search, pagination, KSh, M-Pesa paste | `transactions/`, `static/js/forms.js` | `python manage.py test transactions` |
| 6. Budgets | Monthly/semester budgets, limits, obligations, warnings | `budgeting/` | `python manage.py test budgeting` |
| 7. Savings goals | Virtual goals, audit trail, reconciliation | `savings/` | `python manage.py test savings` |
| 8. Dashboard | Live aggregates and Chart.js charts with period filters | `analytics/`, `templates/dashboard/`, `static/js/dashboard.js` | `python manage.py test analytics` |
| 9. AI/ML engine | Baselines, forecasters, backtest, anomalies, synthetic data | `ai_engine/engine/`, `evaluate_models` command, `docs/MODEL_EVALUATION.md` | `python manage.py evaluate_models` |
| 10. Insights & alerts | Dated, explainable insight cards; notifications | `ai_engine/services.py`, `ai_engine/views.py`, `templates/insights/` | `python manage.py test ai_engine`; open AI insights |
| 11. Reports, testing, security | CSV/PDF, 75 tests, test report | `reports/`, `*/tests.py`, `docs/TEST_REPORT.md` | `python manage.py test` |
| 12. PWA & deployment | Manifest, service worker, offline page, icons, production settings, backups | `core/views.py`, `templates/core/`, `static/js/pwa-register.js`, `scripts/`, `docs/DEPLOYMENT.md` | Install from Chrome; `check --deploy` |

## Implemented vs planned (for the defence)

**Implemented:** everything in the table above, tested on SQLite and MariaDB 10.11.

**Planned / not yet done:**
* Real-device PWA install testing over HTTPS on the deployed domain.
* User acceptance testing with consenting students, and re-running the model evaluation on that data.
* AES-256 field-level encryption (proposal 1.9) is not implemented. Passwords are hashed with Django's PBKDF2, data is protected by authentication, ownership checks and HTTPS in transit. Field encryption at rest can be added with a library such as `django-cryptography`, or by enabling MySQL data-at-rest encryption on the server. Note the trade-off: encrypted amount fields cannot be summed by the database, so totals would have to be computed in Python.
* Offline transaction entry (would need a separately designed, secure sync queue).
