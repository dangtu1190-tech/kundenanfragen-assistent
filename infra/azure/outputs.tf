output "app_url" {
  description = "Öffentliche HTTPS-Adresse der Container App (nach einem apply)."
  value       = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}

output "key_vault_name" {
  description = "Name des angelegten Key Vault."
  value       = azurerm_key_vault.kv.name
}

output "secret_setzen" {
  description = "Nach dem apply einmal ausführen; der Wert kommt aus der eigenen Ablage, nie aus dem Repo."
  value       = "az keyvault secret set --vault-name ${azurerm_key_vault.kv.name} --name ${var.key_vault_secret_name} --value '<SCHLUESSEL>'"
}
