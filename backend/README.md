# TalentBridge Python Django Backend API

## Overview
This is the core RESTful API server for TalentBridge, built with **Python 3**, **Django 5/6**, and **MySQL**. It handles authentication, profile management, resume parsing, ATS scoring, PDF report generation, and automated workflows.

## Architecture
```
backend/
├── django_backend/      # Project settings, WSGI/ASGI, root URL routing
│   ├── settings.py      # Django configuration (CORS, DB, JWT, etc.)
│   ├── urls.py          # Root URL dispatcher
│   └── wsgi.py          # WSGI entry point
│
├── api/                 # Main TalentBridge API Application
│   ├── models.py        # Django ORM models (User, PasswordReset, ATSReport)
│   ├── views.py         # REST controllers & endpoint handlers
│   ├── urls.py          # Route definitions for /api/*
│   ├── ats_scorer.py    # Core ATS resume scoring engine
│   ├── ats_pdf.py       # PDF report generation with ReportLab
│   ├── resume_parser.py # PDF and DOCX text extraction
│   ├── email_service.py # Automated email notifications
│   └── token_util.py    # Stateless JWT authentication helpers
│
├── manage.py            # Django management CLI
├── requirements.txt     # Python dependencies
├── schema.sql           # Database initialization schema
├── .env                 # Environment variables
└── node_legacy/         # Archived original Node.js backend files
```

## Environment Variables (`.env`)
```env
PORT=5000
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=talentbridge_db
DJANGO_SECRET_KEY=replace_with_a_secure_random_key
JWT_SECRET=your_jwt_secret
FRONTEND_URL=http://localhost:3000
```

## Running Locally

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Migrations / Check Database**:
   ```bash
   python manage.py check
   ```

3. **Start Django Server**:
   ```bash
   python manage.py runserver 5000
   ```
   The backend API will be available at `http://localhost:5000`.

## API Endpoints
- `GET /` — Health check
- `GET /api/db-test` — Database connectivity test
- `POST /api/auth/register` — Register a new account
- `POST /api/auth/login` — Sign in and receive JWT
- `GET /api/auth/verify-email` — Verify account email
- `POST /api/auth/forgot-password` — Password reset link dispatch
- `POST /api/auth/reset-password` — Set new password
- `GET /api/profile/me` — Current user profile
- `POST /api/resume/score` — Upload PDF/DOCX resume & score against JD
- `GET /api/resume/history` — Fetch recent ATS score history
- `GET /api/resume/report/<id>/pdf` — Download ATS report PDF
