# Plan gegen einen Mock-Provider: kein Azure-Konto, keine Zugangsdaten, kein Apply.
# Der Mock liefert für berechnete Werte Platzhalter; geprüft wird die Konfiguration selbst.
mock_provider "azurerm" {}

variables {
  subscription_id = "00000000-0000-0000-0000-000000000000"
  key_vault_name  = "kv-kanfragen-test"
}

# Der Mock-Provider erzeugt für berechnete Attribute zufällige Zeichenketten.
# tenant_id und object_id werden vom Key Vault bzw. der Rollenzuweisung als
# UUID validiert; ohne diese Überschreibung schlägt der Plan schon an der
# Validierung fehl, bevor die eigentlichen Assertions geprüft werden.
override_data {
  target = data.azurerm_client_config.current
  values = {
    tenant_id = "00000000-0000-0000-0000-000000000000"
    object_id = "00000000-0000-0000-0000-000000000001"
  }
}

run "plan_ohne_zugangsdaten" {
  command = plan

  assert {
    condition     = azurerm_container_app.app.template[0].min_replicas == 0
    error_message = "min_replicas muss 0 sein (scale-to-zero). Bei > 0 laufen Replikate rund um die Uhr und kosten auch ohne Traffic."
  }

  assert {
    condition     = azurerm_container_app.app.template[0].max_replicas == 1
    error_message = "max_replicas muss 1 sein: der Zustand liegt in JSON-Dateien im Container (Ergebnisse, Mails, tickets.json). Zwei Replikate hätten jedes einen eigenen Satz Dateien und einen eigenen Ticketzähler, und die Idempotenz über externe_referenz gälte nur je Replikat."
  }

  assert {
    condition     = azurerm_container_app.app.ingress[0].external_enabled && !azurerm_container_app.app.ingress[0].allow_insecure_connections
    error_message = "Ingress muss extern erreichbar und auf HTTPS beschränkt sein."
  }

  assert {
    condition = alltrue([
      for e in azurerm_container_app.app.template[0].container[0].env :
      e.secret_name == "llm-api-key" && (e.value == null || e.value == "") if e.name == "LLM_API_KEY"
      ]) && length([
      for e in azurerm_container_app.app.template[0].container[0].env : e if e.name == "LLM_API_KEY"
    ]) == 1
    error_message = "LLM_API_KEY muss genau einmal vorkommen und darf nur aus dem Key-Vault-Secret kommen, nie als Klartextwert."
  }

  assert {
    condition = alltrue([
      for e in azurerm_container_app.app.template[0].container[0].env :
      e.value == "0" if e.name == "LIVE_MODELLAUFRUFE"
    ])
    error_message = "Live-Modellaufrufe müssen standardmäßig aus sein (LIVE_MODELLAUFRUFE=0)."
  }

  assert {
    condition     = azurerm_key_vault.kv.rbac_authorization_enabled
    error_message = "Key Vault muss RBAC nutzen; die App liest über ihre Managed Identity."
  }

  assert {
    condition     = length(azurerm_container_app.app.template[0].container) == 2
    error_message = "Es müssen genau zwei Container im Template stehen: app und der systeme-Sidecar."
  }

  assert {
    condition     = azurerm_container_app.app.ingress[0].target_port == 8040
    error_message = "Der Ingress muss auf Port 8040 (app) zeigen; der systeme-Sidecar bekommt keinen eigenen Ingress."
  }

  assert {
    condition = alltrue([
      for e in azurerm_container_app.app.template[0].container[0].env :
      e.value == "http://localhost:8050" if e.name == "SYSTEME_BASE_URL"
      ]) && length([
      for e in azurerm_container_app.app.template[0].container[0].env : e if e.name == "SYSTEME_BASE_URL"
    ]) == 1
    error_message = "Der app-Container muss SYSTEME_BASE_URL=http://localhost:8050 gesetzt haben (Sidecar teilt sich localhost)."
  }

  # /api/health kommt ohne Aufruf eines Fachsystems aus. Zeigten die Proben auf
  # /api/status, würde ein Ausfall des systeme-Sidecars (oder sein etwas
  # späterer Start) den gesunden App-Container als ungesund neu starten lassen.
  assert {
    condition     = azurerm_container_app.app.template[0].container[0].liveness_probe[0].path == "/api/health"
    error_message = "Die Liveness-Probe des app-Containers muss auf /api/health zeigen, nicht auf /api/status (das ruft das MES im Sidecar auf)."
  }

  assert {
    condition     = azurerm_container_app.app.template[0].container[0].readiness_probe[0].path == "/api/health"
    error_message = "Die Readiness-Probe des app-Containers muss auf /api/health zeigen, nicht auf /api/status (das ruft das MES im Sidecar auf)."
  }

  assert {
    condition     = azurerm_consumption_budget_resource_group.budget.amount <= 10
    error_message = "Das Budget muss klein bleiben."
  }
}
