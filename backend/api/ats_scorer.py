import re
from typing import List, Dict, Any

def normalize(text: str = "") -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()

def uniq(seq):
    seen = set()
    res = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            res.append(item)
    return res

def extract_emails(text: str) -> List[str]:
    matches = re.findall(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", text, re.IGNORECASE)
    return uniq(matches)

def extract_phones(text: str) -> List[str]:
    matches = re.findall(r"(\+?\d{1,3}[\s-]?)?(\(?\d{3,5}\)?[\s-]?)?\d{3,4}[\s-]?\d{4}", text)
    # re.findall with groups returns tuples, find iter matches instead
    full_matches = [m.group(0).strip() for m in re.finditer(r"(\+?\d{1,3}[\s-]?)?(\(?\d{3,5}\)?[\s-]?)?\d{3,4}[\s-]?\d{4}", text)]
    valid = [m for m in uniq(full_matches) if len(re.sub(r"\D", "", m)) >= 10]
    return valid

def extract_links(text: str) -> Dict[str, Any]:
    links = uniq(re.findall(r"https?://[^\s)]+", text, re.IGNORECASE))
    has_linkedin = any("linkedin.com" in l.lower() for l in links)
    has_github = any("github.com" in l.lower() for l in links)
    return {
        "links": links,
        "hasLinkedIn": has_linkedin,
        "hasGitHub": has_github,
    }

def has_bullets(raw: str) -> bool:
    return any(b in raw for b in ["", "- ", "* ", " "])

def has_dates(t: str) -> bool:
    return bool(
        re.search(r"\b(19|20)\d{2}\b", t) or
        re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", t)
    )

def section_present(t: str, keys: List[str]) -> bool:
    return any(k in t for k in keys)

def extract_keywords(jd_text: str) -> List[str]:
    stop = {
        "the", "and", "for", "with", "to", "in", "of", "a", "an", "is", "are", "on", "as", "at",
        "you", "your", "we", "our", "will", "have", "has", "be", "this", "that", "from", "or", "by"
    }
    cleaned = re.sub(r"[^a-z0-9\s]", " ", normalize(jd_text))
    words = [w for w in cleaned.split(" ") if len(w) >= 3 and w not in stop]
    return uniq(words)[:35]

def severity_for_issue(issue_type: str) -> str:
    if issue_type == "format":
        return "high"
    if issue_type == "section":
        return "medium"
    return "low"

def score_resume_ats(resume_text: str, job_description: str = "") -> Dict[str, Any]:
    raw = resume_text or ""
    t = normalize(raw)
    jd = normalize(job_description)

    # Section checks
    sections = {
        "education": ["education", "academic", "b.tech", "bachelor", "masters", "university", "college"],
        "skills": ["skills", "technical skills", "technologies", "tool", "tooling"],
        "experience": ["experience", "work experience", "internship", "employment", "professional experience"],
        "projects": ["projects", "project", "personal projects", "academic projects"],
    }

    section_status = {
        "education": section_present(t, sections["education"]),
        "skills": section_present(t, sections["skills"]),
        "experience": section_present(t, sections["experience"]),
        "projects": section_present(t, sections["projects"]),
    }

    # Format checklist
    emails = extract_emails(raw)
    phones = extract_phones(raw)
    link_info = extract_links(raw)

    checklist = [
        {"key": "email", "label": "Email present", "pass": len(emails) > 0},
        {"key": "phone", "label": "Phone present", "pass": len(phones) > 0},
        {"key": "linkedin", "label": "LinkedIn link present", "pass": link_info["hasLinkedIn"]},
        {"key": "github", "label": "GitHub link present", "pass": link_info["hasGitHub"]},
        {"key": "dates", "label": "Dates/timelines present", "pass": has_dates(t)},
        {"key": "bullets", "label": "Bullet points used", "pass": has_bullets(raw)},
    ]

    word_count = len([w for w in t.split(" ") if w])

    # Keywords matching
    matched_keywords = []
    missing_keywords = []
    keyword_match_percent = None

    if len(jd) > 20:
        keywords = extract_keywords(jd)
        for k in keywords:
            if k in t:
                matched_keywords.append(k)
            else:
                missing_keywords.append(k)
        keyword_match_percent = round((len(matched_keywords) / max(1, len(keywords))) * 100)

    # Scoring (Total 100)
    breakdown = {"keywords": 0, "sections": 0, "format": 0}

    if len(jd) > 20 and keyword_match_percent is not None:
        breakdown["keywords"] = round((keyword_match_percent / 100) * 35)
    else:
        breakdown["keywords"] = 15

    sec_points = {
        "education": 8 if section_status["education"] else 0,
        "skills": 9 if section_status["skills"] else 0,
        "experience": 9 if section_status["experience"] else 0,
        "projects": 9 if section_status["projects"] else 0,
    }
    breakdown["sections"] = sum(sec_points.values())

    all_sections = all(section_status.values())
    if all_sections:
        breakdown["sections"] = min(35, breakdown["sections"] + 3)

    passed_count = sum(1 for c in checklist if c["pass"])
    breakdown["format"] += round((passed_count / len(checklist)) * 18)

    if 250 <= word_count <= 900:
        breakdown["format"] += 12
    elif word_count >= 180:
        breakdown["format"] += 8
    else:
        breakdown["format"] += 4

    score = breakdown["keywords"] + breakdown["sections"] + breakdown["format"]
    score = max(0, min(100, score))

    # Actionable Fixes
    fixes = []
    if len(emails) == 0:
        fixes.append("Add an email address at the top.")
    if len(phones) == 0:
        fixes.append("Add a phone number at the top.")
    if not link_info["hasLinkedIn"]:
        fixes.append("Add your LinkedIn profile link.")
    if not link_info["hasGitHub"]:
        fixes.append("Add your GitHub link (if you have projects).")
    if not has_bullets(raw):
        fixes.append("Use bullet points for impact-based achievements.")
    if not has_dates(t):
        fixes.append("Add dates for education/experience (e.g., Jan 2026  Mar 2026).")

    if not section_status["skills"]:
        fixes.append("Add a clear Skills section with tools/tech.")
    if not section_status["projects"]:
        fixes.append("Add a Projects section with 23 projects and results.")
    if not section_status["experience"]:
        fixes.append("Add Internship/Experience section (even small ones).")
    if not section_status["education"]:
        fixes.append("Add Education section (college, degree, year).")

    if len(jd) > 20 and keyword_match_percent is not None and keyword_match_percent < 60:
        fixes.append("Add missing job keywords (only if you truly know them).")
    if len(jd) <= 20:
        fixes.append("Paste a Job Description for a more accurate ATS score.")

    if word_count < 180:
        fixes.append("Resume is too short. Add more detail & measurable outcomes.")
    elif word_count > 1000:
        fixes.append("Resume is too long. Keep it concise (12 pages).")

    # Issues list
    issues = []
    for c in checklist:
        if not c["pass"]:
            matched_fix = next((f for f in fixes if c["key"] in f.lower()), "")
            issues.append({
                "type": "format",
                "severity": severity_for_issue("format"),
                "field": c["key"],
                "message": f"{c['label']} is missing",
                "fix": matched_fix,
            })

    for k, v in section_status.items():
        if not v:
            issues.append({
                "type": "section",
                "severity": severity_for_issue("section"),
                "field": k,
                "message": f"Missing section: {k}",
                "fix": f'Add a "{k.upper()}" heading with relevant details.',
            })

    if word_count < 180:
        issues.append({
            "type": "content",
            "severity": severity_for_issue("content"),
            "field": "length",
            "message": "Resume content is too short",
            "fix": "Add more bullet points with measurable impact (numbers, scale, results).",
        })
    elif word_count > 1000:
        issues.append({
            "type": "content",
            "severity": severity_for_issue("content"),
            "field": "length",
            "message": "Resume content is too long",
            "fix": "Reduce to key achievements. Keep 12 pages.",
        })

    # Examples
    examples = []
    if not has_bullets(raw):
        examples.append({
            "title": "Bullet Rewrite Example",
            "bad": "Worked on backend APIs",
            "good": "Built 8 REST APIs in Node.js/Django + MySQL, improved response time by 35% via indexing and query optimization.",
        })
    if not has_dates(t):
        examples.append({
            "title": "Date Formatting Example",
            "bad": "Internship at Company",
            "good": "Internship  Company | Jan 2026  Mar 2026",
        })
    if len(jd) > 20 and keyword_match_percent is not None and keyword_match_percent < 60:
        examples.append({
            "title": "Keyword Matching Example",
            "bad": "Skills: Java, HTML, CSS",
            "good": "Skills: Django, Python, MySQL, REST APIs, JWT, Docker, Git (aligned with JD keywords)",
        })

    insights = {
        "wordCount": word_count,
        "keywordAdvice": f"Matched {len(matched_keywords)} keywords, missing {len(missing_keywords)}." if keyword_match_percent is not None else "Paste Job Description to calculate keyword match.",
        "topFix": fixes[0] if fixes else "Improve formatting and add measurable achievements",
    }

    level = "Needs Improvement"
    if score >= 80:
        level = "Strong"
    elif score >= 60:
        level = "Good"
    elif score >= 40:
        level = "Average"

    return {
        "ok": True,
        "score": score,
        "level": level,
        "breakdown": breakdown,
        "sectionStatus": section_status,
        "keywordMatchPercent": keyword_match_percent,
        "matchedKeywords": matched_keywords[:25],
        "missingKeywords": missing_keywords[:25],
        "checklist": checklist,
        "detected": {
            "wordCount": word_count,
            "emails": emails,
            "phones": phones,
            "links": link_info["links"][:10],
        },
        "fixes": fixes[:12],
        "issues": issues,
        "examples": examples,
        "insights": insights,
    }
