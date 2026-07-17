# Phase 2 — Frozen catalog collection

Collected at 2026-07-16T19:33:12.578203+00:00.

## Summary

- Frozen catalog size: **1238** active jobs.
- Source totals: himalayas: 20, indeed: 760, jobicy: 419, remotive: 39.
- Source terminal statuses: error: 64, success: 69.
- JobSpy used its bounded request and refresh budgets. An `error` or `empty` report is valid telemetry and does not invalidate the frozen catalog.

## Source telemetry

| Category | Source | Query | Location | Status | Found | Persisted | ms | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Data science | remotive | — | Remote | success | 39 | 39 | 177 | — |
| Data science | himalayas | Data Scientist | Remote | success | 20 | 20 | 1398 | — |
| Data science | jobicy | Data Scientist | Remote | success | 47 | 47 | 806 | — |
| Data science | himalayas | Data Analyst | Remote | success | 20 | 20 | 1565 | — |
| Data science | jobicy | Data Analyst | Remote | success | 50 | 50 | 884 | — |
| Data science | himalayas | Analytics Engineer | Remote | success | 20 | 20 | 778 | — |
| Data science | jobicy | Analytics Engineer | Remote | success | 50 | 50 | 876 | — |
| Data science | indeed | Data Scientist | India | success | 50 | 50 | 753 | — |
| Data science | linkedin | Data Scientist | India | error | 0 | 0 | 32020 | JobSpy request exceeded 15.0 seconds |
| Data science | indeed | Data Analyst | India | success | 50 | 50 | 1534 | — |
| Data science | linkedin | Data Analyst | India | error | 0 | 0 | 32012 | JobSpy request exceeded 15.0 seconds |
| Data science | indeed | Analytics Engineer | India | success | 50 | 50 | 762 | — |
| Data science | linkedin | Analytics Engineer | India | error | 0 | 0 | 16912 | JobSpy refresh time budget exceeded |
| Data science | indeed | Data Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Data science | linkedin | Data Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Data science | indeed | ML Scientist | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Data science | linkedin | ML Scientist | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Data science | indeed | BI Analyst | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Data science | linkedin | BI Analyst | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| AI | remotive | — | Remote | success | 39 | 39 | 173 | — |
| AI | himalayas | AI Engineer | Remote | success | 20 | 20 | 1600 | — |
| AI | jobicy | AI Engineer | Remote | success | 50 | 50 | 1116 | — |
| AI | himalayas | ML Engineer | Remote | success | 20 | 20 | 1528 | — |
| AI | jobicy | ML Engineer | Remote | success | 50 | 50 | 904 | — |
| AI | himalayas | LLM Engineer | Remote | success | 20 | 20 | 1394 | — |
| AI | jobicy | LLM Engineer | Remote | success | 50 | 50 | 837 | — |
| AI | indeed | AI Engineer | India | success | 50 | 50 | 746 | — |
| AI | linkedin | AI Engineer | India | error | 0 | 0 | 32014 | JobSpy request exceeded 15.0 seconds |
| AI | indeed | ML Engineer | India | success | 50 | 50 | 1014 | — |
| AI | linkedin | ML Engineer | India | error | 0 | 0 | 32013 | JobSpy request exceeded 15.0 seconds |
| AI | indeed | LLM Engineer | India | success | 50 | 50 | 902 | — |
| AI | linkedin | LLM Engineer | India | error | 0 | 0 | 17308 | JobSpy request exceeded 0.3 seconds |
| AI | indeed | MLOps Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| AI | linkedin | MLOps Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| AI | indeed | Applied Scientist | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| AI | linkedin | Applied Scientist | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| AI | indeed | NLP Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| AI | linkedin | NLP Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Forward-deployed engineering | remotive | — | Remote | success | 39 | 39 | 173 | — |
| Forward-deployed engineering | himalayas | Forward Deployed Engineer | Remote | success | 20 | 20 | 1513 | — |
| Forward-deployed engineering | jobicy | Forward Deployed Engineer | Remote | success | 10 | 10 | 600 | — |
| Forward-deployed engineering | himalayas | Solutions Engineer | Remote | success | 20 | 20 | 821 | — |
| Forward-deployed engineering | jobicy | Solutions Engineer | Remote | success | 50 | 50 | 1000 | — |
| Forward-deployed engineering | himalayas | Customer Engineer | Remote | success | 20 | 20 | 969 | — |
| Forward-deployed engineering | jobicy | Customer Engineer | Remote | success | 50 | 50 | 989 | — |
| Forward-deployed engineering | indeed | Forward Deployed Engineer | India | success | 50 | 50 | 819 | — |
| Forward-deployed engineering | linkedin | Forward Deployed Engineer | India | error | 0 | 0 | 32018 | JobSpy request exceeded 15.0 seconds |
| Forward-deployed engineering | indeed | Solutions Engineer | India | success | 50 | 50 | 755 | — |
| Forward-deployed engineering | linkedin | Solutions Engineer | India | error | 0 | 0 | 32017 | JobSpy request exceeded 15.0 seconds |
| Forward-deployed engineering | indeed | Customer Engineer | India | success | 50 | 50 | 811 | — |
| Forward-deployed engineering | linkedin | Customer Engineer | India | error | 0 | 0 | 17580 | JobSpy request exceeded 0.6 seconds |
| Forward-deployed engineering | indeed | Implementation Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Forward-deployed engineering | linkedin | Implementation Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Forward-deployed engineering | indeed | Technical Consultant | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Forward-deployed engineering | linkedin | Technical Consultant | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Forward-deployed engineering | indeed | Deployment Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Forward-deployed engineering | linkedin | Deployment Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| SAP | remotive | — | Remote | success | 39 | 39 | 103 | — |
| SAP | himalayas | SAP Consultant | Remote | success | 20 | 20 | 826 | — |
| SAP | jobicy | SAP Consultant | Remote | success | 13 | 13 | 675 | — |
| SAP | himalayas | SAP S 4HANA Consultant | Remote | success | 20 | 20 | 1439 | — |
| SAP | jobicy | SAP S 4HANA Consultant | Remote | success | 1 | 1 | 672 | — |
| SAP | himalayas | SAP FICO | Remote | success | 20 | 20 | 1529 | — |
| SAP | jobicy | SAP FICO | Remote | error | 0 | 0 | 672 | Client error '404 Not Found' for url 'https://jobicy.com/api/v2/remote-jobs?count=50&tag=SAP+FICO'<br>For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404 |
| SAP | indeed | SAP Consultant | India | success | 50 | 50 | 671 | — |
| SAP | linkedin | SAP Consultant | India | error | 0 | 0 | 32011 | JobSpy request exceeded 15.0 seconds |
| SAP | indeed | SAP S 4HANA Consultant | India | success | 46 | 46 | 920 | — |
| SAP | linkedin | SAP S 4HANA Consultant | India | error | 0 | 0 | 32017 | JobSpy request exceeded 15.0 seconds |
| SAP | indeed | SAP FICO | India | success | 50 | 50 | 852 | — |
| SAP | linkedin | SAP FICO | India | error | 0 | 0 | 17526 | JobSpy request exceeded 0.5 seconds |
| SAP | indeed | SAP ABAP | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| SAP | linkedin | SAP ABAP | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| SAP | indeed | SAP Fiori | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| SAP | linkedin | SAP Fiori | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| SAP | indeed | SAP Basis | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| SAP | linkedin | SAP Basis | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Innovation | remotive | — | Remote | success | 39 | 39 | 113 | — |
| Innovation | himalayas | Innovation Manager | Remote | success | 20 | 20 | 1017 | — |
| Innovation | jobicy | Innovation Manager | Remote | success | 50 | 50 | 937 | — |
| Innovation | himalayas | Digital Transformation Manager | Remote | success | 20 | 20 | 1490 | — |
| Innovation | jobicy | Digital Transformation Manager | Remote | success | 50 | 50 | 787 | — |
| Innovation | himalayas | Innovation Strategist | Remote | success | 20 | 20 | 1007 | — |
| Innovation | jobicy | Innovation Strategist | Remote | success | 7 | 7 | 696 | — |
| Innovation | indeed | Innovation Manager | India | success | 50 | 50 | 695 | — |
| Innovation | linkedin | Innovation Manager | India | error | 0 | 0 | 32023 | JobSpy request exceeded 15.0 seconds |
| Innovation | indeed | Digital Transformation Manager | India | success | 50 | 50 | 841 | — |
| Innovation | linkedin | Digital Transformation Manager | India | error | 0 | 0 | 32014 | JobSpy request exceeded 15.0 seconds |
| Innovation | indeed | Innovation Strategist | India | success | 50 | 50 | 1042 | — |
| Innovation | linkedin | Innovation Strategist | India | error | 0 | 0 | 17378 | JobSpy request exceeded 0.4 seconds |
| Innovation | indeed | Product Innovation Manager | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Innovation | linkedin | Product Innovation Manager | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Innovation | indeed | Venture Builder | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Innovation | linkedin | Venture Builder | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Innovation | indeed | R&D Manager | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Innovation | linkedin | R&D Manager | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Testing | remotive | — | Remote | success | 39 | 39 | 103 | — |
| Testing | himalayas | QA Automation Engineer | Remote | success | 20 | 20 | 773 | — |
| Testing | jobicy | QA Automation Engineer | Remote | success | 24 | 24 | 776 | — |
| Testing | himalayas | SDET | Remote | success | 20 | 20 | 883 | — |
| Testing | jobicy | SDET | Remote | success | 5 | 5 | 592 | — |
| Testing | himalayas | Test Automation Engineer | Remote | success | 20 | 20 | 896 | — |
| Testing | jobicy | Test Automation Engineer | Remote | success | 50 | 50 | 1078 | — |
| Testing | indeed | QA Automation Engineer | India | success | 50 | 50 | 770 | — |
| Testing | linkedin | QA Automation Engineer | India | error | 0 | 0 | 32013 | JobSpy request exceeded 15.0 seconds |
| Testing | indeed | SDET | India | success | 50 | 50 | 606 | — |
| Testing | linkedin | SDET | India | error | 0 | 0 | 32018 | JobSpy request exceeded 15.0 seconds |
| Testing | indeed | Test Automation Engineer | India | success | 50 | 50 | 693 | — |
| Testing | linkedin | Test Automation Engineer | India | error | 0 | 0 | 17901 | JobSpy request exceeded 0.9 seconds |
| Testing | indeed | QA Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Testing | linkedin | QA Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Testing | indeed | Software Engineer in Test | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Testing | linkedin | Software Engineer in Test | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Testing | indeed | API Test Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Testing | linkedin | API Test Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Frontend | remotive | — | Remote | success | 39 | 39 | 169 | — |
| Frontend | himalayas | Frontend Developer | Remote | success | 20 | 20 | 1552 | — |
| Frontend | jobicy | Frontend Developer | Remote | success | 22 | 22 | 672 | — |
| Frontend | himalayas | Front-End Engineer | Remote | success | 20 | 20 | 1415 | — |
| Frontend | jobicy | Front-End Engineer | Remote | success | 11 | 11 | 631 | — |
| Frontend | himalayas | React Developer | Remote | success | 20 | 20 | 1395 | — |
| Frontend | jobicy | React Developer | Remote | success | 37 | 37 | 875 | — |
| Frontend | indeed | Frontend Developer | India | success | 50 | 50 | 871 | — |
| Frontend | linkedin | Frontend Developer | India | error | 0 | 0 | 32014 | JobSpy request exceeded 15.0 seconds |
| Frontend | indeed | Front-End Engineer | India | success | 50 | 50 | 605 | — |
| Frontend | linkedin | Front-End Engineer | India | error | 0 | 0 | 32016 | JobSpy request exceeded 15.0 seconds |
| Frontend | indeed | React Developer | India | success | 50 | 50 | 720 | — |
| Frontend | linkedin | React Developer | India | error | 0 | 0 | 17773 | JobSpy request exceeded 0.8 seconds |
| Frontend | indeed | UI Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Frontend | linkedin | UI Engineer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Frontend | indeed | JavaScript Developer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Frontend | linkedin | JavaScript Developer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Frontend | indeed | TypeScript Developer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
| Frontend | linkedin | TypeScript Developer | India | error | 0 | 0 | 0 | JobSpy refresh time budget exceeded |
