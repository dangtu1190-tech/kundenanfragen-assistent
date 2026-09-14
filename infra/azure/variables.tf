variable "subscription_id" {
  description = "Azure-Abonnement. Nur für ein apply nötig, das hier nie ausgeführt wird."
  type        = string
}

variable "location" {
  description = "Azure-Region."
  type        = string
  default     = "germanywestcentral"
}

variable "name_prefix" {
  description = "Namenspräfix aller Ressourcen (Kleinbuchstaben und Ziffern)."
  type        = string
  default     = "kanfragen"
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{2,11}$", var.name_prefix))
    error_message = "name_prefix: 3 bis 12 Zeichen, Kleinbuchstaben und Ziffern, beginnt mit Buchstabe."
  }
}

variable "environment_name" {
  description = "Umgebungskürzel, Teil der Ressourcennamen."
  type        = string
  default     = "demo"
}

variable "key_vault_name" {
  description = "Name des Key Vault. Weltweit eindeutig, 3 bis 24 Zeichen."
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]$", var.key_vault_name))
    error_message = "key_vault_name: 3 bis 24 Zeichen, Buchstaben, Ziffern, Bindestriche; beginnt mit Buchstabe."
  }
}

variable "key_vault_secret_name" {
  description = "Name des Secrets im Key Vault, das den Modellschlüssel hält."
  type        = string
  default     = "llm-api-key"
}

# Das GHCR-Paket muss einmal manuell auf PUBLIC gestellt werden (neue Pakete
# sind standardmäßig privat). Bei einem privaten Paket kann die Container App
# das Image nicht ziehen, ein echtes apply schlägt mit Unauthorized fehl; dann
# wäre ein registry { server = "ghcr.io", ... }-Block mit Zugangsdaten oder
# Identity nötig, den diese reine Plan-Konfiguration bewusst auslässt.
# ":latest" ist ein Komfort-Default: ein erneuter Push desselben Tags erzeugt
# bei revision_mode "Single" keine neue Revision. Für einen echten Rollout
# diese Variable auf den "sha-<kurz>"-Tag der Pipeline setzen und apply ausführen.
variable "container_image" {
  description = "Öffentliches Image aus der GitHub Container Registry (von der CI gebaut). Dasselbe Image liefert beide Container (app und systeme, siehe main.tf)."
  type        = string
  default     = "ghcr.io/dangtu1190-tech/kundenanfragen-assistent:latest"
}

# Standard 1, und zwar nicht nur aus Kostengründen: der Zustand der Anwendung
# liegt in JSON-Dateien im Container (data/ergebnisse.json, data/mails.json und
# systeme/daten/tickets.json). Zwei Replikate hätten jedes seinen eigenen Satz
# Dateien und damit einen eigenen Ticketzähler; dieselbe Mail bekäme je nach
# Replikat ein anderes Ergebnis, und die Idempotenz über externe_referenz gälte
# nur innerhalb eines Replikats. Erst mit einer gemeinsamen Datenhaltung
# (Datenbank) ist ein höherer Wert fachlich zulässig; deshalb bleibt die
# Validierung bei 1 bis 10 und die Entscheidung beim Setzen der Variablen.
variable "max_replicas" {
  description = "Obergrenze der Replikate. Standard 1: der Zustand liegt in Dateien im Container, zwei Replikate hätten getrennte Ergebnisse und Ticketzähler."
  type        = number
  default     = 1
  validation {
    condition     = var.max_replicas >= 1 && var.max_replicas <= 10
    error_message = "max_replicas: 1 bis 10."
  }
}

variable "live_modellaufrufe" {
  description = "Live-Pfad der Anwendung. Standard aus: sonst zahlt der Schlüssel für jeden Besucher."
  type        = bool
  default     = false
}

variable "llm_provider" {
  description = "Anbieterkennung für die Anwendung (LLM_PROVIDER). Eigenes Konto, kein Firmenzugang eines Arbeitgebers."
  type        = string
  default     = "openai"
}

variable "llm_base_url" {
  description = "OpenAI-kompatible Basis-URL (LLM_BASE_URL)."
  type        = string
  default     = "https://api.openai.com/v1"
}

variable "llm_model" {
  description = "Modellname (LLM_MODEL)."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "budget_alert_email" {
  description = "Empfänger des Budget-Alarms."
  type        = string
  default     = "budget-alarm@example.invalid"
}

variable "budget_amount" {
  description = "Monatliches Budget in der Währung des Abonnements. Alarm bei 80 und bei 100 Prozent des Forecasts."
  type        = number
  default     = 5
}

variable "budget_start_date" {
  description = "Start des Budgetzeitraums. Muss der erste Tag eines Monats und zum Zeitpunkt des apply nicht in der Vergangenheit sein; vor einem echten apply anpassen."
  type        = string
  default     = "2026-10-01T00:00:00Z"
}

variable "tags" {
  description = "Tags aller Ressourcen."
  type        = map(string)
  default = {
    projekt = "kundenanfragen-assistent"
    zweck   = "demo"
  }
}
