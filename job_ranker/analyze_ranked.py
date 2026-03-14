import sys
import re
import numpy as np
import pandas as pd

# --------------------------------------------------
# Load CSV
# --------------------------------------------------

if len(sys.argv) < 2:
    print("Usage: python analyze_ranked.py ranked_jobs_xxx.csv")
    exit()

filename = sys.argv[1]
df = pd.read_csv(filename)

print(f"\nLoaded {len(df)} rows from {filename}")

TOP_N = 200  # evaluate ranking quality here

# --------------------------------------------------
# Basic Score Analytics
# --------------------------------------------------

if "final_score" in df.columns:
    print("\n=== SCORE DISTRIBUTION (GLOBAL) ===")
    print(df["final_score"].describe())

    print("\n=== SCORE DISTRIBUTION (TOP 200) ===")
    print(df.head(TOP_N)["final_score"].describe())

    print("\nTop 10 scores:")
    print(df[["title", "company", "final_score"]].head(10))

# --------------------------------------------------
# Company Distribution
# --------------------------------------------------

print("\n=== TOP COMPANIES (GLOBAL) ===")
print(df["company"].value_counts().head(15))

print(f"\n=== TOP COMPANIES (TOP {TOP_N}) ===")
print(df.head(TOP_N)["company"].value_counts().head(15))

# --------------------------------------------------
# Location Distribution
# --------------------------------------------------

if "location" in df.columns:
    print("\n=== TOP LOCATIONS (TOP 200) ===")
    print(df.head(TOP_N)["location"].value_counts().head(15))

# --------------------------------------------------
# Role Breakdown
# --------------------------------------------------

if "role" in df.columns:
    print("\n=== ROLE DISTRIBUTION (GLOBAL) ===")
    print(df["role"].value_counts())

    print(f"\n=== ROLE DISTRIBUTION (TOP {TOP_N}) ===")
    print(df.head(TOP_N)["role"].value_counts())

# --------------------------------------------------
# Site Distribution
# --------------------------------------------------

if "site" in df.columns:
    print(f"\n=== SITE DISTRIBUTION (TOP {TOP_N}) ===")
    print(df.head(TOP_N)["site"].value_counts())

# --------------------------------------------------
# Experience Signal Mining (FIXED REGEX)
# --------------------------------------------------

print("\n=== EXPERIENCE SIGNALS (TOP 200) ===")

def extract_yoe(text):
    # Only capture 1–2 digit experience values
    matches = re.findall(r"\b([1-9]\d?)\+?\s*(?:years|yrs)\b", str(text).lower())
    return [int(m) for m in matches]

all_years = []

for desc in df.head(TOP_N).get("description", []):
    all_years.extend(extract_yoe(desc))

if all_years:
    print("Average mentioned YOE:", round(np.mean(all_years), 2))
    print("Median mentioned YOE:", np.median(all_years))
    print("Max mentioned YOE:", np.max(all_years))
else:
    print("No experience patterns detected.")

# --------------------------------------------------
# Keyword Frequency (CLEANED)
# --------------------------------------------------

print("\n=== TOP KEYWORDS (TOP 200 DESCRIPTIONS) ===")

corpus = " ".join(
    df.head(TOP_N).get("description", "").astype(str).tolist()
).lower()

tokens = re.findall(r"[a-z]{4,}", corpus)

stopwords = {
    "with", "from", "have", "that", "will", "this", "your",
    "team", "role", "work", "years", "experience", "skills",
    "business", "solutions", "development", "engineering",
    "software", "services", "strong", "across", "full",
    "time", "data"
}

tokens = [t for t in tokens if t not in stopwords]

freq = pd.Series(tokens).value_counts().head(20)

print(freq)

print("\nAnalysis complete.")