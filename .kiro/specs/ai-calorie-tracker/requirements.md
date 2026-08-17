# Requirements Document

## Introduction

This document defines the requirements for the AI Calorie Tracker feature — a personal AI-powered calorie tracking application. The user photographs food items, has them identified via GPT-4o-mini, estimates caloric content, and tracks daily intake against a personalized TDEE-based calorie goal. The system includes onboarding, weight tracking, animated charts, and deploys serverlessly on AWS with extreme cost optimization.

## Glossary

- **TDEE**: Total Daily Energy Expenditure — the total calories burned per day including activity.
- **BMR**: Basal Metabolic Rate — calories burned at rest.
- **Mifflin-St Jeor**: The formula used to calculate BMR from weight, height, age, and sex.
- **SPA**: Single Page Application — the frontend served from S3/CloudFront.
- **Clean Architecture**: Separation of domain, application, and infrastructure layers.

## Requirements

### Requirement 1: User Authentication

**User Story:** As a user, I want to log in with my username and password so that my calorie data is private and secure. As a user, I want my session to persist until I explicitly log out so I don't have to re-authenticate frequently.

#### Acceptance Criteria
- [ ] User can log in via a dark-mode login form with username and password fields
- [ ] Authentication uses AWS Cognito with USER_PASSWORD_AUTH flow
- [ ] JWT tokens (id_token, access_token, refresh_token) are stored in memory only (not localStorage)
- [ ] All API requests include the JWT access token in the Authorization header
- [ ] Token auto-refreshes before expiry using the refresh token
- [ ] Invalid credentials display an inline error message
- [ ] Self-registration is disabled — only admin-created users can authenticate
- [ ] Logout clears all tokens from memory

### Requirement 2: Onboarding & TDEE Calculation

**User Story:** As a first-time user, I want to be guided through a setup process so the app can calculate my personalized calorie goal. As a user, I want to see my calculated TDEE and suggested deficit goal so I can accept or adjust it.

#### Acceptance Criteria
- [ ] If no profile exists (GET /profile returns 404), the onboarding UI is shown
- [ ] Onboarding collects: weight (kg), height (cm), age, sex (male/female), activity level (sedentary/light/moderate/active/very_active)
- [ ] TDEE is calculated using the Mifflin-St Jeor formula: Male BMR = (10 × weight) + (6.25 × height) - (5 × age) + 5; Female BMR = same - 161; TDEE = BMR × activity multiplier
- [ ] A calorie deficit goal is suggested (TDEE - 400 kcal by default)
- [ ] The safety floor ensures no goal is suggested below 1200 kcal
- [ ] User can accept the suggested goal or adjust it manually
- [ ] Profile and initial weight record are persisted on completion
- [ ] Input validation enforces: weight 30–300 kg, height 100–250 cm, age 13–120

### Requirement 3: Food Image Analysis & Entry Creation

**User Story:** As a user, I want to photograph my food and have AI estimate the calories so I can track intake without manual data entry. As a user, I want to see the AI's confidence score so I know how reliable the estimate is.

#### Acceptance Criteria
- [ ] User can capture a photo via camera or select from gallery
- [ ] Image is sent as base64 to POST /entries with JWT authorization
- [ ] GPT-4o-mini analyzes the image and returns: food_name, estimated_calories, confidence (0–1)
- [ ] Image size is validated (max 20MB) before upload
- [ ] If the image doesn't contain recognizable food, a FoodNotRecognizedError is returned
- [ ] Entry is persisted in DynamoDB with unique ID, timestamp, and date
- [ ] Response includes the new entry plus updated daily summary (total, remaining, goal status)
- [ ] A loading spinner displays during AI analysis

### Requirement 4: Daily Calorie Tracking & Progress Display

**User Story:** As a user, I want to see my daily calorie progress in a visual ring so I can quickly gauge how much I've consumed. As a user, I want to see my food entries listed for today so I can review what I've eaten.

#### Acceptance Criteria
- [ ] Dashboard shows an animated progress ring (Chart.js doughnut) with consumed vs remaining calories
- [ ] Progress ring animates from previous value to new value on each food entry (requestAnimationFrame)
- [ ] Ring color is green (#00d68f) when within goal, orange (#ff9f43) above 80%, red (#ff6b6b) when exceeded
- [ ] Today's food entries are listed below the ring with food name, calories, confidence, and timestamp
- [ ] Entry cards appear with a fadeInUp CSS animation
- [ ] Daily summary is fetched via GET /summary?date=YYYY-MM-DD
- [ ] total_calories always equals the sum of individual entry calories
- [ ] remaining_calories = max(0, goal - total) and is never negative

### Requirement 5: Goal Achievement Celebrations

**User Story:** As a user, I want a celebration animation when I stay within my calorie goal so I feel rewarded for healthy eating. As a user, I want a visual warning when I exceed my goal so I'm aware immediately.

#### Acceptance Criteria
- [ ] Canvas Confetti animation triggers when the daily total is at or below the goal at end of day or when goal is first achieved
- [ ] A CSS shake animation triggers on the calorie display when the goal is exceeded
- [ ] Goal status evaluates to WITHIN_GOAL if total_calories <= target, EXCEEDED otherwise
- [ ] Animations are performant and non-blocking

### Requirement 6: Weekly Summary & Bar Chart

**User Story:** As a user, I want to see a weekly bar chart of my daily intake so I can spot trends and patterns.

#### Acceptance Criteria
- [ ] Weekly view shows a Chart.js bar chart with 7 days of intake data
- [ ] Each bar is green if within goal, red if exceeded for that day
- [ ] A horizontal line marks the calorie goal across all days
- [ ] Data is fetched via GET /summary/week?start=YYYY-MM-DD
- [ ] Empty days show a zero-height bar

### Requirement 7: Weight Tracking & Progress Chart

**User Story:** As a user, I want to log my weight periodically so I can track my progress over time. As a user, I want to see a weight line chart so I can visualize trends.

#### Acceptance Criteria
- [ ] Weight tracker screen has a form to enter new weight (kg)
- [ ] POST /weight saves the record, recalculates TDEE with new weight, and suggests an updated goal
- [ ] User can accept the new suggested goal or keep their current one
- [ ] Weight history is displayed as a Chart.js line chart with smooth bezier curves and gradient fill
- [ ] History is fetched via GET /weight/history?limit=30
- [ ] Weight update preserves all non-weight profile fields (height, age, sex, activity level)
- [ ] Input validation enforces weight between 30–300 kg

### Requirement 8: Infrastructure & Deployment (Terraform)

**User Story:** As a developer, I want the entire stack deployable via Terraform so infrastructure is reproducible and version-controlled. As a developer, I want costs to remain under $1/month for a single user.

#### Acceptance Criteria
- [ ] Terraform provisions: DynamoDB table (on-demand), Lambda (ARM64, 128MB), API Gateway HTTP API, S3 bucket, CloudFront distribution, Cognito User Pool
- [ ] API Gateway uses a JWT authorizer linked to the Cognito User Pool
- [ ] Lambda uses ARM64 architecture for 20% cost reduction
- [ ] DynamoDB uses on-demand (PAY_PER_REQUEST) billing
- [ ] S3 bucket hosts the SPA static files with CloudFront as CDN
- [ ] A single Cognito user is created (self-registration disabled)
- [ ] OpenAI API key is stored as a Lambda environment variable (from Terraform variable)
- [ ] All resources are in a single AWS region (us-east-1 default)

### Requirement 9: Clean Architecture & TDD

**User Story:** As a developer, I want a clear separation between domain, application, and infrastructure layers so the codebase is testable and maintainable. As a developer, I want all domain logic covered by unit tests before implementation so correctness is guaranteed.

#### Acceptance Criteria
- [ ] Domain layer contains pure business entities and rules with zero external dependencies
- [ ] Application layer defines use cases and Protocol-based ports for dependency inversion
- [ ] Infrastructure layer implements ports with concrete AWS and OpenAI adapters
- [ ] Unit tests cover all domain functions (TDEE calculation, goal evaluation, calorie summation)
- [ ] Unit tests use mocked ports for use case testing
- [ ] Integration tests validate DynamoDB and OpenAI adapter behavior
- [ ] Test coverage includes all correctness properties defined in the design

### Requirement 10: API Design & Error Handling

**User Story:** As a user, I want clear error messages when something goes wrong so I know how to fix it. As a developer, I want consistent API responses so the frontend can handle all cases predictably.

#### Acceptance Criteria
- [ ] API endpoints follow RESTful conventions (POST for create, GET for read, PUT for update)
- [ ] Validation errors return 400 with field-specific error messages
- [ ] Image too large returns 413 Payload Too Large
- [ ] Profile not found returns 404 (triggers onboarding)
- [ ] AI service failures return 503 with retry-after hint after 3 retries with exponential backoff
- [ ] Food not recognized returns a specific error response the frontend can handle gracefully
- [ ] Duplicate onboarding attempt (profile already exists) returns 409 Conflict
- [ ] All responses include appropriate CORS headers for the SPA origin
