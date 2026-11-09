# Browser tests

These drive a real Chrome against a running site (the Docker stack, or `npm run dev`) and test the
main staff flows: signing in, publishing a notice with a photo and a PDF, photos for an activity,
page content, enquiries, the draft preview link, old-address redirects, and the phone layout. Every test removes what it created.

```bash
docker compose up -d --build          # or: npm run dev (with the backend running)

# two staff accounts for the tests (make them once; use your own passwords)
docker compose exec backend python -m app.cli create-admin --email e2e.editor@example.org --name "E2E Editor" --role editor
docker compose exec backend python -m app.cli create-admin --email e2e.boss@example.org   --name "E2E Boss"   --role super_admin
# the super admin must have two-factor login: sign in once, set it up on "My account", and keep the
# setup key (the long text) as E2E_ADMIN_TOTP_SECRET

E2E_EDITOR_EMAIL=e2e.editor@example.org E2E_EDITOR_PASSWORD='...' \
E2E_ADMIN_EMAIL=e2e.boss@example.org E2E_ADMIN_PASSWORD='...' E2E_ADMIN_TOTP_SECRET='...' \
npm run e2e
```

Tests that need an account that is not configured are skipped. Other settings: `E2E_BASE` (default
`http://localhost:3000`), `E2E_CHROME` (path of Chrome; default `/usr/bin/google-chrome`).
