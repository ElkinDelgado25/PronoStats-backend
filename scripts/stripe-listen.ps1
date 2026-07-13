# Escucha webhooks de Stripe en local y los reenvia al backend de PronoStats.
# Requisito: Stripe CLI instalada (https://stripe.com/docs/stripe-cli)
#
# Uso:
#   cd PronoStats-backend
#   .\scripts\stripe-listen.ps1
#
# Copia el whsec_... que imprime y pegalo en STRIPE_WEBHOOK_SECRET del .env

$port = $env:STRIPE_FORWARD_PORT
if (-not $port) { $port = "8001" }

Write-Host "Reenviando eventos Stripe -> http://localhost:$port/wallet/stripe/webhook"
stripe listen --forward-to "localhost:$port/wallet/stripe/webhook"
