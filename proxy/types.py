from dataclasses import dataclass

ROLES = ('user', 'assistant')

# Normalized finish reasons. Adapters map each provider's value to one of these.
FINISH_STOP = 'stop'
FINISH_LENGTH = 'length'
FINISH_FILTERED = 'filtered'
FINISH_TOOL_CALL = 'tool_call'
FINISH_OTHER = 'other'


@dataclass(frozen=True)
class Message:
    role: str  # 'user' or 'assistant'
    content: str


@dataclass(frozen=True)
class ChatResult:
    text: str
    # All input tokens, cached ones included, on every interface. This is what is billed.
    input_tokens: int | None
    output_tokens: int | None
    cached_tokens: int | None
    finish_reason: str
    raw_finish_reason: str | None
    response_id: str | None
    model: str | None
