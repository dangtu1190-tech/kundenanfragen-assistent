# Azure Container Apps für den Kundenanfragen-Assistenten.
# Vollständig und validierbar, bewusst nie angewendet: es soll nichts laufen,
# das Geld kostet. Prüfung nur über fmt, validate und terraform test (Mock).

resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.name_prefix}-${var.environment_name}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-${var.name_prefix}-${var.environment_name}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  # Kostendeckel: 0,1 GB Logs am Tag reichen für eine Demo locker; die Quote
  # deckelt nur die Aufnahmekosten, sie ist keine Freistufe.
  daily_quota_gb = 0.1
  tags           = var.tags
}

resource "azurerm_container_app_environment" "env" {
  name                       = "cae-${var.name_prefix}-${var.environment_name}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  tags                       = var.tags
}

# User-Assigned statt System-Assigned: die Container App referenziert das
# Key-Vault-Secret schon bei ihrer Erstellung. Eine System-Identität gäbe es
# erst danach, die Rollenzuweisung käme zu spät.
resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${var.name_prefix}-${var.environment_name}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = var.tags
}

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "kv" {
  name                       = var.key_vault_name
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  # Demo: Aufräumen ohne Wartefrist möglich. In Produktion wäre purge protection an.
  purge_protection_enabled   = false
  soft_delete_retention_days = 7
  tags                       = var.tags
}

# Wer ausrollt, darf den Secret-Wert setzen (Officer). Die App darf ihn nur lesen (User).
resource "azurerm_role_assignment" "deployer_secrets_officer" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "app_secrets_user" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# Der Eintrag wird mit einem Platzhalter angelegt. Der echte Schlüssel geht nie
# durch Terraform (nicht im Code, nicht in Variablen, nicht im State), sondern
# danach per `az keyvault secret set` (siehe outputs). ignore_changes verhindert,
# dass ein späteres apply den echten Wert wieder mit dem Platzhalter überschreibt.
resource "azurerm_key_vault_secret" "llm_api_key" {
  name         = var.key_vault_secret_name
  value        = "PLATZHALTER-nach-apply-per-az-cli-setzen"
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_role_assignment.deployer_secrets_officer]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_container_app" "app" {
  name                         = "ca-${var.name_prefix}-${var.environment_name}"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  # Schlüssel als Key-Vault-Referenz: die App liest ihn zur Laufzeit über ihre
  # Identität. Der Wert selbst steht nirgends in dieser Konfiguration.
  secret {
    name                = "llm-api-key"
    identity            = azurerm_user_assigned_identity.app.id
    key_vault_secret_id = azurerm_key_vault_secret.llm_api_key.versionless_id
  }

  ingress {
    external_enabled           = true
    target_port                = 8040
    transport                  = "auto"
    allow_insecure_connections = false # nur HTTPS

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    # min_replicas = 0 ist die Scale-to-zero-Einstellung und die wichtigste Zeile
    # dieser Datei. Bei min_replicas > 0 laufen die Replikate rund um die Uhr und
    # werden auch ohne Traffic berechnet. Das ist der häufigste Grund für
    # unerwartete Rechnungen. Mit 0 fährt Azure die App ohne Anfragen herunter;
    # der erste Aufruf danach dauert einige Sekunden (Kaltstart).
    min_replicas = 0
    max_replicas = var.max_replicas

    container {
      name   = "app"
      image  = var.container_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "PORT"
        value = "8040"
      }
      env {
        name  = "LIVE_MODELLAUFRUFE"
        value = var.live_modellaufrufe ? "1" : "0"
      }
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      env {
        name  = "LLM_BASE_URL"
        value = var.llm_base_url
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
      env {
        name        = "LLM_API_KEY"
        secret_name = "llm-api-key"
      }
      env {
        # Der zweite Container läuft im selben Replikat und teilt sich mit
        # diesem den Netzwerk-Namespace (localhost), genau wie ein Sidecar in
        # Kubernetes. Kein DNS-Name wie im Compose-Setup nötig.
        name  = "SYSTEME_BASE_URL"
        value = "http://localhost:8050"
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8040
        path      = "/api/status"
      }

      readiness_probe {
        transport = "HTTP"
        port      = 8040
        path      = "/api/status"
      }
    }

    # Sidecar aus demselben Image: die Mock-Systemlandschaft (ERP, CRM, MES).
    # Kein eigener Ingress, kein eigenes Scaling; sie läuft mit im Replikat des
    # App-Containers und ist für die App nur über localhost:8050 erreichbar.
    container {
      name    = "systeme"
      image   = var.container_image
      cpu     = 0.25
      memory  = "0.5Gi"
      command = ["sh", "-c", "exec python -m uvicorn systeme.main:app --host 0.0.0.0 --port 8050"]

      liveness_probe {
        transport = "HTTP"
        port      = 8050
        path      = "/"
      }
    }
  }

  depends_on = [azurerm_role_assignment.app_secrets_user]
}

# Das Budget selbst ist kostenlos; es stoppt nichts, es warnt nur. Zusammen mit
# min_replicas = 0 ist es die zweite Verteidigungslinie gegen eine unerwartete
# Rechnung.
resource "azurerm_consumption_budget_resource_group" "budget" {
  name              = "budget-${var.name_prefix}-${var.environment_name}"
  resource_group_id = azurerm_resource_group.rg.id
  amount            = var.budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 80
    threshold_type = "Actual"
    operator       = "GreaterThan"
    contact_emails = [var.budget_alert_email]
  }

  notification {
    enabled        = true
    threshold      = 100
    threshold_type = "Forecasted"
    operator       = "GreaterThan"
    contact_emails = [var.budget_alert_email]
  }
}
