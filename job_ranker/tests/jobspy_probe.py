from jobspy import scrape_jobs

print("Starting JobSpy probe...")

try:
    jobs = scrape_jobs(
        site_name=["indeed"],
        search_term="mlops engineer",
        location="India",
        results_wanted=5,
    )

    if jobs is None:
        print("Returned None")
    elif isinstance(jobs, list):
        print(f"Returned {len(jobs)} jobs")
        print(jobs[0] if jobs else "Empty list")
    else:
        print("Returned type:", type(jobs))

except Exception as e:
    print("Exception:", repr(e))