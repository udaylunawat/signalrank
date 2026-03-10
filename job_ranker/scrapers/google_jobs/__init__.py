"""Google Jobs Scraper — standalone scraper for Google Jobs (udm=8)."""
from .scraper import GoogleJobsScraper
from .model import Job

__all__ = ["GoogleJobsScraper", "Job"]
__version__ = "0.1.0"
