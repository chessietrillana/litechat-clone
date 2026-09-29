# Proxy log lines were not shown (fixed)

## What happened

`proxy/client.py` logs one line per proxy call to the `proxy` logger:

- success at INFO level (tokens, time taken)
- failure at WARNING level

At first the project had no `LOGGING` setting. So:

- **INFO lines were dropped.** You never saw the success lines, even in `runserver`.
- **WARNING lines still showed up** on the console (stderr). They came through Python's fallback handler, with no time or level shown.

This is standard Python behavior: a logger with no handler only prints WARNING and above, through a last-resort handler.

## Fix (done in the chat-sessions plan)

`config/settings.py` now has a `LOGGING` setting. It sends the `proxy` logger to the console at INFO level, with the time and level:

```
2026-09-29 07:27:32,702 INFO proxy: proxy call ok interface=openai model=gpt-5.6-luna status=200 seconds=1.4 input_tokens=183 output_tokens=15 cached_tokens=0 finish=stop
```

Side effect: `manage.py test` now prints these lines too, from the proxy client tests. They come from saved sample replies in the tests, not real calls. The tests still pass.

## Safety

The log lines never contain keys or message text. Tests in `proxy/tests/test_client.py` check this.
Keep it that way when changing the logging.
