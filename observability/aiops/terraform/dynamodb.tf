###############################################################################
# DynamoDB — Incident History Table
# Stores every alert, Claude's analysis, and every action taken.
# Required for:
#   - Context enrichment (has this alert fired before?)
#   - Audit trail (FedRAMP requirement)
#   - Continuous improvement (feedback loop)
###############################################################################

resource "aws_dynamodb_table" "incidents" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  table_class  = "STANDARD"
  hash_key     = "incident_id"
  range_key    = "timestamp"

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "alert_name"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  global_secondary_index {
    name            = "AlertNameIndex"
    hash_key        = "alert_name"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name    = var.dynamodb_table_name
    Purpose = "AIOps incident history and audit trail"
  }
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.incidents.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.incidents.arn
}