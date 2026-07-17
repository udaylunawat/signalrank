# Phase 1 — Query matrix

## Objective

Measure whether primary-lane-first ordering improves top-ten role quality without changing the catalog, resume text, extracted skills, or score weights.

## Collection controls

- JobSpy is enabled with a 15-second request deadline and a 90-second deadline per category refresh.
- Each category runs sequentially against the India location lane. Remote inventory is also collected from public remote-job APIs.
- The first three terms are intentionally the strongest public-API terms because those sources accept only the first three role queries in a refresh.
- Every source report, including empty and timed-out JobSpy calls, is included in Phase 2.

## Matrix

| Category | Search terms |
| --- | --- |
| Data science | Data Scientist; Data Analyst; Analytics Engineer; Data Engineer; ML Scientist; BI Analyst |
| AI | AI Engineer; ML Engineer; LLM Engineer; MLOps Engineer; Applied Scientist; NLP Engineer |
| FDE | Forward Deployed Engineer; Solutions Engineer; Customer Engineer; Implementation Engineer; Technical Consultant; Deployment Engineer |
| SAP | SAP Consultant; SAP S/4HANA Consultant; SAP FICO; SAP ABAP; SAP Fiori; SAP Basis |
| Innovation | Innovation Manager; Digital Transformation Manager; Innovation Strategist; Product Innovation Manager; Venture Builder; R&D Manager |
| Testing | QA Automation Engineer; SDET; Test Automation Engineer; QA Engineer; Software Engineer in Test; API Test Engineer |
| Frontend | Frontend Developer; Front-End Engineer; React Developer; UI Engineer; JavaScript Developer; TypeScript Developer |

## Metrics

- Primary-lane share in the top 10.
- Primary-first rate for candidates with one or more primary matches.
- Primary/broader ordering violations.
- Automated title-family Precision@10 proxy.
- Human-labelled Precision@10, Recall@20, and NDCG@10/20 when labels are supplied.
- Source status, duration, discovered jobs, and frozen catalog size.
