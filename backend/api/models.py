from django.db import models

class User(models.Model):
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, unique=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=50, default="user")
    provider = models.CharField(max_length=50, default="local")
    provider_id = models.CharField(max_length=255, null=True, blank=True)
    is_verified = models.IntegerField(default=0)
    verify_token_hash = models.CharField(max_length=255, null=True, blank=True)
    verify_token_expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        managed = False

    def __str__(self):
        return f"{self.name} <{self.email}>"


class PasswordReset(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    token_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_resets"
        managed = False


class ATSReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column="user_id")
    resume_name = models.CharField(max_length=255, null=True, blank=True)
    score = models.IntegerField()
    level = models.CharField(max_length=50, null=True, blank=True)
    keyword_match_percent = models.FloatField(null=True, blank=True)
    breakdown_json = models.TextField(null=True, blank=True)
    section_status_json = models.TextField(null=True, blank=True)
    checklist_json = models.TextField(null=True, blank=True)
    issues_json = models.TextField(null=True, blank=True)
    fixes_json = models.TextField(null=True, blank=True)
    examples_json = models.TextField(null=True, blank=True)
    job_desc_snippet = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ats_reports"
        managed = False
