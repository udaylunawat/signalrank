# Phase 3 — Pre-fix versus post-fix ranking

Both variants use the same frozen catalog, 70 PII-free resumes, extracted skills, target roles, locations, embeddings, and score weights. The only difference is final ordering: score-only pre-fix versus primary-lane-first post-fix. Embeddings were computed locally on `mps`.

## A/B metrics

| Category | Variant | Candidates | Primary eligible | Primary top-10 share | Primary-first rate | Violations | Mean first primary rank | P@10 proxy | Mean ranked jobs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Data science | Pre-fix | 10 | 10 | 40.0% | 100.0% | 10 | 1.00 | 40.0% | 200.0 |
| Data science | Post-fix | 10 | 10 | 100.0% | 100.0% | 0 | 1.00 | 80.0% | 200.0 |
| AI | Pre-fix | 10 | 10 | 70.0% | 100.0% | 10 | 1.00 | 40.0% | 200.0 |
| AI | Post-fix | 10 | 10 | 100.0% | 100.0% | 0 | 1.00 | 50.0% | 200.0 |
| Forward-deployed engineering | Pre-fix | 10 | 10 | 10.0% | 0.0% | 10 | 10.00 | 10.0% | 200.0 |
| Forward-deployed engineering | Post-fix | 10 | 10 | 100.0% | 100.0% | 0 | 1.00 | 40.0% | 200.0 |
| SAP | Pre-fix | 10 | 10 | 100.0% | 100.0% | 10 | 1.00 | 100.0% | 200.0 |
| SAP | Post-fix | 10 | 10 | 100.0% | 100.0% | 0 | 1.00 | 100.0% | 200.0 |
| Innovation | Pre-fix | 10 | 0 | 0.0% | 0.0% | 0 | 0.00 | 10.0% | 200.0 |
| Innovation | Post-fix | 10 | 0 | 0.0% | 0.0% | 0 | 0.00 | 10.0% | 200.0 |
| Testing | Pre-fix | 10 | 10 | 70.0% | 100.0% | 10 | 1.00 | 70.0% | 200.0 |
| Testing | Post-fix | 10 | 10 | 100.0% | 100.0% | 0 | 1.00 | 90.0% | 200.0 |
| Frontend | Pre-fix | 10 | 10 | 50.0% | 100.0% | 10 | 1.00 | 20.0% | 200.0 |
| Frontend | Post-fix | 10 | 10 | 100.0% | 100.0% | 0 | 1.00 | 50.0% | 200.0 |
| Overall | Pre-fix | 70 | 60 | 48.6% | 83.3% | 60 | 2.50 | 41.4% | 200.0 |
| Overall | Post-fix | 70 | 60 | 85.7% | 100.0% | 0 | 1.00 | 60.0% | 200.0 |

An ordering violation means a broader result appears above a primary result when primary results exist.

## Post-fix top-five samples

| Category | Candidate 01 top five titles |
| --- | --- |
| Data science | Data Analyst / Data Scientist \| Python \| SQL \| Power BI \| Machine Learning<br>Senior Data Scientist AI ML<br>Data Analyst<br>Data Science Manager<br>Senior Data & Analytics Engineer |
| AI | Lead I - ML Engineering :: AI Engineer<br>GEN AI Developer<br>AI/ML Engineer<br>Data Scientist (LLM & Agentic AI)<br>AI/ML Engineer |
| Forward-deployed engineering | FDE (Forward Deployed Engineer)<br>Software Engineer<br>Forward Deployed Engineer<br>Lead I - ML Engineering :: AI Engineer<br>AI Solutions Engineer |
| SAP | SAP S/4HANA Materials Management Consultant<br>SAP S/4HANA Sales and Distribution Consultant<br>SAP BW Consultant<br>SAP FICO Consultant<br>SAP FICO Lead Consultant |
| Innovation | IOS mid-level dev<br>Lead Software Engineer- Java Fullstack<br>R&D Engineer 5, Software<br>Senior Software Engineer<br>IN_Senior Associate_Technical Product Manager_GCC_Advisory_Bnaglore |
| Testing | SDET / Test Automation Engineer<br>Software Development Engineer in Test<br>Software Development Engineer In Test / SDET<br>Senior Enterprise Software Test Engineer<br>SDET Senior Automation Tester |
| Frontend | Senior Technical Lead - Web UI (HTML, JavaScript, React.js)<br>Front-end React Engineer<br>React JS Full Stack Developer<br>Senior React Developer<br>Z2_Full stack developer - Java/Kotlin, Spring Boot, Vue/React |
