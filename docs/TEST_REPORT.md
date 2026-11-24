# Test report (Phase 11)

* **Date:** 24 November 2026
* **Command:** `python manage.py test -v 2`
* **Environments:** SQLite 3 (Python 3.13, Django 5.2) and MariaDB 10.11 via PyMySQL
* **Result:** **75 tests, 75 passed, 0 failed** in both environments
* **Evidence:** console output of the command above; test code in each app's `tests.py`

## Defects found and fixed during testing

| # | Defect | Found by | Fix | Regression test |
|---|---|---|---|---|
| D1 | Model selection crashed (division by zero) when spending was perfectly constant and the baseline error was 0 | `InsightServiceTests` | `select_model` keeps the baseline when its error is 0 | `test_zero_error_baseline_does_not_crash` |
| D2 | The best model (Ridge) could never be selected because it was compared only when tested on the same number of days as the baseline | Synthetic evaluation (`evaluate_models`) | Models are now compared on the days both were tested (paired MAE) | `test_selection_prefers_baseline_unless_clearly_better` |
| D3 | A single monthly rent payment was reported as a "spending trend" | Manual review of demo insights | Trends need at least 3 transactions in the two windows | `test_trend_ignores_single_rent_payment` |
| D4 | Production `collectstatic` failed: Chart.js referenced a missing source map | Production-mode check | Source map added to `static/vendor/chartjs/` | Manual: `collectstatic` succeeds with `DJANGO_DEBUG=False` |
| D5 | Backup script failed because it read `.env` as a shell script | Backup/restore round trip | Script now reads only `DB_*` lines | Manual: backup → delete rows → restore returned all 158 rows |
| D6 | Sidebar close button visible on desktop | Visual check (screenshots) | CSS specificity corrected | Manual visual check |

## Test cases

| ID | Area | Test case | Expected result | Actual | Status |
|---|---|---|---|---|---|
| A1 | Registration | Register with valid data | User created, logged in, email lower-cased, password hashed | As expected | Pass |
| A2 | Registration | Duplicate email, missing consent | Form errors on email and consent; no account | As expected | Pass |
| A3 | Registration | Weak password `12345678` | Rejected by password validators | As expected | Pass |
| A4 | Access control | Anonymous user opens 9 protected pages | Redirect to login for every page | As expected | Pass |
| A5 | Auth | Log in, log out | Login redirects to dashboard; after logout dashboard redirects to login | As expected | Pass |
| A6 | Auth | Logout via GET | 405 (logout requires POST, prevents CSRF logout) | As expected | Pass |
| A7 | Auth | Password reset request | One email with a reset link | As expected | Pass |
| A8 | Security | Login POST without CSRF token | 403 Forbidden | As expected | Pass |
| A9 | Settings | Semester end before start; valid profile update | Error shown; valid update saved | As expected | Pass |
| A10 | Privacy | Delete account with correct / wrong password | Account and expenses deleted / nothing deleted | As expected | Pass |
| T1 | Ledger | Add, edit, delete expense | Cash balance 9,749.50 → 9,700.00 → 10,000.00 | As expected | Pass |
| T2 | Arithmetic | Ten expenses of 0.10 | Total exactly 1.00 (no float drift) | As expected | Pass |
| T3 | Validation | Amounts 0, −50, "abc", 20,000,000 | Each rejected; nothing saved | As expected | Pass |
| T4 | Validation | Expense dated 5 days in the future | Rejected | As expected | Pass |
| T5 | Ledger | Search, category + date filter, page 2 | 1 result; 10 results totalling 1,000; 6 rows on page 2 | As expected | Pass |
| T6 | Categories | Custom category | Visible to owner only | As expected | Pass |
| T7 | Ownership | GET/POST edit and delete on another user's income and expense | 404 every time; record unchanged | As expected | Pass |
| T8 | Ownership | List page | Other users' records and totals not shown | As expected | Pass |
| T9 | Ownership | POST with forged `owner` field | Record saved to the signed-in user only | As expected | Pass |
| T10 | Ownership | Use another user's private category | Form error | As expected | Pass |
| T11–T15 | M-Pesa parser | Till payment, received (phone stripped), sent, paybill, airtime, withdrawal, unrecognised, empty | Correct kind, amount, date, reference; phone and balance never in description; withdrawal flagged as not spending; clear errors | As expected | Pass |
| T16 | Parser endpoint | Paste matatu payment | Suggests "Transport"; nothing saved | As expected | Pass |
| B1 | Budget | Expenses on 31 Oct, 1 Nov, 30 Nov, 1 Dec for a November budget | Only 1 and 30 Nov counted (inclusive boundaries) | As expected | Pass |
| B2 | Budget | 79.99%, 80%, >100% used | ok → warning → exceeded | As expected | Pass |
| B3 | Budget | Edit and delete an expense | Spent recalculated each time | As expected | Pass |
| B4 | Budget | Category limit and unpaid obligation | Category spent and state correct; free-after-obligations correct | As expected | Pass |
| B5 | Budget | Another user's expense in range | Not counted | As expected | Pass |
| B6 | Alerts | Repeated warnings | One warning notification, then one exceeded notification | As expected | Pass |
| B7 | Budget views | Invalid dates; valid semester budget | Error; budget created | As expected | Pass |
| B8 | Ownership | Another user's budget detail, delete, add limit | 404; budget unchanged | As expected | Pass |
| S1 | Savings | Allocate 4,000 | Cash 15,000 unchanged; expenses unchanged; available 11,000 | As expected | Pass |
| S2 | Savings | Allocate more than available | Rejected | As expected | Pass |
| S3 | Savings | Reach target, then release | Completed → active again; cannot release more than saved | As expected | Pass |
| S4 | Savings | Reverse an entry | Balance 0; 2 entries kept; cannot reverse twice or reverse a reversal | As expected | Pass |
| S5 | Reconciliation | Allocate 1,000 + 1,500.50, release 500.25 | Ledger sum = goal balance = dashboard allocation = 2,000.25 | As expected | Pass |
| S6 | Ownership | Another user's goal | 404 on view and move | As expected | Pass |
| S7 | Savings | Allocate with no income | Clear error; nothing saved | As expected | Pass |
| D1 | Dashboard | Totals | Income 30,000; expenses 7,000.50; cash 22,999.50 (another user's 99,999 excluded) | As expected | Pass |
| D2 | Dashboard | Week vs all-time filter | 2,000.50 vs 7,000.50 | As expected | Pass |
| D3 | Charts | Chart JSON | Live, user-scoped data; 6 trend months | As expected | Pass |
| D4 | Dashboard | Invalid period; new user | Falls back to month; onboarding shown | As expected | Pass |
| M1–M4 | AI baseline | Zero-filled series; runway 15 days; short history; zero spend | Correct values; no runway when nothing is spent | As expected | Pass |
| M5–M9 | Forecasting | Constant series; no look-ahead; selection rule; zero error; short history | MAE 0; past-only predictions; ≥5% paired gain required; no crash; overall mean used | As expected | Pass |
| M10–M12 | Patterns | Clear outlier; too few samples; single rent payment | Outlier flagged; nothing flagged; rent not reported as trend | As expected | Pass |
| M13–M14 | Data / categoriser | Synthetic data labelled and reproducible; keyword matches | All rows tagged `[SYNTHETIC]`; same seed gives same data; matatu → Transport, kibanda → Food, unknown → none | As expected | Pass |
| M15–M18 | Insights | Empty user; runway/shortfall/forecast; caching; scoping | Data-quality insight; metrics and disclaimer present; reused until data changes; never shown to other users | As expected | Pass |
| R1 | Reports | October report | Income 10,000; expenses 500 (November excluded) | As expected | Pass |
| R2 | Reports | CSV export | Own rows only; other user's row absent; `=HYPERLINK` neutralised to `'=HYPERLINK` | As expected | Pass |
| R3 | Reports | PDF export | Valid PDF (`%PDF` header) | As expected | Pass |
| R4 | Reports | Custom range end before start | Form invalid | As expected | Pass |
| R5 | Reports | Anonymous export | Redirect to login | As expected | Pass |
| P1 | PWA | Manifest | standalone, theme `#123D2B`, 192 and 512 icons | As expected | Pass |
| P2 | PWA | Service worker | Root scope; navigations network-only; no private paths in cache list | As expected | Pass |
| P3 | PWA | Offline page while signed in | Contains no user data | As expected | Pass |
| H1 | Security | Signed-in response headers | `Cache-Control: no-store`; `X-Frame-Options: DENY` | As expected | Pass |
| F1 | Formatting | KSh filter | `KSh 1,234.50`, `-KSh 50`, `KSh 0.00` | As expected | Pass |

## Manual and non-automated checks

| Check | Method | Result |
|---|---|---|
| Every page loads for the demo user (34 URLs) | Django test client smoke script | All 200 (404 for unknown URL) |
| Responsive layout | Headless Chrome screenshots at 1366×900 and 390×844 | Sidebar becomes a drawer, tables stack into cards, stat tiles stack |
| M-Pesa paste flow in the browser | Headless Chrome | Message parsed, category suggested, pre-filled form link shown |
| Service worker registers with scope `/` | Headless Chrome | Registered; no console errors |
| Production settings | `check --deploy` with `DJANGO_DEBUG=False` | Only optional `SECURE_HSTS_PRELOAD` warning |
| Production static files | `collectstatic` + WhiteNoise | Hashed URLs used in pages and service worker |
| MySQL | MariaDB 10.11: migrate, seed, full test suite | Pass |
| Backup / restore | `scripts/backup_mysql.sh`, delete rows, `restore_mysql.sh` | All 158 rows restored |

## Not yet tested (to do before the final defence)

* PWA install on a real Android phone and an iPhone over HTTPS on the deployed domain.
* User acceptance testing with the 30-student focus group (proposal section 3.3), with consent.
* Model accuracy on real (consented) student data; current figures come from synthetic data only.
* Load testing on the chosen hosting plan.
