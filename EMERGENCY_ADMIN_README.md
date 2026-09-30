# PAKAL – Emergency Admin Access

Keep this file with the deployment and share it only with the people responsible for PAKAL.
It never contains a password.

## 1. Where the admin console is

The console is served from a single secret-ish path, set by the `ADMIN_SECURE_PATH` environment variable.

| | |
|---|---|
| Default path | `/pakal-management-console` |
| Production URL | `https://<PAKAL_HOST>/pakal-management-console` (`PAKAL_HOST` is set in `.env`) |
| `/admin` | Always returns **404** – it is not a valid address anymore |

Deep links work too, for example `…/pakal-management-console/sso` or `…/pakal-management-console/nexus`.

If the path was changed and nobody remembers it, read it from the host:

```bash
grep ADMIN_SECURE_PATH /path/to/pakal/.env
docker exec pakal_appstore printenv ADMIN_SECURE_PATH
```

The container also logs an error at startup if the configured value is invalid, and falls back to the
default path. A valid value is one path segment: starts with `/`, 7–64 characters, letters, digits and `. _ ~ -`
only, and not `/admin`, `/api`, `/static` or `/health`.

In the portal, the admin (shield) button is shown only to users whose SSO / LDAP account carries the admin
role or group. Everyone else never sees a link to the console.

## 2. Normal sign-in (for reference)

1. Signed in to the portal with Keycloak or LDAP **and** in the admin role/group → opening the console signs
   you in automatically.
2. Otherwise the console shows a login form: Keycloak button, or an LDAP user in the admin group.

## 3. Emergency local login (Keycloak / LDAP down or misconfigured)

The local service account **`pakal`** is always checked first and does not depend on Keycloak or LDAP.

1. Open `https://<PAKAL_HOST>/pakal-management-console` (or your custom path).
2. The console never redirects to Keycloak on its own, so the login form appears even when Keycloak is down.
   (If you still hold a valid admin portal session you are taken straight in instead.)
3. Ignore the Keycloak button. In the form, enter:
   - **Username:** `pakal` (or the value of `LOCAL_ADMIN_USERNAME` / `ADMIN_USERNAME` if it was changed)
   - **Password:** the emergency password kept in your team's password vault
4. Press **Sign in**. You land on the Overview page with full admin rights.
5. Fix the broken integration (Keycloak / LDAP / Nexus pages), then sign out.

Five failed attempts from one address lock the form for 5 minutes (`LOGIN_MAX_ATTEMPTS`,
`LOGIN_WINDOW_SECONDS`). Wait, or restart the container to clear the counter.

### Which password is in effect?

Highest priority first:

1. A password saved in the console (**Keycloak & LDAP → Local admin**). Stored as a bcrypt hash in the
   database (`/data/pakal.db`). The Local admin card shows "database" as the source.
2. `LOCAL_ADMIN_PASSWORD` (plain text in the environment – avoid in production).
3. `ADMIN_PASSWORD_HASH` from `.env`.

There is no built-in password: if none of these is set, the emergency local login is disabled until you
create one (section 4).

## 4. Resetting a lost emergency password

Run on the Docker host.

1. Create a new hash (min. 10 characters, typed twice, nothing is echoed):

   ```bash
   docker exec -it pakal_appstore python -m pakal.security hash-password
   ```

2. Put it in `.env`, **inside single quotes** (the hash contains `$`):

   ```bash
   ADMIN_PASSWORD_HASH='$2b$12$...'
   ```

3. If a password was ever saved in the console, remove that override so the `.env` value applies:

   ```bash
   docker exec pakal_appstore python -c "from pakal import auth_config; auth_config.reset('local_admin')"
   ```

4. Recreate the container so it reads the new environment:

   ```bash
   docker compose up -d --force-recreate pakal
   ```

5. Sign in as in section 3, then store the new password in the vault.

## 5. After an emergency

- Check the container log for `Admin login (local)` lines and confirm every one was expected:
  `docker logs pakal_appstore 2>&1 | grep "Admin login"`.
- If the emergency password was shared outside the vault, rotate it (section 4).
