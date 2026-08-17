# --- Cognito User Pool ---

resource "aws_cognito_user_pool" "nutritrack" {
  name = "nutritrack-user-pool"

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length    = 8
    require_lowercase = false
    require_numbers   = false
    require_symbols   = false
    require_uppercase = false
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }
}

# --- Cognito App Client ---

resource "aws_cognito_user_pool_client" "nutritrack" {
  name         = "nutritrack-app-client"
  user_pool_id = aws_cognito_user_pool.nutritrack.id

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  generate_secret = false

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30
}

# --- User Creation ---
# Create the user manually in AWS Console or via CLI:
#   aws cognito-idp admin-create-user \
#     --user-pool-id <pool_id> \
#     --username <tu-usuario> \
#     --temporary-password <password> \
#     --user-attributes Name=email,Value=tu@email.com Name=email_verified,Value=true
#
#   aws cognito-idp admin-set-user-password \
#     --user-pool-id <pool_id> \
#     --username <tu-usuario> \
#     --password <password-definitivo> \
#     --permanent
