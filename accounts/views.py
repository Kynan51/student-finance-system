from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from .forms import DeleteAccountForm, LoginForm, PreferencesForm, ProfileForm, RegistrationForm


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("analytics:dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome, {user.display_name}! Start by recording your income.")
        return redirect("analytics:dashboard")
    return render(request, "accounts/register.html", {"form": form})


class StudentLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("core:landing")


class StyledPasswordResetView(auth_views.PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class StyledPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


@login_required
@require_http_methods(["GET", "POST"])
def settings_view(request):
    user = request.user
    profile_form = ProfileForm(instance=user, prefix="profile")
    prefs_form = PreferencesForm(instance=user, prefix="prefs")
    password_form = PasswordChangeForm(user, prefix="pwd")
    for field in password_form.fields.values():
        field.widget.attrs["class"] = "input"

    if request.method == "POST":
        section = request.POST.get("section")
        if section == "profile":
            profile_form = ProfileForm(request.POST, instance=user, prefix="profile")
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated.")
                return redirect("accounts:settings")
        elif section == "preferences":
            prefs_form = PreferencesForm(request.POST, instance=user, prefix="prefs")
            if prefs_form.is_valid():
                prefs_form.save()
                messages.success(request, "Preferences saved.")
                return redirect("accounts:settings")
        elif section == "password":
            password_form = PasswordChangeForm(user, request.POST, prefix="pwd")
            for field in password_form.fields.values():
                field.widget.attrs["class"] = "input"
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "Password changed.")
                return redirect("accounts:settings")
        messages.error(request, "Please correct the highlighted fields.")

    return render(
        request,
        "accounts/settings.html",
        {"profile_form": profile_form, "prefs_form": prefs_form, "password_form": password_form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def delete_account(request):
    form = DeleteAccountForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        logout(request)
        user.delete()  # cascades to every financial record the user owns
        messages.success(request, "Your account and all of your financial records were deleted.")
        return redirect("core:landing")
    return render(request, "accounts/delete_account.html", {"form": form})
