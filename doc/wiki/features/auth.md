# Auth: sign up, log in, log out

Users sign up with a username and password. There is no email and no email verification.
Built with Django's own auth parts. There is no custom auth code except the sign-up view.

Plan: `doc/plan/1790661940_auth.md`.

## Sign up

- URL: `/accounts/signup/`.
- Fields: username, password, confirm password. This is Django's `UserCreationForm`.
- Password rules (Django defaults): at least 8 characters, not too common, not all numbers, not too close to the username.
- On success: the user is created, logged in, and sent to the home page.
- New users are not staff and not superusers.
- A logged-in user who opens this page is sent to the home page.

## Log in

- URL: `/accounts/login/`. Django's `LoginView`.
- On success: goes to `?next=` if given, else the home page.
- Wrong password: the page shows an error. The user stays logged out.
- A logged-in user who opens this page is sent to the home page.

## Log out

- URL: `/accounts/logout/`. Django's `LogoutView`.
- **POST only.** The nav bar has a **Log out** button inside a small form. A GET returns 405. See [the footgun](../footguns/django-logout-requires-post.md).
- After logout: sent to the login page.

## Home page

- URL: `/`. Needs login. Visitors are sent to `/accounts/login/?next=/`.
- Shows "Hello, <username>." The chat plan will replace this page.

## Settings

In `config/settings.py`:

| Setting | Value | Why |
|---|---|---|
| `LOGIN_URL` | `/accounts/login/` | Where `login_required` sends visitors. A path, not a URL name (see below). |
| `LOGIN_REDIRECT_URL` | `home` | Where to go after login when there is no `next`. |
| `LOGOUT_REDIRECT_URL` | `login` | Where to go after logout. |

`LOGIN_URL` is a path because `login_required` looks up a URL name on every redirect.
When the name did not exist yet, the redirect crashed with `NoReverseMatch`. The path always works.

## Not built yet

- Password change and password reset (reset needs email).
- Profile page.
- An admin can set a new password for a user in the Django admin: **Users** → pick the user → **Reset password**.

## Tests

- `accounts/tests.py`, class `LoginTests`: login form, good and bad login, `next`, redirects, logout by POST, GET logout refused (405), nav shows the right links.
- `accounts/tests.py`, class `SignUpTests`: form has only username and two passwords, valid sign-up, not staff, taken username, mismatched passwords, weak password, redirect when logged in.
- `config/tests.py`, class `HomePageTests`: visitor redirect, logged-in user sees their name.
