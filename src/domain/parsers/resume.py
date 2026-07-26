"""Resume document parser."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def parse_resume(raw_text: str, raw_result: Any) -> dict[str, Any]:
    """Parse resume data from extracted text.

    Args:
        raw_text: Plain text extracted from the resume.
        raw_result: Raw parser result object (ResumeExtracted if from smartresume).

    Returns:
        Dict with full_name, email, phone, work_experience, education, skills.
    """
    # If we have a ResumeExtracted-like object from smartresume, use it directly
    if raw_result is not None and hasattr(raw_result, "full_name"):
        return _from_smartresume(raw_result)

    text = _get_text(raw_text, raw_result)

    if not text or len(text.strip()) < 5:
        return _empty_result()

    logger.debug("parsing_resume", text_length=len(text))

    work_exp = _extract_work_experience(text)
    education = _extract_education(text)
    skills = _extract_skills(text)
    certifications = _extract_certifications(text)

    current = next((e for e in work_exp if e.get("is_current")), None)

    return {
        "full_name": _extract_name(text),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "location": _extract_location(text),
        "summary": _extract_summary(text),
        "years_of_experience": _estimate_years(work_exp),
        "work_experience": work_exp,
        "total_positions": len(work_exp),
        "current_employer": current.get("company") if current else None,
        "current_job_title": current.get("job_title") if current else None,
        "education": education,
        "highest_degree": _highest_degree(education),
        "skills": skills,
        "skill_count": len(skills),
        "certifications": certifications,
    }


def _from_smartresume(resume: Any) -> dict[str, Any]:
    """Convert a ResumeExtracted smartresume object to dict."""
    work_experience = []
    for exp in getattr(resume, "work_experience", []) or []:
        work_experience.append({
            "job_title": exp.job_title if hasattr(exp, "job_title") else exp.get("job_title"),
            "company": exp.company if hasattr(exp, "company") else exp.get("company"),
            "location": exp.location if hasattr(exp, "location") else exp.get("location"),
            "start_date": exp.start_date if hasattr(exp, "start_date") else exp.get("start_date"),
            "end_date": exp.end_date if hasattr(exp, "end_date") else exp.get("end_date"),
            "is_current": exp.is_current if hasattr(exp, "is_current") else exp.get("is_current", False),
            "description": exp.description if hasattr(exp, "description") else exp.get("description"),
            "achievements": exp.achievements if hasattr(exp, "achievements") else exp.get("achievements"),
            "duration_months": exp.duration_months if hasattr(exp, "duration_months") else exp.get("duration_months"),
            "industry": exp.industry if hasattr(exp, "industry") else exp.get("industry"),
        })

    education = []
    for edu in getattr(resume, "education", []) or []:
        education.append({
            "degree": edu.degree if hasattr(edu, "degree") else edu.get("degree"),
            "institution": edu.institution if hasattr(edu, "institution") else edu.get("institution"),
            "field_of_study": edu.field_of_study if hasattr(edu, "field_of_study") else edu.get("field_of_study"),
            "start_date": edu.start_date if hasattr(edu, "start_date") else edu.get("start_date"),
            "end_date": edu.end_date if hasattr(edu, "end_date") else edu.get("end_date"),
            "gpa": edu.gpa if hasattr(edu, "gpa") else edu.get("gpa"),
        })

    current = next((e for e in work_experience if e.get("is_current")), None)

    return {
        "full_name": getattr(resume, "full_name", None) or "Unknown",
        "email": getattr(resume, "email", None),
        "phone": getattr(resume, "phone", None),
        "location": getattr(resume, "location", None),
        "summary": getattr(resume, "summary", None),
        "years_of_experience": getattr(resume, "years_of_experience", None),
        "work_experience": work_experience,
        "total_positions": getattr(resume, "total_positions", 0) or 0,
        "current_employer": current.get("company") if current else getattr(resume, "current_employer", None),
        "current_job_title": current.get("job_title") if current else getattr(resume, "current_job_title", None),
        "education": education,
        "highest_degree": getattr(resume, "highest_degree", None),
        "skills": getattr(resume, "skills", []) or [],
        "skill_count": len(getattr(resume, "skills", []) or []),
        "certifications": getattr(resume, "certifications", []) or [],
    }


def _get_text(raw_text: str, raw_result: Any) -> str:
    """Get text from raw_text or raw_result."""
    if raw_text and len(raw_text.strip()) > 5:
        return raw_text
    if raw_result is not None and hasattr(raw_result, "raw_extracted_data"):
        data = raw_result.raw_extracted_data
        if isinstance(data, dict) and "markdown" in data:
            return data["markdown"] or ""
        return str(data)
    return ""


def _extract_name(text: str) -> str | None:
    """Extract name from resume (usually first non-empty line)."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines:
        # Skip lines that are clearly contact info or headers
        if re.match(r"^[\d\+\(\)\-\s\.]+$", line):
            continue
        if "@" in line or "http" in line.lower() or "linkedin" in line.lower():
            continue
        if len(line) <= 60 and not line.startswith("#"):
            return line
    return None


def _extract_email(text: str) -> str | None:
    """Extract email address."""
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else None


def _extract_phone(text: str) -> str | None:
    """Extract phone number."""
    match = re.search(r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}", text)
    return match.group(0) if match else None


def _extract_location(text: str) -> str | None:
    """Extract location/city."""
    locations = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain", "Al Ain"]
    for loc in locations:
        if loc.lower() in text.lower():
            return loc
    match = re.search(r"(?:Location|City|Based in|Location)\s*[:\-]?\s*([A-Za-z\s,]+?)(?:\n|$)", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_summary(text: str) -> str | None:
    """Extract professional summary."""
    match = re.search(
        r"(?:Summary|Profile|Professional Summary|About Me|ملخص)\s*[:\-]?\s*([\s\S]{50,300}?)(?=\n\s*\n|\n\s*(?:Experience|Work|Education|Skills|التعليم|المهارات)|$)",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return None


def _extract_work_experience(text: str) -> list[dict[str, Any]]:
    """Extract work experience entries."""
    experiences = []

    # Split by common section headers
    exp_section = re.split(
        r"(?:^|\n)\s*(?:WORK EXPERIENCE|PROFESSIONAL EXPERIENCE|EXPERIENCE|WORK HISTORY|الخبرة العملية)\s*(?:$|\n)",
        text,
        flags=re.IGNORECASE,
    )

    if len(exp_section) < 2:
        return experiences

    exp_text = exp_section[1]
    # Split by job entries (look for company names, dates, job titles)
    entries = re.split(r"(?=\n\s*[A-Za-z]+.*\d{4})", exp_text)

    for entry in entries[:10]:  # limit
        exp = _parse_single_experience(entry)
        if exp.get("job_title") or exp.get("company"):
            experiences.append(exp)

    return experiences


def _parse_single_experience(entry: str) -> dict[str, Any]:
    """Parse a single work experience entry."""
    lines = [line.strip() for line in entry.split("\n") if line.strip()]

    job_title = None
    company = None
    location = None
    start_date = None
    end_date = None
    is_current = False
    description = None

    # Look for date patterns
    date_match = re.search(r"(\d{4})\s*[-–]\s*(\d{4}|Present|Current|حتى الآن)", entry, re.IGNORECASE)
    if date_match:
        start_date = _safe_date(date_match.group(1))
        end_str = date_match.group(2)
        if end_str.lower() in ("present", "current", "حتى الآن"):
            is_current = True
            end_date = None
        else:
            end_date = _safe_date(end_str)

    # Look for "Present" indicator
    if re.search(r"\bPresent\b|\bCurrent\b", entry, re.IGNORECASE):
        is_current = True

    # First non-date line is often job title
    for line in lines:
        if re.match(r"\d{4}", line):
            continue
        if not job_title and len(line) < 60:
            job_title = line
            continue
        if not company and len(line) < 80 and not re.match(r"[\d\-\s\.]+$", line):
            company = line
            break

    # Description: remaining text
    desc_lines = []
    for line in lines:
        if line.startswith("•") or line.startswith("-") or line.startswith("*"):
            desc_lines.append(line.lstrip("•-* ").strip())

    description = "\n".join(desc_lines[:5]) if desc_lines else None

    return {
        "job_title": job_title,
        "company": company,
        "location": location,
        "start_date": start_date,
        "end_date": end_date,
        "is_current": is_current,
        "description": description,
        "achievements": [],
        "duration_months": None,
        "industry": None,
    }


def _extract_education(text: str) -> list[dict[str, Any]]:
    """Extract education entries."""
    educations = []

    edu_section = re.split(
        r"(?:^|\n)\s*(?:EDUCATION|EDUCATIONAL BACKGROUND|التعليم|المؤهلات)\s*(?:$|\n)",
        text,
        flags=re.IGNORECASE,
    )

    if len(edu_section) < 2:
        return educations

    edu_text = edu_section[1]
    # Split by entries
    entries = re.split(r"(?=\n\s*[A-Za-z]+.*(?:University|College|Institute|Degree|Bachelor|Master|PhD))", edu_text, flags=re.IGNORECASE)

    for entry in entries[:5]:
        edu = _parse_single_education(entry)
        if edu.get("degree") or edu.get("institution"):
            educations.append(edu)

    return educations


def _parse_single_education(entry: str) -> dict[str, Any]:
    """Parse a single education entry."""
    lines = [line.strip() for line in entry.split("\n") if line.strip()]

    degree = None
    institution = None
    field_of_study = None
    start_date = None
    end_date = None
    gpa = None

    # Look for dates
    date_match = re.search(r"(\d{4})\s*[-–]?\s*(\d{4})?", entry)
    if date_match:
        start_date = _safe_date(date_match.group(1))
        if date_match.group(2):
            end_date = _safe_date(date_match.group(2))

    # Look for GPA
    gpa_match = re.search(r"(?:GPA|CGPA|Grade)\s*[:\-]?\s*([\d\.]+)", entry, re.IGNORECASE)
    if gpa_match:
        gpa = float(gpa_match.group(1))

    # Look for degree keywords
    degree_keywords = ["Bachelor", "Master", "PhD", "Doctorate", "Associate", "Diploma", "High School"]
    for kw in degree_keywords:
        if kw.lower() in entry.lower():
            degree_match = re.search(rf"({kw}[^,\n]{{0,60}})", entry, re.IGNORECASE)
            if degree_match:
                degree = degree_match.group(1).strip()
                break

    # Institution
    inst_match = re.search(r"(?:University|College|Institute|أكاديمية|جامعة)[^,\n]{0,50}", entry, re.IGNORECASE)
    if inst_match:
        institution = inst_match.group(0).strip()

    return {
        "degree": degree,
        "institution": institution,
        "field_of_study": field_of_study,
        "start_date": start_date,
        "end_date": end_date,
        "gpa": gpa,
    }


def _extract_skills(text: str) -> list[str]:
    """Extract skills from resume."""
    skills = []
    skill_keywords = [
        "Python", "Java", "JavaScript", "TypeScript", "SQL", "C++", "C#", "Go", "Rust",
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Jenkins", "CI/CD",
        "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI", "Spring Boot",
        "Machine Learning", "Data Analysis", "Data Science", "Deep Learning", "NLP",
        "Project Management", "Agile", "Scrum", "PMP",
        "Excel", "Power BI", "Tableau", "SAP", "Salesforce",
        "Arabic", "English", "French",
    ]

    for skill in skill_keywords:
        if re.search(rf"\b{re.escape(skill)}\b", text, re.IGNORECASE):
            skills.append(skill)

    return skills


def _extract_certifications(text: str) -> list[str]:
    """Extract certifications."""
    certs = []
    cert_keywords = [
        "PMP", "AWS Certified", "Azure Certified", "Google Cloud", "CISSP", "CISA",
        "CPA", "CFA", "Six Sigma", "Prince2", "Scrum Master", "ITIL",
    ]
    for cert in cert_keywords:
        if re.search(rf"\b{re.escape(cert)}\b", text, re.IGNORECASE):
            certs.append(cert)
    return certs


def _estimate_years(work_exp: list[dict]) -> int | None:
    """Estimate years of experience from work history."""
    total_months = 0
    for exp in work_exp:
        start = exp.get("start_date")
        end = exp.get("end_date")
        if start and exp.get("is_current"):
            from datetime import date, datetime as _date
            end = _date.today()
        if start and end:
            try:
                if isinstance(start, str):
                    start = _parse_date_string(start)
                if isinstance(end, str):
                    end = _parse_date_string(end)
                if start and end:
                    delta = end - start
                    total_months += delta.days // 30
            except Exception:
                pass
    return total_months // 12 if total_months > 0 else None


def _highest_degree(education: list[dict]) -> str | None:
    """Determine highest degree from education list."""
    hierarchy = ["PhD", "Doctorate", "Master", "Bachelor", "Associate", "Diploma"]
    for degree in hierarchy:
        for edu in education:
            deg = edu.get("degree") or ""
            if degree.lower() in deg.lower():
                return degree
    return None


def _safe_date(year: str) -> date | None:
    """Create a date from a year string."""
    try:
        return date(int(year), 1, 1)
    except ValueError:
        return None


def _parse_date_string(value: str) -> date | None:
    """Parse a date string."""
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y"]:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _empty_result() -> dict[str, Any]:
    """Return empty result when no text is available."""
    return {
        "full_name": None,
        "email": None,
        "phone": None,
        "location": None,
        "summary": None,
        "years_of_experience": None,
        "work_experience": [],
        "total_positions": 0,
        "current_employer": None,
        "current_job_title": None,
        "education": [],
        "highest_degree": None,
        "skills": [],
        "skill_count": 0,
        "certifications": [],
    }
