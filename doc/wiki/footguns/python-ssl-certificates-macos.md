# Python HTTPS fails on macOS: certificate verify failed

## What happens

Python from python.org on macOS does not ship with trusted root certificates.
Any HTTPS call from Python fails, for example a call to the proxy:

```
SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: unable to get local issuer certificate
```

curl works fine on the same machine. curl uses the system certificates. Python does not.

## Fix

Run this once per Python install:

```
open "/Applications/Python 3.11/Install Certificates.command"
```

It installs `certifi` and links its bundle to Python's OpenSSL cert file.
This was done on the main dev machine on 2026-09-29.

## How to check

```
venv/bin/python -c "import urllib.request; print(urllib.request.urlopen('https://proxy.litechat.ai/docs', timeout=30).status)"
```

It should print `200`.

## Note

A new machine or a new Python install needs the fix again.
The app code cannot fix this by itself unless we add `certifi`. We have not done that.
