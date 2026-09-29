"""Errors raised by the proxy client.

`user_message` is safe to show to users. `detail` is for logs and admins.
Neither may ever contain an API key.
"""

NOT_SET_UP = 'This model is not set up. Please tell the site admin.'


class ProxyError(Exception):
    user_message = 'Something went wrong talking to the model.'

    def __init__(self, detail='', status=None):
        self.detail = detail
        self.status = status
        super().__init__(f'{type(self).__name__} (status={status}): {detail}')


class ProxyConfigError(ProxyError):
    user_message = NOT_SET_UP


class ProxyTimeout(ProxyError):
    user_message = 'The model took too long to answer. Please try again.'


class ProxyConnectionError(ProxyError):
    user_message = 'Could not reach the model service. Please try again.'


class ProxyAuthError(ProxyError):
    user_message = NOT_SET_UP


class ProxyRateLimitError(ProxyError):
    user_message = 'Too many requests right now. Please wait a moment and try again.'


class ProxyBadRequestError(ProxyError):
    user_message = 'The model could not handle this request.'


class ProxyUpstreamError(ProxyError):
    user_message = 'The model service had a problem. Please try again later.'


class ProxyResponseError(ProxyError):
    user_message = 'The model sent a reply we could not read.'
