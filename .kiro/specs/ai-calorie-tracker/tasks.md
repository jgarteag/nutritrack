# Implementation Plan: AI Calorie Tracker

## Overview

This plan implements the AI Calorie Tracker as a serverless Python backend with a vanilla JavaScript SPA frontend. The approach follows Clean Architecture (domain → use cases → infrastructure) with TDD, then builds the frontend, Terraform infrastructure, and integration tests. Tasks are ordered to build foundational layers first, enabling incremental testing at each step.

## Tasks

- [x] 1. Project scaffolding and domain layer implementation
  - Set up Python project structure: `src/nutritrack/domain/`, `src/nutritrack/use_cases/`, `src/nutritrack/infrastructure/`, `tests/unit/`, `tests/integration/`
  - Create `pyproject.toml` with dependencies (boto3, openai, pytest, pytest-asyncio)
  - Implement domain enums: `GoalStatus`, `Sex`, `ActivityLevel` with `ACTIVITY_MULTIPLIERS`
  - Implement frozen dataclasses: `FoodEntry`, `UserProfile`, `WeightRecord`, `DailyGoal`, `DailySummary`
  - Implement pure functions: `calculate_bmr()`, `calculate_tdee()`, `suggest_calorie_goal()`
  - Implement `DailyGoal.evaluate()` method
  - Requirements: 9

- [x] 2. Domain layer unit tests
  - Create `tests/unit/test_domain.py`
  - Write BMR tests: known values for male/female, verify formula correctness
  - Write TDEE tests: all 5 activity levels, verify multipliers applied correctly
  - Write monotonicity property tests: weight, height, activity level increasing → TDEE increasing
  - Write `suggest_calorie_goal` tests: normal deficit, safety floor at 1200, boundaries at 300 and 500
  - Write `DailyGoal.evaluate` tests: total < goal, total == goal, total > goal
  - Write determinism and male > female (difference = 166) property tests
  - Requirements: 9, 2

- [x] 3. Application layer — use cases and ports
  - Create Protocol-based ports: `ImageAnalyzer`, `EntryRepository`, `UserProfileRepository`
  - Create result dataclasses: `FoodAnalysisResult`, `OnboardingResult`, `WeightUpdateResult`, `AddEntryResult`
  - Create custom exceptions: `FoodNotRecognizedError`, `InvalidImageError`, `AIServiceUnavailableError`, `PersistenceError`
  - Implement `add_food_entry()` use case with input validation
  - Implement `get_daily_summary()` use case
  - Implement `complete_onboarding()` use case
  - Implement `update_weight()` use case
  - Requirements: 9, 3, 2, 7

- [x] 4. Use case unit tests
  - Create mock implementations of all Protocol ports
  - Write `add_food_entry` tests: happy path, empty image, image too large, food not recognized
  - Write `get_daily_summary` tests: entries exist, no entries, total equals sum
  - Write `complete_onboarding` tests: happy path, invalid inputs rejected
  - Write `update_weight` tests: happy path, no profile error, preserves non-weight fields
  - Requirements: 9

- [x] 5. Infrastructure layer — DynamoDB repositories
  - Implement `DynamoDBEntryRepository`: `save_entry()` (PutItem), `get_entries_by_date()` (Query with begins_with)
  - Implement `DynamoDBUserProfileRepository`: `get_profile()`, `save_profile()`, `save_weight_record()`, `get_weight_history()`
  - Use single-table design: PK=`USER#default`, SK patterns for PROFILE, WEIGHT#date, DATE#date#ENTRY#uuid
  - Add serialization/deserialization helpers for enum values and DynamoDB types
  - Requirements: 8, 9

- [x] 6. Infrastructure layer — OpenAI image analyzer
  - Implement `OpenAIImageAnalyzer` with GPT-4o-mini model
  - Build system prompt for structured JSON response (food_name, estimated_calories, confidence)
  - Implement base64 image encoding in API call
  - Add JSON response parsing with validation (calories >= 0, confidence 0–1)
  - Handle "not_food" responses as `FoodNotRecognizedError`
  - Implement exponential backoff retry (max 3) for rate limits and network errors
  - Requirements: 3

- [x] 7. Lambda handler and API routing
  - Implement single Lambda handler routing by HTTP method + path
  - Route handlers: POST /entries, GET /summary, GET /profile, POST /profile, PUT /profile/goal, POST /weight, GET /weight/history, GET /summary/week
  - Map exceptions to HTTP status codes: 400, 404, 409, 413, 503
  - Add CORS headers to all responses
  - Initialize dependencies from environment variables
  - Requirements: 10, 3, 4

- [x] 8. Terraform infrastructure
  - Create DynamoDB table (PK String, SK String, PAY_PER_REQUEST)
  - Create Lambda function (Python 3.12, ARM64, 128MB, 30s timeout) with IAM role
  - Create API Gateway HTTP API with all route integrations and JWT authorizer
  - Create Cognito User Pool (no self-registration), App Client (USER_PASSWORD_AUTH), initial user
  - Create S3 bucket for SPA hosting and CloudFront distribution
  - Define variables (OpenAI key, region, username/password) and outputs (API URL, CloudFront domain, Pool/Client IDs)
  - Requirements: 8

- [x] 9. Frontend — HTML structure and dark mode CSS
  - Create `index.html` with all screen sections (login, onboarding, dashboard, weekly, weight, settings)
  - Implement dark mode design system: primary #1a1a2e, secondary #16213e, tertiary #0f3460
  - Define CSS animations: fadeInUp, shake, pulse, slideLeft, slideRight
  - Include Chart.js and Canvas Confetti from CDN
  - Ensure responsive layout and accessible ARIA labels
  - Requirements: 1, 2, 4, 5

- [x] 10. Frontend — authentication and navigation JavaScript
  - Implement Cognito InitiateAuth (USER_PASSWORD_AUTH) login flow
  - Store JWT tokens in module-scoped memory variables
  - Implement token refresh logic before access token expiry
  - Add `Authorization: Bearer` header to all API calls
  - Implement screen navigation with CSS slide transitions
  - Handle login errors with inline messages
  - Requirements: 1

- [x] 11. Frontend — onboarding flow JavaScript
  - Check profile status on login (GET /profile → 404 triggers onboarding)
  - Implement multi-step form: weight/height → age/sex → activity level
  - Add client-side validation (weight 30–300, height 100–250, age 13–120)
  - Submit to POST /profile and display TDEE result with suggested goal
  - Implement goal accept/adjust with PUT /profile/goal
  - Navigate to dashboard after completion
  - Requirements: 2

- [x] 12. Frontend — dashboard and food entry JavaScript
  - Render progress ring as Chart.js doughnut with animated counter (requestAnimationFrame)
  - Implement color transitions: green → orange (>80%) → red (exceeded)
  - Implement camera/gallery image capture and base64 encoding
  - Submit to POST /entries with loading spinner
  - Render entry list with fadeInUp animation
  - Trigger Canvas Confetti on goal met, shake on exceeded
  - Refresh daily summary on load and after each entry
  - Requirements: 3, 4, 5

- [x] 13. Frontend — weekly chart and weight tracker JavaScript
  - Render weekly bar chart (Chart.js) with color-coded bars and goal line
  - Render weight line chart with bezier curves and gradient fill
  - Implement weight form submission (POST /weight) with TDEE update display
  - Implement accept/keep goal logic after weight update
  - Refresh charts on screen navigation
  - Requirements: 6, 7

- [x] 14. Integration tests
  - Write DynamoDB repository integration tests using moto: save/retrieve entries, profiles, weight records
  - Write Lambda handler integration tests: verify routing, status codes, CORS headers
  - Write error handling tests: 400, 404, 409, 413, 503 responses
  - Write end-to-end flow test: onboarding → add entry → get summary
  - Requirements: 9

- [x] 15. Deployment packaging and final wiring
  - Create Lambda deployment package (zip from src/nutritrack/)
  - Create `frontend/config.js` template with API URL and Cognito config placeholders
  - Update frontend JS to read from `window.APP_CONFIG`
  - Update `.gitignore` with .terraform/, *.tfstate*, __pycache__/, *.zip, .env
  - Write README.md with setup, deployment steps, and environment variable documentation
  - Verify `terraform plan` runs without errors
  - Requirements: 8, 10

## Task Dependency Graph

```json
{
  "waves": [
    [1, 9],
    [2, 3, 10],
    [4, 5, 6, 11, 12],
    [7, 13],
    [8, 14],
    [15]
  ]
}
```

## Notes

- Tasks 1–4 form the TDD core: domain logic is fully tested before infrastructure code.
- Tasks 5–7 build the backend infrastructure adapters and Lambda entry point.
- Task 8 (Terraform) can be started in parallel with frontend tasks (9–13) since they are independent.
- Task 9 (HTML/CSS) is independent and can start anytime — it has no backend dependency.
- Task 15 is the final integration step that wires everything together.
- All frontend code uses vanilla JS with no build step for zero deployment complexity.
