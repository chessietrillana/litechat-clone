# Proxy requests can hang: always set a timeout

## What happens

Some requests to https://proxy.litechat.ai hang. The connection opens slowly or never.
On 2026-09-29, about 5 of 18 test requests hit a 30 second timeout. The same request worked when run again.

Reply times also vary a lot for the same tiny prompt. In one `proxy_smoke` run on 2026-09-29:

- google: 1.6 s
- anthropic: 13.7 s
- openai: timed out at 30 s. It took 1.9 s when run again right after.

So a slow success can come close to the 30 s limit. Watch this once real chats (with long histories) exist.

Without a timeout, a request can hang for minutes.
Retries make it worse. One test used a 90 second timeout with 3 retries. It hung for more than 5 minutes.

## Rules

- Set a timeout on every proxy request. Use 30 seconds for now.
- Do not retry by default. The proxy docs say: do not retry after partial output. Usage can be unknown after a failure.
- If a request times out, show the user a clear error. Do not charge the user unless the proxy returned usage.
- The code follows these rules: `proxy/transport.py` (one request, no retry) and `PROXY_TIMEOUT_SECONDS = 30` in settings.
- To check the proxy by hand: `venv/bin/python manage.py proxy_smoke`. If one interface times out, run it again with `--interface <name>`.

## Related

- [Python HTTPS certificates on macOS](python-ssl-certificates-macos.md)
