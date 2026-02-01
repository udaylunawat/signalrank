CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  user TEXT,
  use_case TEXT,
  config_fingerprint TEXT,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  status TEXT
);

CREATE TABLE IF NOT EXISTS jobs_raw (
  job_url TEXT,
  title TEXT,
  company TEXT,
  description TEXT,
  location TEXT,
  site TEXT,
  date_posted TIMESTAMP,
  user TEXT,
  use_case TEXT,
  ingested_at TIMESTAMP,
  PRIMARY KEY (job_url, user, use_case)
);

CREATE TABLE IF NOT EXISTS embeddings (
  text_fp TEXT,
  cfg_fp TEXT,
  vector FLOAT[],
  user TEXT,
  use_case TEXT,
  PRIMARY KEY (text_fp, cfg_fp, user, use_case)
);

CREATE TABLE IF NOT EXISTS run_results (
  run_id TEXT,
  job_url TEXT,
  final_score DOUBLE,
  payload JSON
);

CREATE TABLE IF NOT EXISTS annotations (
  user TEXT,
  use_case TEXT,
  job_url TEXT,
  starred BOOLEAN,
  hidden BOOLEAN,
  updated_at TIMESTAMP,
  PRIMARY KEY (user, use_case, job_url)
);

CREATE TABLE IF NOT EXISTS resume_distillations (
  resume_fp TEXT,
  user TEXT,
  use_case TEXT,
  payload JSON,
  created_at TIMESTAMP,
  PRIMARY KEY (resume_fp, user, use_case)
);