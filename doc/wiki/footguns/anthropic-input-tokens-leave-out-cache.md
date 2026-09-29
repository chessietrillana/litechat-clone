# Anthropic's input_tokens leaves out cached tokens

## What happens

The three proxy interfaces count cached input tokens differently:

| Interface | Input field | Includes cached tokens? |
|---|---|---|
| OpenAI | `prompt_tokens` | Yes |
| Google | `promptTokenCount` | Yes |
| Anthropic | `input_tokens` | **No.** Cache reads are in `cache_read_input_tokens`. Cache writes are in `cache_creation_input_tokens`. |

So if we billed Anthropic's `input_tokens` alone, cached tokens would be free there, but paid on the other two.

## The rule

Cached tokens cost the same as normal input tokens (study NOTE Q9).

`proxy/adapters/anthropic.py` adds all three counts together:

    input_tokens = input_tokens + cache_read_input_tokens + cache_creation_input_tokens

- A missing count is 0.
- If all three are missing, `input_tokens` is `None` (no usage, so no charge).
- `cached_tokens` stays as the cache reads only. It is for information. It is not billed on top.

So `ChatResult.input_tokens` means "all input tokens, cached included" on every interface.
The saved `ChatMessage.input_tokens`, the log line, and the charge all use that number.

## Things to know

- Every cached count was 0 in all our live tests (2026-09-29). The fix is tested with a hand-written sample: `proxy/tests/fixtures/synthetic_anthropic_cache_tokens.json`.
- If a new interface is added, check how it counts cached tokens before billing it.
