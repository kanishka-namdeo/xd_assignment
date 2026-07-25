"""Resume parser for DOCX and PDF resumes."""

import asyncio
import re
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog

from .schemas import (
    EducationExtracted,
    ResumeExtracted,
    WorkExperienceExtracted,
)

logger = structlog.get_logger(__name__)


class ResumeParser:
    """Resume parser for DOCX and PDF files.
    
    Extracts contact info, work experience, education, skills, and certifications.
    Uses smartresume library for structured parsing.
    """

    def __init__(self):
        """Initialize resume parser."""
        self.logger = logger.bind(component="resume_parser")

    async def parse(
        self,
        file_path: str | Path,
    ) -> ResumeExtracted:
        """Parse resume file (DOCX or PDF).
        
        Args:
            file_path: Path to resume file
            
        Returns:
            ResumeExtracted with structured data
            
        Example:
            >>> parser = ResumeParser()
            >>> resume = await parser.parse("candidate_resume.pdf")
            >>> print(resume.full_name)
            >>> print(resume.work_experience)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path}")

        start_time = time.monotonic()
        self.logger.info("resume_parse_start", file_path=str(file_path))

        try:
            result = await asyncio.to_thread(self._parse_sync, file_path)
            duration_ms = (time.monotonic() - start_time) * 1000
            self.logger.info(
                "resume_parse_complete",
                file_path=str(file_path),
                duration_ms=round(duration_ms, 2),
                work_positions=result.total_positions,
                education_count=len(result.education),
                skill_count=result.skill_count,
                confidence=result.extraction_confidence,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self.logger.exception(
                "resume_parse_failed",
                error=str(e),
                file_path=str(file_path),
                duration_ms=round(duration_ms, 2),
            )
            raise

    def _parse_sync(self, file_path: Path) -> ResumeExtracted:
        """Synchronous resume parsing (runs in thread pool)."""
        file_ext = file_path.suffix.lower()
        
        if file_ext == ".pdf":
            return self._parse_pdf(file_path)
        elif file_ext == ".docx":
            return self._parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported resume format: {file_ext}")

    def _parse_pdf(self, file_path: Path) -> ResumeExtracted:
        """Parse PDF resume using smartresume."""
        try:
            from smartresume import Resume
            
            # Load resume using smartresume
            resume = Resume.from_pdf(str(file_path))
            
            return self._convert_smartresume(resume)
        except ImportError:
            self.logger.warning("smartresume_not_available, using fallback")
            return self._parse_pdf_fallback(file_path)
        except Exception as e:
            self.logger.warning("smartresume_failed", error=str(e), fallback=True)
            return self._parse_pdf_fallback(file_path)

    def _parse_docx(self, file_path: Path) -> ResumeExtracted:
        """Parse DOCX resume using smartresume."""
        try:
            from smartresume import Resume
            
            # Load resume using smartresume
            resume = Resume.from_docx(str(file_path))
            
            return self._convert_smartresume(resume)
        except ImportError:
            self.logger.warning("smartresume_not_available, using fallback")
            return self._parse_docx_fallback(file_path)
        except Exception as e:
            self.logger.warning("smartresume_failed", error=str(e), fallback=True)
            return self._parse_docx_fallback(file_path)

    def _convert_smartresume(self, resume: Any) -> ResumeExtracted:
        """Convert smartresume object to ResumeExtracted schema."""
        # Extract work experience
        work_experience = []
        for exp in getattr(resume, "experience", []) or []:
            work_experience.append(
                WorkExperienceExtracted(
                    job_title=exp.get("title", "Unknown"),
                    company=exp.get("company", "Unknown"),
                    location=exp.get("location"),
                    start_date=self._parse_date(exp.get("start_date")),
                    end_date=self._parse_date(exp.get("end_date")) if not exp.get("current") else None,
                    is_current=exp.get("current", False),
                    description=exp.get("description"),
                    achievements=exp.get("achievements"),
                    duration_months=exp.get("duration_months"),
                    industry=exp.get("industry"),
                )
            )
        self.logger.debug(
            "resume_section_extracted",
            section="work_experience",
            count=len(work_experience),
        )

        # Extract education
        education = []
        for edu in getattr(resume, "education", []) or []:
            education.append(
                EducationExtracted(
                    degree=edu.get("degree", "Unknown"),
                    institution=edu.get("institution", "Unknown"),
                    field_of_study=edu.get("field_of_study"),
                    start_date=self._parse_date(edu.get("start_date")),
                    end_date=self._parse_date(edu.get("end_date")),
                    gpa=Decimal(str(edu["gpa"])) if edu.get("gpa") else None,
                )
            )
        self.logger.debug(
            "resume_section_extracted",
            section="education",
            count=len(education),
        )

        # Determine current employer
        current_position = next((exp for exp in work_experience if exp.is_current), None)
        current_employer = current_position.company if current_position else None
        current_job_title = current_position.job_title if current_position else None

        # Determine highest degree
        degree_hierarchy = ["PhD", "Master", "Bachelor", "Associate", "High School"]
        highest_degree = None
        for degree_level in degree_hierarchy:
            for edu in education:
                if degree_level.lower() in edu.degree.lower():
                    highest_degree = edu.degree
                    break
            if highest_degree:
                break

        return ResumeExtracted(
            full_name=getattr(resume, "name", "Unknown"),
            email=getattr(resume, "email"),
            phone=getattr(resume, "phone"),
            location=getattr(resume, "location"),
            summary=getattr(resume, "summary"),
            years_of_experience=getattr(resume, "years_of_experience"),
            work_experience=work_experience,
            total_positions=len(work_experience),
            current_employer=current_employer,
            current_job_title=current_job_title,
            education=education,
            highest_degree=highest_degree,
            skills=getattr(resume, "skills", []) or [],
            skill_count=len(getattr(resume, "skills", []) or []),
            certifications=getattr(resume, "certifications", []) or [],
            extraction_confidence=0.90,  # High confidence for smartresume
            raw_extracted_data={"source": "smartresume"},
            source_coordinates={},
        )

    def _parse_pdf_fallback(self, file_path: Path) -> ResumeExtracted:
        """Fallback PDF parsing using pymupdf4llm + regex."""
        import pymupdf4llm
        
        # Extract text
        text = pymupdf4llm.to_markdown(str(file_path))
        
        return self._extract_from_text(text)

    def _parse_docx_fallback(self, file_path: Path) -> ResumeExtracted:
        """Fallback DOCX parsing using python-docx."""
        try:
            from docx import Document
            
            doc = Document(str(file_path))
            text = "\n".join([para.text for para in doc.paragraphs])
            
            return self._extract_from_text(text)
        except ImportError:
            raise ImportError("python-docx is required for DOCX parsing")

    def _extract_from_text(self, text: str) -> ResumeExtracted:
        """Extract resume data from plain text using regex patterns."""
        # Extract email
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        email = email_match.group(0) if email_match else None
        
        # Extract phone (various formats)
        phone_match = re.search(r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}", text)
        phone = phone_match.group(0) if phone_match else None
        
        # Extract name (first non-empty line, usually)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        full_name = lines[0] if lines else "Unknown"
        
        # Extract skills (common keywords)
        skill_keywords = [
            "Python", "Java", "JavaScript", "SQL", "AWS", "Docker", "Kubernetes",
            "React", "Node.js", "Machine Learning", "Data Analysis", "Project Management",
        ]
        skills = [skill for skill in skill_keywords if skill.lower() in text.lower()]
        
        return ResumeExtracted(
            full_name=full_name,
            email=email,
            phone=phone,
            location=None,
            summary=None,
            years_of_experience=None,
            work_experience=[],
            total_positions=0,
            current_employer=None,
            current_job_title=None,
            education=[],
            highest_degree=None,
            skills=skills,
            skill_count=len(skills),
            certifications=[],
            extraction_confidence=0.60,  # Lower confidence for fallback
            raw_extracted_data={"source": "regex_fallback", "text_length": len(text)},
            source_coordinates={},
        )

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse date string to date object."""
        if not date_str:
            return None
        
        # Try common date formats
        formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %Y", "%b %Y"]
        for fmt in formats:
            try:
                return date.fromisoformat(date_str)
            except ValueError:
                continue
        
        return None
