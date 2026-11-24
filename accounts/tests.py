from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.testutils import PASSWORD, add_expense, make_user
from transactions.models import Expense

from .models import User

PROTECTED_URLS = [
    "analytics:dashboard", "transactions:income_list", "transactions:expense_list", "budgeting:list",
    "savings:list", "ai_engine:insights", "reports:report", "accounts:settings", "analytics:chart_data",
]


class RegistrationTests(TestCase):
    def test_register_logs_user_in_and_hashes_password(self):
        response = self.client.post(reverse("accounts:register"), {
            "first_name": "Wanjiku", "username": "wanjiku", "email": "Wanjiku@Example.com",
            "university": "MKU", "year_of_study": 2, "password1": PASSWORD, "password2": PASSWORD, "consent": "on",
        })
        self.assertRedirects(response, reverse("analytics:dashboard"))
        user = User.objects.get(username="wanjiku")
        self.assertEqual(user.email, "wanjiku@example.com")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith(("pbkdf2_", "argon2", "bcrypt")))

    def test_consent_and_unique_email_required(self):
        make_user("taken")
        response = self.client.post(reverse("accounts:register"), {
            "first_name": "X", "username": "newuser", "email": "taken@example.com",
            "password1": PASSWORD, "password2": PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("email", form.errors)
        self.assertIn("consent", form.errors)

    def test_weak_password_rejected(self):
        response = self.client.post(reverse("accounts:register"), {
            "first_name": "X", "username": "weak", "email": "weak@example.com",
            "password1": "12345678", "password2": "12345678", "consent": "on",
        })
        self.assertFalse(User.objects.filter(username="weak").exists())
        self.assertIn("password2", response.context["form"].errors)


class AuthAccessTests(TestCase):
    def test_protected_pages_redirect_anonymous_users(self):
        for name in PROTECTED_URLS:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse("accounts:login"), response["Location"])

    def test_login_and_logout(self):
        make_user("brian")
        response = self.client.post(reverse("accounts:login"), {"username": "brian", "password": PASSWORD})
        self.assertRedirects(response, reverse("analytics:dashboard"))
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)
        self.assertEqual(self.client.get(reverse("analytics:dashboard")).status_code, 302)

    def test_logout_requires_post(self):
        make_user("brian")
        self.client.login(username="brian", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)

    def test_password_reset_sends_email(self):
        make_user("reset")
        self.client.post(reverse("accounts:password_reset"), {"email": "reset@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    def test_csrf_enforced_on_login(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        make_user("csrf")
        response = client.post(reverse("accounts:login"), {"username": "csrf", "password": PASSWORD})
        self.assertEqual(response.status_code, 403)


class SettingsTests(TestCase):
    def setUp(self):
        self.user = make_user("kevin")
        self.client.login(username="kevin", password=PASSWORD)

    def test_update_profile_and_semester_validation(self):
        url = reverse("accounts:settings")
        bad = self.client.post(url, {
            "section": "profile", "profile-first_name": "Kevin", "profile-email": "kevin@example.com",
            "profile-semester_start": "2026-09-01", "profile-semester_end": "2026-08-01",
        })
        self.assertIn("semester_end", bad.context["profile_form"].errors)
        self.client.post(url, {
            "section": "profile", "profile-first_name": "Kev", "profile-email": "kevin@example.com",
            "profile-semester_start": "2026-09-01", "profile-semester_end": "2026-12-20",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Kev")
        self.assertEqual(str(self.user.semester_end), "2026-12-20")

    def test_delete_account_removes_financial_data(self):
        add_expense(self.user, 100)
        response = self.client.post(reverse("accounts:delete_account"), {"password": PASSWORD})
        self.assertRedirects(response, reverse("core:landing"))
        self.assertFalse(User.objects.filter(username="kevin").exists())
        self.assertEqual(Expense.objects.count(), 0)

    def test_delete_account_requires_correct_password(self):
        self.client.post(reverse("accounts:delete_account"), {"password": "wrong"})
        self.assertTrue(User.objects.filter(username="kevin").exists())
