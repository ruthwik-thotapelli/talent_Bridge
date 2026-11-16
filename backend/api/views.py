import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
import requests

import urllib.parse
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.db import connection

from .models import User, PasswordReset, ATSReport
from .token_util import sign_token, decode_token
from .resume_parser import extract_resume_text
from .ats_scorer import score_resume_ats
from .ats_pdf import build_ats_pdf_buffer
from .email_service import (
    send_verification_email,
    send_reset_email,
    send_welcome_email,
    send_login_alert_email,
)

def get_authenticated_user(request, optional=False):
    auth_header = request.headers.get("Authorization", "") or request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1].strip()
        try:
            payload = decode_token(token)
            user_id = payload.get("id")
            email = payload.get("email")
            if user_id:
                user = User.objects.filter(id=user_id).first()
                if user:
                    return user
            if email:
                user = User.objects.filter(email=email).first()
                if user:
                    return user
        except Exception as e:
            print(f"[Auth Token Decode Error] {e}")
    if optional:
        return None
    return None

# ==========================================
# Root / Health Check
# ==========================================
def root_view(request):
    return HttpResponse(" TalentBridge Backend (Django) running")

def db_test_view(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 + 1 AS result")
            row = cursor.fetchone()
        return JsonResponse({"message": "DB OK ", "dbTest": {"result": row[0]}})
    except Exception as e:
        return JsonResponse({"message": "DB Error ", "error": str(e)}, status=500)

# ==========================================
# Auth Endpoints
# ==========================================
@csrf_exempt
def register_view(request):
    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"message": "Invalid JSON payload"}, status=400)

    try:
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", "")).strip()

        if not name or not email or not password:
            return JsonResponse({"message": "Name, email, password required"}, status=400)

        existing = User.objects.filter(email=email).first()
        if existing:
            if existing.provider and existing.provider != "local":
                return JsonResponse({
                    "message": f"This email is already registered using {existing.provider}. Please login using {existing.provider}."
                }, status=409)

            if existing.is_verified == 1:
                return JsonResponse({"message": "Email already registered"}, status=409)

            # Auto-verify if Brevo not configured, else resend verification
            if not getattr(settings, "BREVO_API_KEY", ""):
                existing.is_verified = 1
                existing.save()
                return JsonResponse({"message": "Account verified! You can now log in."}, status=200)

            raw_token = secrets.token_hex(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            expires = datetime.now(timezone.utc) + timedelta(minutes=30)

            existing.verify_token_hash = token_hash
            existing.verify_token_expiry = expires
            existing.save()

            verify_link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}&email={email}"
            try:
                send_verification_email(email, existing.name or name, verify_link)
            except Exception:
                pass

            return JsonResponse({"message": "Account exists but not verified. Verification email re-sent."}, status=200)

        # Hash password with bcrypt
        hashed_pass = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")

        auto_verify = not bool(getattr(settings, "BREVO_API_KEY", ""))
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(minutes=30)

        user = User(
            name=name,
            email=email,
            password=hashed_pass,
            role="user",
            provider="local",
            is_verified=1 if auto_verify else 0,
            verify_token_hash=token_hash if not auto_verify else None,
            verify_token_expiry=expires if not auto_verify else None,
        )
        user.save()

        if not auto_verify:
            verify_link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}&email={email}"
            try:
                send_verification_email(email, name, verify_link)
            except Exception:
                pass
            return JsonResponse({"message": "Account created! Please verify your email, then login."}, status=201)
        else:
            return JsonResponse({"message": "Account created successfully! You can now log in."}, status=201)
    except Exception as err:
        print(f"[Register Error] {err}")
        return JsonResponse({"message": "Registration failed", "error": str(err)}, status=500)


def verify_email_view(request):
    token = request.GET.get("token")
    email = request.GET.get("email", "").strip().lower()

    if not token or not email:
        return HttpResponse("Invalid verification link", status=400)

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user = User.objects.filter(email=email).first()

    if not user:
        return HttpResponse("Invalid verification link", status=400)

    if user.is_verified == 1:
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}/login?verified=1")

    if not user.verify_token_hash or not user.verify_token_expiry:
        return HttpResponse("Verification link invalid", status=400)

    now = datetime.now(timezone.utc)
    if user.verify_token_expiry < now or user.verify_token_hash != token_hash:
        return HttpResponse("Verification link expired or invalid", status=400)

    user.is_verified = 1
    user.verify_token_hash = None
    user.verify_token_expiry = None
    user.save()

    try:
        send_welcome_email(email, user.name)
    except Exception:
        pass

    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/login?verified=1")


@csrf_exempt
def login_view(request):
    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"message": "Invalid JSON payload"}, status=400)

    try:
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", "")).strip()

        if not email or not password:
            return JsonResponse({"message": "Email and password required"}, status=400)

        user = User.objects.filter(email=email).first()
        if not user:
            return JsonResponse({"message": "Invalid email or password"}, status=401)

        # In local dev without Brevo, auto-verify if needed
        if user.provider == "local" and user.is_verified == 0:
            if not getattr(settings, "BREVO_API_KEY", ""):
                user.is_verified = 1
                user.save()
            else:
                return JsonResponse({"message": "Please verify your email first"}, status=403)

        if not user.password:
            return JsonResponse({"message": "Use Google/GitHub login for this account"}, status=401)

        # Check password
        try:
            match = bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8"))
        except Exception:
            match = False

        if not match:
            return JsonResponse({"message": "Invalid email or password"}, status=401)

        token = sign_token({"id": user.id, "email": user.email, "role": user.role})

        # Optional login alert
        meta = {
            "ip": request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "N/A")),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            send_login_alert_email(user.email, user.name, meta)
        except Exception:
            pass

        return JsonResponse({
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "provider": user.provider,
            },
        })
    except Exception as err:
        print(f"[Login Error] {err}")
        return JsonResponse({"message": "Login failed", "error": str(err)}, status=500)


@csrf_exempt
def forgot_password_view(request):
    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    email = str(data.get("email", "")).strip().lower()
    if not email:
        return JsonResponse({"message": "Email is required"}, status=400)

    user = User.objects.filter(email=email).first()
    if not user:
        return JsonResponse({"message": "If the email exists, reset link sent "})

    if user.provider == "local" and user.is_verified == 0:
        return JsonResponse({"message": "Please verify your email first"}, status=403)

    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)

    PasswordReset.objects.filter(user=user).delete()
    PasswordReset.objects.create(user=user, token_hash=token_hash, expires_at=expires)

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}&email={user.email}"
    try:
        send_reset_email(user.email, user.name, reset_link)
    except Exception:
        pass

    return JsonResponse({"message": "If the email exists, reset link sent "})


@csrf_exempt
def reset_password_view(request):
    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    token = data.get("token")
    email = str(data.get("email", "")).strip().lower()
    new_password = str(data.get("newPassword", "")).strip()

    if not token or not email or not new_password:
        return JsonResponse({"message": "token, email, newPassword required"}, status=400)

    user = User.objects.filter(email=email).first()
    if not user:
        return JsonResponse({"message": "Invalid request"}, status=400)

    token_hash = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    reset_entry = PasswordReset.objects.filter(
        user=user, token_hash=token_hash, expires_at__gt=now
    ).order_by("-id").first()

    if not reset_entry:
        return JsonResponse({"message": "Token invalid or expired"}, status=400)

    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")
    user.password = hashed
    user.provider = "local"
    user.save()

    PasswordReset.objects.filter(user=user).delete()

    return JsonResponse({"message": "Password updated successfully "})

# ==========================================
# Admin Auth Endpoints
# ==========================================
@csrf_exempt
def admin_forgot_password_view(request):
    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    email = str(data.get("email", "")).strip().lower()
    if not email:
        return JsonResponse({"message": "Email is required"}, status=400)

    user = User.objects.filter(email=email).first()
    if not user or user.role != "admin":
        return JsonResponse({"message": "If the email exists, reset link sent "})

    if user.provider == "local" and user.is_verified == 0:
        return JsonResponse({"message": "Admin email is not verified yet."}, status=403)

    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)

    PasswordReset.objects.filter(user=user).delete()
    PasswordReset.objects.create(user=user, token_hash=token_hash, expires_at=expires)

    reset_link = f"{settings.FRONTEND_URL}/admin/reset-password?token={raw_token}&email={user.email}"
    try:
        send_reset_email(user.email, user.name or "Admin", reset_link)
    except Exception:
        pass

    return JsonResponse({"message": "If the email exists, reset link sent "})


@csrf_exempt
def admin_reset_password_view(request):
    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    token = data.get("token")
    email = str(data.get("email", "")).strip().lower()
    new_password = str(data.get("newPassword", "")).strip()

    if not token or not email or not new_password:
        return JsonResponse({"message": "token, email, newPassword required"}, status=400)

    user = User.objects.filter(email=email).first()
    if not user or user.role != "admin":
        return JsonResponse({"message": "Invalid request"}, status=400)

    token_hash = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    reset_entry = PasswordReset.objects.filter(
        user=user, token_hash=token_hash, expires_at__gt=now
    ).order_by("-id").first()

    if not reset_entry:
        return JsonResponse({"message": "Token invalid or expired"}, status=400)

    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")
    user.password = hashed
    user.provider = "local"
    user.save()

    PasswordReset.objects.filter(user=user).delete()

    return JsonResponse({"message": "Admin password updated successfully "})

# ==========================================
# Profile Endpoints
# ==========================================
def profile_me_view(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({"ok": False, "message": "Not authorized, token missing or invalid"}, status=401)

    return JsonResponse({
        "message": "Profile fetched ",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "provider": user.provider,
        }
    })

def profile_admin_view(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({"ok": False, "message": "Not authorized"}, status=401)
    if user.role != "admin":
        return JsonResponse({"ok": False, "message": "Admin only"}, status=403)

    return JsonResponse({
        "message": "Admin route ",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "provider": user.provider,
        }
    })

# ==========================================
# Resume / ATS Endpoints
# ==========================================
@csrf_exempt
def resume_score_view(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)

    user = get_authenticated_user(request, optional=True)
    file = request.FILES.get("resume")
    job_desc = request.POST.get("jobDescription", "")

    if not file:
        return JsonResponse({"ok": False, "message": "Resume file is required (PDF/DOCX)"}, status=400)

    try:
        text = extract_resume_text(file)
    except Exception as e:
        return JsonResponse({"ok": False, "message": str(e)}, status=400)

    if not text or len(text) < 30:
        return JsonResponse({
            "ok": False,
            "message": "Could not extract readable text from resume. Try another PDF/DOCX."
        }, status=400)

    result = score_resume_ats(text, job_desc)

    # Save report
    report = ATSReport.objects.create(
        user=user,
        resume_name=file.name,
        score=result["score"],
        level=result["level"],
        keyword_match_percent=result["keywordMatchPercent"],
        breakdown_json=json.dumps(result["breakdown"]),
        section_status_json=json.dumps(result["sectionStatus"]),
        checklist_json=json.dumps(result["checklist"]),
        issues_json=json.dumps(result["issues"]),
        fixes_json=json.dumps(result["fixes"]),
        examples_json=json.dumps(result["examples"]),
        job_desc_snippet=(job_desc or "")[:500],
    )

    return JsonResponse({
        "ok": True,
        "extractedChars": len(text),
        "reportId": report.id,
        **result,
    })


def resume_history_view(request):
    user = get_authenticated_user(request, optional=True)

    if user:
        reports = ATSReport.objects.filter(user=user).order_by("-created_at")[:10]
    else:
        reports = ATSReport.objects.all().order_by("-created_at")[:10]

    def safe_parse(v, fallback):
        if not v:
            return fallback
        try:
            return json.loads(v)
        except Exception:
            return fallback

    history = []
    for r in reports:
        history.append({
            "id": r.id,
            "resumeName": r.resume_name,
            "score": r.score,
            "level": r.level,
            "keywordMatchPercent": r.keyword_match_percent,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
            "jobDescSnippet": r.job_desc_snippet,
            "breakdown": safe_parse(r.breakdown_json, {}),
            "sectionStatus": safe_parse(r.section_status_json, {}),
            "checklist": safe_parse(r.checklist_json, []),
            "issues": safe_parse(r.issues_json, []),
            "fixes": safe_parse(r.fixes_json, []),
            "examples": safe_parse(r.examples_json, []),
        })

    return JsonResponse({"ok": True, "history": history})


def download_ats_pdf_view(request, report_id):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({"ok": False, "message": "Login required to download PDF"}, status=401)

    report = ATSReport.objects.filter(id=report_id, user=user).first()
    if not report:
        return JsonResponse({"ok": False, "message": "Report not found"}, status=404)

    pdf_buffer = build_ats_pdf_buffer(report)
    safe_name = "".join(c for c in (report.resume_name or "ats-report") if c.isalnum() or c in "-_")[:40]

    response = HttpResponse(pdf_buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{safe_name}-ATS-{report.id}.pdf"'
    return response

# ==========================================
# OAuth (Google / GitHub)
# ==========================================
def google_auth_view(request):
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    if not client_id:
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed&reason=no_google_client_id')

    redirect_uri = f'{request.scheme}://localhost:5000/api/auth/google/callback'
    scope = 'openid email profile'
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'prompt': 'select_account',
        'access_type': 'offline',
    }
    google_auth_url = f'https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}'
    return HttpResponseRedirect(google_auth_url)


def google_callback_view(request):
    code = request.GET.get('code')
    error = request.GET.get('error')
    if error or not code:
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed')

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    redirect_uri = f'{request.scheme}://localhost:5000/api/auth/google/callback'

    try:
        token_res = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=10,
        )
        token_data = token_res.json()
        access_token = token_data.get('access_token')
        if not access_token:
            return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed')

        user_info_res = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        user_info = user_info_res.json()
        email = (user_info.get('email') or '').strip().lower()
        provider_id = user_info.get('id')
        name = user_info.get('name') or 'Google User'

        if not email:
            return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed')

        user = User.objects.filter(email=email).first()
        if user:
            user.provider = 'google'
            user.provider_id = str(provider_id)
            user.is_verified = 1
            user.save()
        else:
            user = User.objects.create(
                name=name,
                email=email,
                password=None,
                role='user',
                provider='google',
                provider_id=str(provider_id),
                is_verified=1,
            )

        token = sign_token({'id': user.id, 'email': user.email, 'role': user.role})
        redirect_params = urllib.parse.urlencode({
            'token': token,
            'name': user.name or '',
            'email': user.email or '',
            'provider': 'google',
        })
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/oauth-success?{redirect_params}')

    except Exception as e:
        print(f'[Google OAuth Error] {e}')
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed')


def github_auth_view(request):
    client_id = getattr(settings, 'GITHUB_CLIENT_ID', '')
    if not client_id:
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed&reason=no_github_client_id')

    redirect_uri = f'{request.scheme}://{request.get_host()}/api/auth/github/callback'
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'user:email',
        'prompt': 'login',
    }
    github_url = f'https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}'
    return HttpResponseRedirect(github_url)


def github_callback_view(request):
    code = request.GET.get('code')
    error = request.GET.get('error')
    if error or not code:
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed')

    client_id = getattr(settings, 'GITHUB_CLIENT_ID', '')
    client_secret = getattr(settings, 'GITHUB_CLIENT_SECRET', '')
    redirect_uri = f'{request.scheme}://{request.get_host()}/api/auth/github/callback'

    try:
        token_res = requests.post(
            'https://github.com/login/oauth/access_token',
            headers={'Accept': 'application/json'},
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'redirect_uri': redirect_uri,
            },
            timeout=10,
        )
        token_data = token_res.json()
        access_token = token_data.get('access_token')
        if not access_token:
            return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed')

        user_res = requests.get(
            'https://api.github.com/user',
            headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'},
            timeout=10,
        )
        gh_user = user_res.json()
        provider_id = gh_user.get('id')
        name = gh_user.get('name') or gh_user.get('login') or 'GitHub User'
        email = (gh_user.get('email') or '').strip().lower()

        if not email:
            emails_res = requests.get(
                'https://api.github.com/user/emails',
                headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'},
                timeout=10,
            )
            emails_list = emails_res.json()
            if isinstance(emails_list, list):
                primary = next((e for e in emails_list if e.get('primary') and e.get('verified')), None)
                if not primary and len(emails_list) > 0:
                    primary = emails_list[0]
                if primary:
                    email = (primary.get('email') or '').strip().lower()

        if not email:
            return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed')

        user = User.objects.filter(email=email).first()
        if user:
            user.provider = 'github'
            user.provider_id = str(provider_id)
            user.is_verified = 1
            user.save()
        else:
            user = User.objects.create(
                name=name,
                email=email,
                password=None,
                role='user',
                provider='github',
                provider_id=str(provider_id),
                is_verified=1,
            )

        token = sign_token({'id': user.id, 'email': user.email, 'role': user.role})
        redirect_params = urllib.parse.urlencode({
            'token': token,
            'name': user.name or '',
            'email': user.email or '',
            'provider': 'github',
        })
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/oauth-success?{redirect_params}')

    except Exception as e:
        print(f'[GitHub OAuth Error] {e}')
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?oauth=failed')
