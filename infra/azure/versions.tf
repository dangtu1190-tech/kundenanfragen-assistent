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
