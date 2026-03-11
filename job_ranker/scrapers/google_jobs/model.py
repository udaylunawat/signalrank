"""Data models for Google Jobs scraper."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    description: str
    job_url: Optional[str] = None
    date_posted: Optional[date] = None
    is_remote: bool = False
    job_type: Optional[str] = None
    salary: Optional[str] = None
    source: str = "google"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "job_url": self.job_url,
            "date_posted": str(self.date_posted) if self.date_posted else None,
            "is_remote": self.is_remote,
            "job_type": self.job_type,
            "salary": self.salary,
            "source": self.source,
        }
