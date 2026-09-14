# Cloud-Deployment-Weg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Container, CI-Pipeline, Terraform-Konfiguration (nur Plan), Render/Fly-Dateien und README-Abschnitt „Betrieb" für den Serviceanfragen-Assistenten, ohne laufende Kosten und ohne Änderung der Anwendungslogik.

**Architecture:** Ein einziger Eingriff in die Anwendung (Umgebungsschalter `LIVE_MODELLAUFRUFE`, Standard aus, sperrt den Verarbeiten-Endpunkt mit 403). Alles andere sind neue Dateien neben der Anwendung: `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `infra/azure/*`, `render.yaml`, `fly.toml`, plus README.

**Tech Stack:** Python 3.12, FastAPI, Docker (Multi-Stage, python:3.12-slim), GitHub Actions, ghcr.io, Terraform 1.16 mit azurerm ~> 4.0 und `terraform test`/`mock_provider`, Ruff.

**Spec:** `planung/specs/2026-09-11-cloud-deployment-design.md`

## Global Constraints

- Arbeitsverzeichnis: `C:\Users\dtn\Desktop\serviceanfragen-assistent-cloud` (git-Worktree, Branch `cloud-deployment`). Python-Befehl `python`.
- Sprache Deutsch in Kommentaren, Meldungen, Doku und Commits. Keine Gedankenstriche (—) in Prosa, kein Marketington.
- Anwendungslogik unverändert. Erlaubt sind nur die in Task 1 genannten Zeilen in `app/main.py`, `docs/index.html`, `tests/test_main.py`, `.env.example`.
- Kein Schlüssel, kein Langdock-Zugang, kein echter Wert in irgendeiner Datei. `LLM_API_KEY` bleibt überall leer oder ein Platzhalter.
- Kein `terraform apply`, kein Push eines Images, kein Ausrollen. Lokal wird nur gebaut, gestartet, geplant.
- Terraform-Binary lokal: `C:\Users\dtn\AppData\Local\Temp\claude\c--Users-dtn-Desktop-Engel\9776635e-1787-4a2c-955e-323fce53f99c\scratchpad\tf\terraform.exe`. Ruff lokal: `C:\Users\dtn\AppData\Local\Temp\claude\c--Users-dtn-Desktop-Engel\9776635e-1787-4a2c-955e-323fce53f99c\scratchpad\venv\Scripts\ruff.exe`.
- Vor jedem Commit: `python -m pytest -q` grün (Echtlauf-Test skippt), Ruff grün, `git status --short` ohne `__pycache__`, ohne `.terraform/`, ohne `.env`.
- Commits enden mit `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Dateien in UTF-8 ohne BOM, LF-Zeilenenden.

---

## Dateistruktur

| Datei | Änderung | Task |
|---|---|---|
| `app/main.py` | Schalter lesen, 403 im Verarbeiten-Endpunkt, Feld im Status | 1 |
| `docs/index.html` | Badge und Knöpfe deaktivieren bei ausgeschaltetem Live-Pfad | 1 |
| `tests/test_main.py` | Fixture schaltet ein; zwei neue Tests; ungenutzter Import weg | 1 |
| `.env.example` | `LIVE_MODELLAUFRUFE`, `PORT`, Hinweise | 1 |
| `ruff.toml` | schmale Regelmenge | 2 |
| `Dockerfile`, `.dockerignore`, `docker-compose.yml` | Container | 2 |
| `.gitignore` | `.terraform/`, `*.tfstate*`, `terraform.tfvars` | 3 |
| `infra/azure/versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`, `terraform.tfvars.example`, `tests/plan.tftest.hcl` | IaC | 3 |
| `.github/workflows/ci.yml` | Pipeline | 4 |
| `render.yaml`, `fly.toml` | öffentliche Demo, vorbereitet | 4 |
| `README.md` | Badge, Abschnitte 5, 8, neuer Abschnitt Betrieb, Abschnitt Bewusst nicht enthalten | 5 |

---

### Task 1: Live-Schalter `LIVE_MODELLAUFRUFE`

**Files:**
- Modify: `app/main.py`
- Modify: `docs/index.html` (Funktion `starte`, Zeilen ~188-203)
- Modify: `tests/test_main.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `GET /api/status` enthält `live_modellaufrufe: bool`. `POST /api/mails/{id}/verarbeiten` antwortet 403 mit `detail = "Live-Modellaufrufe sind abgeschaltet (LIVE_MODELLAUFRUFE=0). Die Demo zeigt aufgezeichnete Ergebnisse."`, wenn der Schalter aus ist. Task 2 und 4 prüfen genau das im Rauchtest.

- [ ] **Step 1: Fixture einschalten, ungenutzten Import entfernen, zwei Tests anhängen**

In `tests/test_main.py` die Zeile `from pathlib import Path` löschen (ungenutzt, Ruff F401). Die Fixture `client` so ändern, dass sie den Schalter einschaltet:

```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    daten = tmp_path / "data"
    daten.mkdir()
    shutil.copyfile("data/mails.json", daten / "mails.json")
    shutil.copyfile("data/kalender.json", daten / "kalender.json")
    monkeypatch.setattr(speicher, "DATEN", daten)
    monkeypatch.setenv("LIVE_MODELLAUFRUFE", "1")
    app = erzeuge_app(client_factory=lambda: FakeClient(ANTWORT))
    return TestClient(app)
```

Am Dateiende anhängen:

```python
def test_status_meldet_live_schalter(client, monkeypatch):
    assert client.get("/api/status").json()["live_modellaufrufe"] is True
    monkeypatch.setenv("LIVE_MODELLAUFRUFE", "0")
    assert client.get("/api/status").json()["live_modellaufrufe"] is False


def test_verarbeiten_ohne_live_schalter_ist_gesperrt(client, monkeypatch):
    """Standard aus: kein Modellaufruf, kein Überschreiben des aufgezeichneten Ergebnisses.
    Sonst zahlt der hinterlegte Schlüssel für jeden Besucher der öffentlichen Demo."""
    client.post("/api/mails/m01/verarbeiten")
    vorher = client.get("/api/mails/m01").json()["ergebnis"]
    monkeypatch.delenv("LIVE_MODELLAUFRUFE", raising=False)
    r = client.post("/api/mails/m01/verarbeiten")
    assert r.status_code == 403
    assert r.json()["detail"] == "Live-Modellaufrufe sind abgeschaltet (LIVE_MODELLAUFRUFE=0). Die Demo zeigt aufgezeichnete Ergebnisse."
    assert client.get("/api/mails/m01").json()["ergebnis"] == vorher
    for wert in ("0", "false", "nein", ""):
        monkeypatch.setenv("LIVE_MODELLAUFRUFE", wert)
        assert client.post("/api/mails/m01/verarbeiten").status_code == 403, wert
    for wert in ("1", "true", "JA", "on"):
        monkeypatch.setenv("LIVE_MODELLAUFRUFE", wert)
        assert client.post("/api/mails/m01/verarbeiten").status_code == 200, wert
```

Hinweis: Eine lokale `.env` wird von `lade_konfig` per `setdefault` gelesen. `monkeypatch.delenv` entfernt einen eventuell daraus gesetzten Wert; der Test ist deshalb unabhängig von der `.env` des Entwicklers.

- [ ] **Step 2: Tests laufen lassen, die neuen müssen fehlschlagen**

Run: `python -m pytest tests/test_main.py -q`
Expected: 2 failed (KeyError `live_modellaufrufe`, Status 200 statt 403), Rest passed.

- [ ] **Step 3: Schalter in `app/main.py`**

`import os` zu den Imports. Nach `_heute()` einfügen:

```python
def _live_modellaufrufe() -> bool:
    """Standard aus. Bei einer öffentlich erreichbaren Instanz zahlt sonst der
    hinterlegte Schlüssel für jeden Besucher, der auf Verarbeiten klickt."""
    return os.getenv("LIVE_MODELLAUFRUFE", "0").strip().lower() in ("1", "true", "ja", "on")
```

Im Status-Endpunkt das Feld ergänzen:

```python
        return {"anbieter": client.konfig.provider, "modell": client.konfig.model,
                "schluessel_gesetzt": client.konfig.schluessel_gesetzt or client.konfig.provider in ("ollama", "fake"),
                "live_modellaufrufe": _live_modellaufrufe(),
                "heute": _heute().isoformat(), "modus": "server"}
```

Im Verarbeiten-Endpunkt als erste Zeilen:

```python
    def verarbeiten(mail_id: str):
        if not _live_modellaufrufe():
            raise HTTPException(403, "Live-Modellaufrufe sind abgeschaltet (LIVE_MODELLAUFRUFE=0). "
                                     "Die Demo zeigt aufgezeichnete Ergebnisse.")
        mail = _mail(mail_id)
```

Nichts anderes in `app/main.py` ändern.

- [ ] **Step 4: Tests grün**

Run: `python -m pytest -q`
Expected: alle passed, 1 skipped (Echtlauf).

- [ ] **Step 5: Oberfläche**

In `docs/index.html`, Funktion `starte`, den Erfolgszweig ersetzen:

```js
    .then(function (s) {
      statisch = false;
      document.getElementById("kopf-info").textContent = s.anbieter + " / " + s.modell;
      if (s.live_modellaufrufe === false) {
        document.getElementById("kopf-info").innerHTML = s.anbieter + " / " + s.modell +
          ' <span class="badge" style="background:#5a6472">Live-Modellaufrufe abgeschaltet: aufgezeichnete Ergebnisse, Freigabe und Ablehnung funktionieren</span>';
        document.getElementById("btn-alle").disabled = true;
        document.getElementById("btn-neu").disabled = true;
        document.getElementById("btn-neu-verarbeiten").disabled = true;
      }
      ladeMailsServer();
    })
```

Sonst nichts in `docs/index.html` ändern.

- [ ] **Step 6: `.env.example`**

Datei komplett ersetzen:

```
# Live-Modellaufrufe: 0 = aus (Standard). Die Demo zeigt dann die aufgezeichneten
# Ergebnisse, Freigabe und Ablehnung funktionieren, "Verarbeiten" ist gesperrt.
# 1 = an: jeder Klick auf "Verarbeiten" ruft das Modell und kostet Geld.
# Eine öffentlich erreichbare Instanz bleibt auf 0, sonst zahlt der Schlüssel für jeden Besucher.
LIVE_MODELLAUFRUFE=0
# Anbieter: langdock oder ollama; jeder andere OpenAI-kompatible Endpunkt über LLM_BASE_URL
LLM_PROVIDER=langdock
# Basis-URL des Anbieters. Für Ollama: http://localhost:11434/v1
LLM_BASE_URL=https://api.langdock.com/openai/eu/v1
# Modellname. Ollama z. B. qwen2.5:7b
LLM_MODEL=gpt-5.1
# Schlüssel eines eigenen Kontos. Nie einchecken. Bei Ollama beliebiger Wert.
LLM_API_KEY=
# Port des Servers im Container (Render und Fly setzen ihn selbst). run.bat/run.sh nutzen fest 8040.
PORT=8040
```

- [ ] **Step 7: Ruff und Tests, dann Commit**

Run: `<ruff.exe> check --select E4,E7,E9,F app tests` (Pfad siehe Global Constraints) → `All checks passed!`
Run: `python -m pytest -q` → alle passed, 1 skipped.

```bash
git add app/main.py docs/index.html tests/test_main.py .env.example
git commit -m "feat(server): Schalter LIVE_MODELLAUFRUFE, Standard aus, sperrt den Verarbeiten-Endpunkt

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Container (Dockerfile, .dockerignore, docker-compose.yml, ruff.toml)

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `ruff.toml`

**Interfaces:**
- Consumes: 403-Verhalten aus Task 1.
- Produces: Image lauscht auf `$PORT` (Standard 8040), `GET /api/status` liefert 200. Task 4 baut dasselbe Image in der Pipeline.

- [ ] **Step 1: `ruff.toml`**

```toml
# Absichtlich schmale Regelmenge: Syntax- und Importfehler, undefinierte Namen,
# ungenutzte Importe. Stilregeln bleiben aus, damit der Linter keine Umbauten
# am bestehenden Code erzwingt (Ruff 0.16 aktiviert sonst ISC, FURB, DTZ, RUF ...).
target-version = "py312"
line-length = 130

[lint]
select = ["E4", "E7", "E9", "F"]
```

Run: `<ruff.exe> check app tests` → `All checks passed!` (jetzt ohne `--select`, die Datei greift).

- [ ] **Step 2: `.dockerignore`**

```
.git
.gitignore
.github
.env
.env.*
.venv
venv
__pycache__
*.pyc
.pytest_cache
.superpowers
planung
tests
infra
docs/data
docs/GESPRAECH.md
README.md
run.bat
run.sh
docker-compose.yml
render.yaml
fly.toml
ruff.toml
```

- [ ] **Step 3: `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1
# Stufe 1: Abhängigkeiten in ein eigenes Prefix installieren. pip-Cache und
# Build-Reste bleiben in dieser Stufe zurück.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stufe 2: Laufzeitbild. Enthält nur Python, die installierten Pakete und die
# Anwendung. Keine Konfigurationswerte im Image; alles kommt aus Umgebungsvariablen.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8040 \
    LIVE_MODELLAUFRUFE=0
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /install /usr/local
# data/ gehört dem Laufzeit-User: der Server schreibt Status, Kalender und neue
# Mails dorthin. Im Container ist das flüchtig (siehe README, Betrieb).
COPY --chown=app:app app/ app/
COPY --chown=app:app data/ data/
COPY --chown=app:app docs/index.html docs/index.html
USER app
EXPOSE 8040
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/status' % os.environ.get('PORT', '8040'), timeout=3)" || exit 1
# exec, damit uvicorn PID 1 ist und Stopp-Signale direkt bekommt.
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8040}"]
```

- [ ] **Step 4: `docker-compose.yml`**

```yaml
# Lokaler Start mit einem Befehl: docker compose up --build
# Konfiguration nur über Umgebungsvariablen; .env ist optional (siehe .env.example).
services:
  app:
    build: .
    image: serviceanfragen-assistent:local
    ports:
      - "8040:8040"
    env_file:
      - path: .env
        required: false
    restart: unless-stopped
```

- [ ] **Step 5: Bauen, starten, prüfen**

```bash
docker build -t serviceanfragen-assistent:local .
docker run -d --rm --name sa-test -p 8040:8040 serviceanfragen-assistent:local
sleep 4
curl -s http://localhost:8040/api/status
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8040/api/mails/m01/verarbeiten
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8040/
docker inspect --format '{{.State.Health.Status}}' sa-test
docker exec sa-test id -u
docker image ls serviceanfragen-assistent:local --format '{{.Size}}'
docker stop sa-test
```

Expected: Status-JSON mit `"live_modellaufrufe": false` und `"modus": "server"`; `403`; `200`; Health `starting` oder `healthy` (nach 30 s `healthy`); UID `10001`; Größe notieren.

Dann `docker compose up --build -d` im Projektordner, `curl -s http://localhost:8040/api/status`, `docker compose down`. Expected: gleiches Status-JSON.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml ruff.toml
git commit -m "build: Dockerfile (Multi-Stage, non-root, Healthcheck), Compose, Ruff-Konfiguration

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Terraform für Azure Container Apps (nur Plan)

**Files:**
- Create: `infra/azure/versions.tf`, `infra/azure/variables.tf`, `infra/azure/main.tf`, `infra/azure/outputs.tf`, `infra/azure/terraform.tfvars.example`, `infra/azure/tests/plan.tftest.hcl`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate`, `terraform test` laufen im Ordner `infra/azure` ohne Zugangsdaten grün. Task 4 ruft genau diese vier Befehle.

- [ ] **Step 1: `.gitignore` ergänzen**

Anhängen:

```
.terraform/
.terraform.lock.hcl
*.tfstate
*.tfstate.*
terraform.tfvars
```

(Die Lock-Datei bleibt bewusst draußen: die Pipeline initialisiert frisch, und die Versionsgrenze steht in `versions.tf`.)

- [ ] **Step 2: `infra/azure/versions.tf`**

```hcl
terraform {
  # >= 1.7 wegen mock_provider in terraform test (Plan ohne Azure-Konto)
  required_version = ">= 1.7"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  # Keine automatische Registrierung von Resource Providern: dafür braucht es
  # Rechte auf Abonnementebene, und für einen reinen Plan ist es unnötig.
  resource_provider_registrations = "none"
}
```

- [ ] **Step 3: `infra/azure/variables.tf`**

```hcl
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
  default     = "svcanfragen"
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

variable "container_image" {
  description = "Öffentliches Image aus der GitHub Container Registry (von der CI gebaut)."
  type        = string
  default     = "ghcr.io/dangtu1190-tech/serviceanfragen-assistent:latest"
}

variable "max_replicas" {
  description = "Obergrenze der Replikate. Deckelt Kosten bei unerwartetem Traffic."
  type        = number
  default     = 2
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
  description = "Anbieterkennung für die Anwendung (LLM_PROVIDER). Nicht der Langdock-Zugang des Arbeitgebers."
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

variable "tags" {
  description = "Tags aller Ressourcen."
  type        = map(string)
  default = {
    projekt = "serviceanfragen-assistent"
    zweck   = "demo"
  }
}
```

- [ ] **Step 4: `infra/azure/main.tf`**

```hcl
# Azure Container Apps für den Serviceanfragen-Assistenten.
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
  # Kostendeckel: mehr als 0,5 GB Logs am Tag werden verworfen statt berechnet.
  daily_quota_gb = 0.5
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
  }

  depends_on = [azurerm_role_assignment.app_secrets_user]
}
```

- [ ] **Step 5: `infra/azure/outputs.tf`**

```hcl
output "app_url" {
  description = "Öffentliche HTTPS-Adresse der Container App (nach einem apply)."
  value       = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}

output "key_vault_name" {
  value = azurerm_key_vault.kv.name
}

output "secret_setzen" {
  description = "Nach dem apply einmal ausführen; der Wert kommt aus der eigenen Ablage, nie aus dem Repo."
  value       = "az keyvault secret set --vault-name ${azurerm_key_vault.kv.name} --name ${var.key_vault_secret_name} --value <SCHLUESSEL>"
}
```

- [ ] **Step 6: `infra/azure/terraform.tfvars.example`**

```hcl
# Kopie als terraform.tfvars anlegen (steht in .gitignore). Keine Schlüssel hier:
# der Modellschlüssel kommt nach dem apply per az cli in den Key Vault.
subscription_id  = "00000000-0000-0000-0000-000000000000"
location         = "germanywestcentral"
name_prefix      = "svcanfragen"
environment_name = "demo"
key_vault_name   = "kv-svcanfragen-demo-01" # weltweit eindeutig, ggf. Suffix ändern
container_image  = "ghcr.io/dangtu1190-tech/serviceanfragen-assistent:latest"
max_replicas     = 2

# Live-Pfad bleibt aus. Anbieterdaten eines eigenen Kontos; nicht der Langdock-Zugang des Arbeitgebers.
live_modellaufrufe = false
llm_provider       = "openai"
llm_base_url       = "https://api.openai.com/v1"
llm_model          = "gpt-4.1-mini"
```

- [ ] **Step 7: `infra/azure/tests/plan.tftest.hcl`**

```hcl
# Plan gegen einen Mock-Provider: kein Azure-Konto, keine Zugangsdaten, kein Apply.
# Der Mock liefert für berechnete Werte Platzhalter; geprüft wird die Konfiguration selbst.
mock_provider "azurerm" {}

variables {
  subscription_id = "00000000-0000-0000-0000-000000000000"
  key_vault_name  = "kv-svcanfragen-test"
}

run "plan_ohne_zugangsdaten" {
  command = plan

  assert {
    condition     = azurerm_container_app.app.template[0].min_replicas == 0
    error_message = "min_replicas muss 0 sein (scale-to-zero). Bei > 0 laufen Replikate rund um die Uhr und kosten auch ohne Traffic."
  }

  assert {
    condition     = azurerm_container_app.app.template[0].max_replicas >= 1 && azurerm_container_app.app.template[0].max_replicas <= 10
    error_message = "max_replicas muss begrenzt sein (1 bis 10)."
  }

  assert {
    condition     = azurerm_container_app.app.ingress[0].external_enabled && !azurerm_container_app.app.ingress[0].allow_insecure_connections
    error_message = "Ingress muss extern erreichbar und auf HTTPS beschränkt sein."
  }

  assert {
    condition = alltrue([
      for e in azurerm_container_app.app.template[0].container[0].env :
      e.secret_name == "llm-api-key" && (e.value == null || e.value == "") if e.name == "LLM_API_KEY"
    ])
    error_message = "LLM_API_KEY darf nur aus dem Key-Vault-Secret kommen, nie als Klartextwert."
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
}
```

- [ ] **Step 8: Lokal prüfen (Binary siehe Global Constraints; im Ordner `infra/azure`)**

```bash
terraform fmt -check -recursive -diff     # ggf. `terraform fmt -recursive` und erneut prüfen
terraform init -backend=false
terraform validate
terraform test
```

Expected: fmt ohne Ausgabe (Exit 0); init lädt azurerm 4.x; `Success! The configuration is valid.`; `Success! 1 passed, 0 failed.` Falls `validate` ein Attribut nicht kennt (Provider-Schema), das Attribut an die Provider-Doku anpassen und den Plan-Text hier korrigieren, nicht stillschweigend weglassen. `.terraform/` und `.terraform.lock.hcl` dürfen nicht im Commit landen.

- [ ] **Step 9: Commit**

```bash
git add .gitignore infra/
git status --short   # keine .terraform/, keine Lock-Datei
git commit -m "infra: Terraform für Azure Container Apps (scale-to-zero, Key Vault per Managed Identity), nur Plan

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: CI-Pipeline, render.yaml, fly.toml

**Files:**
- Create: `.github/workflows/ci.yml`, `render.yaml`, `fly.toml`

**Interfaces:**
- Consumes: Task 1 (403), Task 2 (Dockerfile), Task 3 (vier Terraform-Befehle im Ordner `infra/azure`).
- Produces: Workflow-Datei `ci.yml`; Badge-URL für Task 5: `https://github.com/dangtu1190-tech/serviceanfragen-assistent/actions/workflows/ci.yml/badge.svg`.

- [ ] **Step 1: `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

permissions:
  contents: read
  packages: write

env:
  IMAGE: ghcr.io/${{ github.repository }}

jobs:
  tests:
    name: Tests und Linter
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Abhängigkeiten
        run: python -m pip install -r requirements.txt ruff
      - name: Linter (Ruff)
        run: ruff check app tests
      - name: Pseudonymisierung, kein Originalwert erreicht das Modell
        # Eigener Schritt, damit dieser Test im Lauf sichtbar ist. Schlägt er
        # fehl, ist der Lauf rot und das Image wird nicht gebaut.
        run: >
          python -m pytest -v
          tests/test_pipeline.py::test_kein_original_erreicht_das_modell
          tests/test_pipeline.py::test_modell_sieht_keine_originale
      - name: Alle Tests
        run: python -m pytest -q

  image:
    name: Docker-Image
    needs: tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Image bauen
        run: docker build -t rauchtest .
      - name: Rauchtest, Container starten
        # Status muss antworten, der Live-Pfad muss gesperrt sein (403).
        run: |
          docker run -d --name rauchtest -p 8040:8040 rauchtest
          for i in $(seq 1 20); do
            curl -sf http://localhost:8040/api/status && break
            sleep 1
          done
          curl -sf http://localhost:8040/api/status | grep -q '"live_modellaufrufe":false'
          code=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8040/api/mails/m01/verarbeiten)
          test "$code" = "403"
          docker logs rauchtest
          docker rm -f rauchtest
      - uses: docker/setup-buildx-action@v3
      - name: Anmelden an ghcr.io
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE }}
          tags: |
            type=raw,value=latest,enable={{is_default_branch}}
            type=sha
      - name: Bauen und (nur auf main) nach ghcr.io schieben
        uses: docker/build-push-action@v6
        with:
          context: .
          push: ${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  terraform:
    name: Terraform (fmt, validate, Plan gegen Mock-Provider)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: infra/azure
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.16.2"
      - run: terraform fmt -check -recursive -diff
      - run: terraform init -backend=false
      - run: terraform validate
      - name: Plan gegen Mock-Provider (keine Azure-Zugangsdaten, kein Apply)
        run: terraform test
```

- [ ] **Step 2: `render.yaml`**

```yaml
# Render Blueprint. Vorbereitet, nicht ausgerollt.
# Free-Plan (Stand 11.09.2026, render.com/docs/free): Instanz schläft nach 15 Minuten
# ohne Anfragen ein, der erste Aufruf danach dauert bis zu einer Minute; 750 Instanz-
# stunden je Monat; Dateisystem flüchtig (Statusänderungen gehen beim Neustart verloren).
services:
  - type: web
    name: serviceanfragen-assistent
    runtime: docker
    plan: free
    region: frankfurt
    dockerfilePath: ./Dockerfile
    healthCheckPath: /api/status
    autoDeploy: false
    envVars:
      # Live-Pfad bleibt aus: sonst zahlt der Schlüssel für jeden Besucher.
      - key: LIVE_MODELLAUFRUFE
        value: "0"
      # Nur im Render-Dashboard setzen, nie in dieser Datei. Ohne Live-Pfad ungenutzt.
      - key: LLM_API_KEY
        sync: false
```

- [ ] **Step 3: `fly.toml`**

```toml
# Fly.io-Konfiguration. Vorbereitet, nicht ausgerollt.
# Achtung: Die Fly.io-Preisseite (fly.io/docs/about/pricing, Stand 11.09.2026) nennt
# keinen kostenlosen Plan mehr; auch gestoppte Maschinen kosten Speicher
# (0,15 $ je GB Root-Dateisystem und Monat). Für eine kostenfreie Demo ist Render
# die bessere Wahl (render.yaml).
app = "serviceanfragen-assistent"
primary_region = "fra"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8080"
  # Live-Pfad bleibt aus: sonst zahlt der Schlüssel für jeden Besucher.
  LIVE_MODELLAUFRUFE = "0"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  # 0 = scale-to-zero, gleiche Begründung wie in infra/azure/main.tf: bei > 0 läuft
  # eine Maschine rund um die Uhr und wird auch ohne Traffic berechnet.
  min_machines_running = 0

  [[http_service.checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"
    method = "GET"
    path = "/api/status"

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
```

- [ ] **Step 4: Syntax prüfen**

```bash
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8')); yaml.safe_load(open('render.yaml', encoding='utf-8')); print('yaml ok')"
python -c "import tomllib; tomllib.load(open('fly.toml','rb')); print('toml ok')"
```

Falls `yaml` fehlt: `python -m pip install pyyaml` (nicht in requirements aufnehmen). Expected: `yaml ok`, `toml ok`. Zusätzlich die Rauchtest-Zeilen aus dem Workflow lokal gegen das Image aus Task 2 ausführen (Bash, `docker run … rauchtest`), Expected: `403`, Grep-Treffer.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml render.yaml fly.toml
git commit -m "ci: GitHub Actions (Tests, Linter, Image nach ghcr.io, Terraform-Plan gegen Mock); Render- und Fly-Konfiguration

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: alle vorherigen Tasks (Dateinamen, Befehle, Badge-URL).

- [ ] **Step 1: Badge**

Direkt unter der Zeile `# Serviceanfragen-Assistent` eine Leerzeile und:

```markdown
[![CI](https://github.com/dangtu1190-tech/serviceanfragen-assistent/actions/workflows/ci.yml/badge.svg)](https://github.com/dangtu1190-tech/serviceanfragen-assistent/actions/workflows/ci.yml)
```

- [ ] **Step 2: Abschnitt 5 „Lokal starten"**

Nach dem Satz „In der `.env` den Schlüssel eintragen (`LLM_API_KEY`), dann:" ergänzen, dass für neue Modellaufrufe zusätzlich `LIVE_MODELLAUFRUFE=1` in der `.env` stehen muss. Neuer Absatz nach der Liste Windows/Linux:

```markdown
Neue Modellaufrufe („Verarbeiten", „Neue Mail") sind nur möglich, wenn in der
`.env` zusätzlich `LIVE_MODELLAUFRUFE=1` steht. Standard ist aus: der Server
zeigt dann die aufgezeichneten Ergebnisse, Freigabe und Ablehnung funktionieren,
der Verarbeiten-Endpunkt antwortet mit HTTP 403 (Abschnitt 10).
```

- [ ] **Step 3: Abschnitt 8 „Tests"**

Testzahl aktualisieren: `python -m pytest -q` lokal ausführen, die Zahl der bestandenen Tests (ohne den skip) eintragen statt „74". Nach dem Codeblock den Satz ergänzen:

```markdown
Der Linter ist Ruff mit einer bewusst schmalen Regelmenge (`ruff.toml`), damit
er Fehler findet, aber keine Umbauten am Code erzwingt.
```

- [ ] **Step 4: Neuer Abschnitt 10 „Betrieb", bisherige 10 und 11 werden 11 und 12**

Vor „## 10. Bewusst nicht enthalten" einfügen:

```markdown
## 10. Betrieb

Der Weg von der Quelle bis zur Cloud ist vollständig beschrieben und geprüft,
aber bewusst nicht ausgerollt. Nichts davon erzeugt laufende Kosten.

**Lokal starten (ein Befehl).** `docker compose up --build`, dann
`http://localhost:8040`. Die `.env` ist optional; ohne sie läuft der Server mit
den aufgezeichneten Ergebnissen. Konfiguration ausschließlich über
Umgebungsvariablen (`.env.example`), keine Werte im Image.

**Image.** Das `Dockerfile` baut in zwei Stufen auf `python:3.12-slim`:
Abhängigkeiten in Stufe 1, Laufzeitbild in Stufe 2 mit `app/`, `data/` und
`docs/index.html`, als Benutzer `app` (UID 10001) ohne Root-Rechte, mit
Healthcheck auf `/api/status`. Der Server schreibt Statusänderungen nach
`data/`; im Container ist das flüchtig, ein Neustart stellt den Stand des
Images wieder her. Die Pipeline (`.github/workflows/ci.yml`) baut das Image bei
jedem Push, prüft im Rauchtest, dass der Live-Pfad gesperrt ist, und schiebt es
bei einem Push auf `main` nach `ghcr.io/dangtu1190-tech/serviceanfragen-assistent`
(`latest` und `sha-…`). `pytest` liegt mit im Image, weil `requirements.txt`
keine Trennung in Laufzeit- und Testabhängigkeiten kennt; das kostet einige
Megabyte und ändert nichts am Verhalten.

**Pipeline.** Drei Jobs: Tests und Linter, Docker-Image, Terraform. Der Test
`tests/test_pipeline.py::test_kein_original_erreicht_das_modell` läuft als
eigener, benannter Schritt vor der übrigen Suite. Schlägt er fehl, wird kein
Image gebaut.

**Cloud-Deployment (Terraform, `infra/azure/`).** Azure Container Apps mit
Resource Group, Log Analytics Workspace (Tagesquote 0,5 GB), Container Apps
Environment, Container App mit externem HTTPS-Ingress, Key Vault und einer
User-Assigned Managed Identity, über die die App den Modellschlüssel liest.
Der Schlüssel steht nirgends in Code, Variablen oder State: Terraform legt nur
einen Platzhalter an, der echte Wert wird nach einem `apply` einmal mit
`az keyvault secret set` gesetzt (`terraform output secret_setzen`). Die
Pipeline führt `terraform fmt -check`, `terraform validate` und `terraform test`
aus; letzteres plant gegen einen Mock-Provider, also ohne Azure-Konto und ohne
Zugangsdaten, und prüft per Assertion unter anderem `min_replicas = 0`. Ein
`terraform apply` gibt es weder lokal noch in der Pipeline. Die Konfiguration
ist vollständig und validiert, aber nie angewendet worden; ein erstes `apply`
findet erfahrungsgemäß Kleinigkeiten (Verzögerung der Rollenzuweisung, weltweit
eindeutiger Key-Vault-Name, Sichtbarkeit des Pakets in der Registry).

**Scale-to-zero.** `min_replicas = 0` ist die entscheidende Zeile. Bei einem
Wert über 0 laufen die Replikate rund um die Uhr und werden auch ohne Traffic
berechnet; das ist der häufigste Grund für unerwartete Rechnungen. Mit 0 fährt
die App ohne Anfragen herunter und startet beim nächsten Aufruf in einigen
Sekunden neu. `max_replicas` ist auf 2 begrenzt, damit auch unerwarteter
Traffic gedeckelt bleibt. Dieselbe Entscheidung steht in `render.yaml` (Free-Plan
mit Spin-down) und `fly.toml` (`min_machines_running = 0`); beide Dateien sind
vorbereitet, nicht ausgerollt. Render bietet laut Doku einen Free-Plan, Fly.io
weist keinen mehr aus.

**Live-Modellpfad standardmäßig aus.** `LIVE_MODELLAUFRUFE=0` ist in Image,
Compose, Terraform, Render und Fly der Standard. Eine öffentlich erreichbare
Instanz arbeitet dann wie GitHub Pages mit den aufgezeichneten Ergebnissen; der
Verarbeiten-Endpunkt antwortet mit HTTP 403. Grund: Sonst zahlt der hinterlegte
Schlüssel für jeden Besucher, der auf „Verarbeiten" klickt. Der Langdock-Zugang
des Arbeitgebers wird für keinen Teil dieses Deployment-Wegs verwendet; die
Anbietervariablen in `terraform.tfvars.example` sind Platzhalter für ein
eigenes Konto.
```

- [ ] **Step 5: Abschnitt „Bewusst nicht enthalten" anpassen**

„Deployment-Automatisierung" aus der Aufzählung streichen und ersetzen durch „ein tatsächlich ausgerolltes Cloud-Deployment (der Weg dahin steht in Abschnitt 10, ausgerollt ist nichts)".

- [ ] **Step 6: Lesen und Commit**

README einmal komplett lesen: Nummerierung 1 bis 12 durchgehend, keine Gedankenstriche, alle genannten Dateien existieren (`ls` prüfen).

```bash
git add README.md
git commit -m "docs: Abschnitt Betrieb (Container, Pipeline, Terraform nur Plan, scale-to-zero, Live-Pfad aus), Badge

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
