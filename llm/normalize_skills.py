# llm/normalize_skills.py
from fast_heuristics import extract_skills_fast

def normalize_skills_batch(texts, batch_size=8, logger=None):
    return [extract_skills_fast(t) for t in texts]