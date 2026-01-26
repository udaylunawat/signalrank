import pandas as pd
import subprocess
import os

# Step 1: Read CSV and drop 'description' column
input_path = "outputs/ranked_jobs.csv"
output_path = "ranked_jobs_head.csv"

df = pd.read_csv(input_path)
if 'description' in df.columns:
    df = df.drop(columns=['description', 'company_url', 'job_url', 'job_url_direct', 'company_logo'], errors='ignore')

# Step 2: Write first 5 rows (plus header)
df.head(5).to_csv(output_path, index=False)

# Step 3: Remove digest.txt if it exists
if os.path.exists("digest.txt"):
    os.remove("digest.txt")

# Step 4: Run gitingest with exclusions
subprocess.run([
    "gitingest",
    "-e", "ranked_jobs.csv",
    "-e", "cache/*",
    "-e", "*.tex",
    "-e", "corpus/*",
    "-e", "outputs/*"
])