# NutriTrack — AI-Powered Calorie Tracker

A personal AI-powered calorie tracking application. Photograph your food, get instant calorie estimates from GPT-4o-mini, and track daily intake against a personalized TDEE-based calorie goal.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         Frontend (SPA)                            │
│  S3 + CloudFront · Vanilla JS · Chart.js · Canvas Confetti       │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   AWS Cognito (Auth)     │
                    │   JWT · USER_PASSWORD    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  API Gateway HTTP API    │
                    │  JWT Authorizer          │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Lambda (Python 3.12)    │
                    │  ARM64 · 128MB           │
                    ├─────────────────────────┤
                    │  Domain Layer            │
                    │  Use Cases Layer         │
                    │  Infrastructure Layer    │
                    └──────┬──────────┬───────┘
                           │          │
              ┌────────────▼──┐  ┌────▼──────────┐
              │  DynamoDB     │  │  OpenAI API   │
              │  On-Demand    │  │  GPT-4o-mini  │
              └───────────────┘  └───────────────┘
```

**Estimated monthly cost (single user):** < $1 USD

## Features

- 📷 Food photo analysis with AI calorie estimation
- 📊 Animated daily progress ring with color-coded status
- 📈 Weekly bar chart and weight trend line chart
- 🎯 Personalized TDEE-based calorie goals (Mifflin-St Jeor formula)
- 🎉 Confetti celebration on goal achievement
- 🏗️ Full Infrastructure-as-Code with Terraform
- 🧪 Clean Architecture with comprehensive test coverage

## Prerequisites

- **Python 3.12+** — Backend runtime
- **Terraform 1.5+** — Infrastructure provisioning
- **AWS CLI v2** — Configured with appropriate credentials
- **An AWS Account** — With permissions for Lambda, DynamoDB, API Gateway, S3, CloudFront, Cognito
- **OpenAI API Key** — For GPT-4o-mini food analysis

## Project Structure

```
nutritrack/
├── src/nutritrack/           # Python backend (Lambda)
│   ├── domain/               #   Business entities & rules
│   ├── use_cases/            #   Application logic & ports
│   ├── infrastructure/       #   AWS & OpenAI adapters
│   └── handler.py            #   Lambda entry point
├── frontend/                 # Static SPA
│   ├── index.html            #   Main HTML (dark mode UI)
│   ├── config.js             #   Runtime configuration (fill after deploy)
│   ├── app.js                #   Auth, navigation, API helper
│   ├── onboarding.js         #   Onboarding flow
│   ├── dashboard.js          #   Dashboard & food entry
│   └── charts.js             #   Weekly & weight charts
├── terraform/                # Infrastructure as Code
│   ├── main.tf               #   Lambda, API Gateway, DynamoDB
│   ├── cognito.tf            #   Auth resources
│   ├── frontend.tf           #   S3, CloudFront
│   ├── variables.tf          #   Input variables
│   └── outputs.tf            #   Deployment outputs
├── tests/                    # Test suite
│   ├── unit/                 #   Domain & use case tests
│   └── integration/          #   DynamoDB & handler tests
├── scripts/
│   └── package-lambda.sh     #   Lambda zip builder
├── pyproject.toml            #   Python project config
└── README.md                 #   This file
```

## Setup

### 1. Clone and install dependencies

```bash
git clone <repository-url>
cd nutritrack

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (including dev)
pip install -e ".[dev]"
```

### 2. Run tests

```bash
pytest
```

### 3. Configure Terraform variables

Create a `terraform/terraform.tfvars` file (this file is git-ignored):

```hcl
openai_api_key = "sk-your-openai-api-key"
aws_region     = "us-east-1"
app_username   = "your-username"
app_password   = "YourSecureP@ssw0rd"
```

## Deployment

### 1. Build the Lambda package

```bash
./scripts/package-lambda.sh
```

This creates `lambda.zip` at the project root.

### 2. Initialize and apply Terraform

```bash
cd terraform
terraform init
terraform plan    # Review changes
terraform apply   # Deploy infrastructure
```

### 3. Get deployment outputs

```bash
terraform output -raw api_url
terraform output -raw cognito_user_pool_id
terraform output -raw cognito_client_id
terraform output -raw cloudfront_domain
```

### 4. Configure the frontend

Edit `frontend/config.js` with the Terraform outputs:

```javascript
window.APP_CONFIG = {
  apiUrl: 'https://xxxxxxxx.execute-api.us-east-1.amazonaws.com',
  cognitoPoolId: 'us-east-1_XXXXXXXXX',
  cognitoClientId: 'xxxxxxxxxxxxxxxxxxxxxxxxxx',
  region: 'us-east-1'
};
```

### 5. Deploy frontend to S3

```bash
aws s3 sync frontend/ s3://$(terraform output -raw frontend_bucket_name) --delete
```

### 6. Access the application

Open the CloudFront URL in your browser:

```bash
echo "https://$(terraform output -raw cloudfront_domain)"
```

## Environment Variables

### Terraform Variables (`terraform.tfvars`)

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `openai_api_key` | OpenAI API key for GPT-4o-mini | Yes | — |
| `aws_region` | AWS region for all resources | No | `us-east-1` |
| `app_username` | Username for the Cognito user | Yes | — |
| `app_password` | Password for the Cognito user | Yes | — |

### Lambda Environment Variables (set by Terraform)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (from Terraform variable) |
| `DYNAMODB_TABLE` | DynamoDB table name |
| `OPENAI_MODEL` | AI model identifier (`gpt-4o-mini`) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/entries` | Upload food image (base64), get AI calorie estimate |
| `GET` | `/summary?date=YYYY-MM-DD` | Daily summary with entries and goal status |
| `GET` | `/summary/week?start=YYYY-MM-DD` | 7-day summary for weekly chart |
| `GET` | `/profile` | Get user profile (404 triggers onboarding) |
| `POST` | `/profile` | Create profile during onboarding |
| `PUT` | `/profile/goal` | Update daily calorie goal |
| `POST` | `/weight` | Log new weight, recalculate TDEE |
| `GET` | `/weight/history?limit=30` | Weight history for charts |

## Cost Breakdown

| Service | Cost Model | Estimated |
|---------|-----------|-----------|
| Lambda (ARM64, 128MB) | Pay per invocation | ~$0.01/mo |
| API Gateway HTTP API | $1/million requests | ~$0.01/mo |
| DynamoDB On-Demand | Pay per read/write | ~$0.01/mo |
| S3 (frontend hosting) | $0.023/GB/month | ~$0.01/mo |
| CloudFront | Free tier (1TB/month) | $0.00/mo |
| Cognito | Free tier (50K MAU) | $0.00/mo |
| GPT-4o-mini | ~$0.15/1M input tokens | ~$0.10/mo |
| **Total** | | **< $1/mo** |

## Development

### Running tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest --cov=src/nutritrack
```

### Code structure (Clean Architecture)

- **Domain Layer** (`src/nutritrack/domain/`) — Pure business logic, zero dependencies
- **Use Cases Layer** (`src/nutritrack/use_cases/`) — Application orchestration, Protocol-based ports
- **Infrastructure Layer** (`src/nutritrack/infrastructure/`) — AWS & OpenAI adapters

## License

See [LICENSE](LICENSE) for details.
