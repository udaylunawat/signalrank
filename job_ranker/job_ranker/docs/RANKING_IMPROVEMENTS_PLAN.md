# Job Ranker - Ranking Improvements Plan

## Objective
Enhance the ranking correctness of the Job Ranker system to better align with the user's profile: "Senior AI Platform Engineer | Cloud Infrastructure | MLOps | Agentic Systems". The goal is to prioritize platform-heavy and production agentic systems roles, while de-prioritizing generic data science, junior ML, customer-facing, and unsuitable company roles.

## Problem Statement
The current scoring mechanism in `domain/scoring.py` has limitations:
*   `seniority_penalty` only penalizes junior roles; it doesn't explicitly boost senior-level roles.
*   No explicit mechanism to heavily boost jobs featuring core competencies like "AI Platform," "MLOps," "Agentic Systems," "GenAI," "CI/CD," "Cloud Infrastructure," and "Governance."
*   Lack of robust negative keyword filters to penalize roles clearly outside the target (e.g., "pure DS," "customer-facing," specific undesired companies).
*   Insufficient role categorization to prioritize platform-heavy roles and de-prioritize others.

## Proposed Improvements

### 1. Refactor `seniority_penalty` to `calculate_seniority_score`
*   **Location:** `domain/scoring.py`
*   **Changes:**
    *   Rename the function `seniority_penalty` to `calculate_seniority_score`.
    *   Add `years_of_experience` as a parameter to this function.
    *   Retain existing junior penalties.
    *   Introduce logic to **boost** jobs with configurable keywords like "Senior," "Lead," "Staff," "Principal" in titles/descriptions, especially when `extract_required_yoe` aligns with the user's 7 years of experience.

### 2. Implement `calculate_role_and_skill_match_score`
*   **Location:** `domain/scoring.py`
*   **Changes:**
    *   Create a new function `calculate_role_and_skill_match_score`.
    *   Implement **strong boosts** for configurable positive keywords/phrases (e.g., "AI Platform", "MLOps", "Agentic AI", "LangGraph", "Kubernetes", "FinOps", "Governance", "CI/CD", "Cloud Infrastructure", "DevOps").
    *   Implement **penalties/filters** for configurable negative keywords/phrases (e.g., "Data Scientist" (unless combined with "Platform"), "Frontend", "React", "Tableau", "QA", "Tester", "Customer Support", "Sales Engineer", "Pre-sales", and potentially specific companies like "TCS", "Virtusa" if added to configuration).
    *   Integrate existing `role_negative_keywords` and `functional_role_penalties` from `config/base.yaml` into this new score.

### 3. Integrate New Scores into `batch/ranker.py`
*   **Location:** `batch/ranker.py`
*   **Changes:**
    *   Update the import statements for the modified and new functions from `domain/scoring.py`.
    *   Modify the call to the renamed `calculate_seniority_score` function, passing `years_of_experience` (which will need to be derived from the user's resume or a configuration).
    *   Add `calculate_role_and_skill_match_score` as a new multiplier in the `final_score` calculation.

### 4. Update `config/base.yaml`
*   **Location:** `config/base.yaml`
*   **Changes:**
    *   Under the `ranking` section, add new configuration parameters:
        *   `seniority_boosting_keywords`: A list of keywords (e.g., "senior", "lead", "staff", "principal") and their associated boost multipliers.
        *   `positive_skill_keywords`: A dictionary of core skill/role keywords with their associated boost multipliers.
        *   `negative_role_keywords`: A list of keywords/phrases that indicate an unsuitable role and their associated penalty multipliers.
        *   `yoe_match_boost`: A boost applied when `extract_required_yoe` from the job description aligns closely with the user's `years_of_experience`.

## Implementation Steps (Sequential)

1.  **Refactor `seniority_penalty` to `calculate_seniority_score` in `domain/scoring.py`.** (This was previously attempted and cancelled, will resume after plan is saved).
2.  **Add `calculate_role_and_skill_match_score` to `domain/scoring.py`.**
3.  **Update `config/base.yaml` with new scoring parameters.**
4.  **Integrate new scoring functions into `batch/ranker.py` and update imports.**
5.  **Run tests and verify changes.**
