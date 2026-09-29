# Django logout needs a POST, not a link

## What happens

Since Django 5.0, `LogoutView` accepts only POST.
A plain link like `<a href="/accounts/logout/">Log out</a>` sends a GET.
Django answers **405 Method Not Allowed**, and the user stays logged in.

Many older tutorials still show a logout link. They are out of date.

## Fix

Use a small form with a CSRF token. Style the button to look like a link if you want.

```html
<form method="post" action="{% url 'logout' %}">
  {% csrf_token %}
  <button type="submit" class="link-button">Log out</button>
</form>
```

This app does this in `templates/base.html`.

## Test

`accounts/tests.py` has `test_logout_by_get_is_refused`. It checks that GET returns 405 and the user stays logged in.
