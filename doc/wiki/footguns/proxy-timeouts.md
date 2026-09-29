# Proxy requests can hang: always set a timeout

## What happens

Some requests to https://proxy.litechat.ai hang. The connection opens slowly or never.
On 2026-09-29, about 5 of 18 test requests hit a 30 second timeout. The same request worked when run again.

Without a timeout, a request can hang for minutes.
Retries make it worse. One test used a 90 second timeout with 3 retries. It hung for more than 5 minutes.

## Rules

- Set a timeout on every proxy request. Use 30 seconds for now.
- Do not retry by default. The proxy docs say: do not retry after partial output. Usage can be unknown after a failure.
- If a request times out, show the user a clear error. Do not charge the user unless the proxy returned usage.

## Related

- [Python HTTPS certificates on macOS](python-ssl-certificates-macos.md)
