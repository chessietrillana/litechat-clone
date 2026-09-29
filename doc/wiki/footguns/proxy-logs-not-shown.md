# Proxy log lines are not shown anywhere (yet)

## What happens

`proxy/client.py` logs one line per proxy call to the `proxy` logger:

- success at INFO level (tokens, time taken)
- failure at WARNING level

But the project has no `LOGGING` setting. So:

- **INFO lines are dropped.** You never see the success lines, even in `runserver`.
- **WARNING lines still show up** on the console (stderr). They come through Python's fallback handler, with no time or level shown. For example, `proxy_smoke` prints `proxy call failed interface=openai ... error=ProxyTimeout` above its own output.

This is standard Python behavior: a logger with no handler only prints WARNING and above, through a last-resort handler.

## Fix (not done yet)

Add a `LOGGING` setting that sends the `proxy` logger to the console at INFO level.
Do this in the chat or metering plan, when the lines become useful.

## Safety

The log lines never contain keys or message text. Tests in `proxy/tests/test_client.py` check this.
Keep it that way when adding a handler.
