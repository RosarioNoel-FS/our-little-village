# Staff sign-in and staging publishing

Implemented and running locally at **http://127.0.0.1:4180/**. The original draft-only preview remains at **http://127.0.0.1:4173/**.

Staff use their own invited email and an Our Little Village passphrase. They do **not** need GitHub accounts, the owner's GitHub password, or access to any GitHub repository. There is no public account signup or web administrator endpoint. The owner issues/revokes invitations from the server command line. An invitation works once, expires in 24 hours and identifies exactly one staff account.

## What is tested and what is not connected

The local mode has a real isolated Git repository, staff authentication, per-account drafts, server media decoding, image optimization, the existing HTML generator, revision checks, build states, separate staging pages and version restore. It has **no remote configured**, and cannot push to GitHub. It is explicitly labeled “on this Mac.” Local staging publish and restore have been exercised through the browser and HTTP tests.

The separate **GitHub App adapter is implemented and tested against controlled GitHub API fixtures**, including actual RSA JWT signing. It is not connected to a real App installation: no App ID, installation ID or private key was present in the environment. The staging branch and workflow were prepared using the owner-authorized repository connection, and the real GitHub build artifact passed checksum/path/repository/revision verification. This does not test the new App credentials or the hosted staff-to-GitHub flow. No suitable Our Little Village hosted service was found in connected Sites. The existing connected websites are unrelated and were not altered. This Python service uses its own dedicated HTTPS hosting rather than changing those Sites or their identity policies.

Production publishing is **not implemented or enableable through configuration**. Both modes accept only staging. The GitHub adapter has hardcoded repository `RosarioNoel-FS/our-little-village` (verified repository ID `1454198001`) and branch `staging/visual-cms`. Neither is supplied by a request or environment override. It never requests a GitHub Pages build or merges into main.

## Run and create staff access

From the repository root, with Python 3.12, Git, OpenSSL, ffmpeg and ffprobe available:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r editor/backend/requirements.txt
.venv/bin/python -m editor.backend.server
```

In another terminal, create an invitation for a real staff member:

```sh
.venv/bin/python -m editor.backend.manage invite --email staff@example.com --name 'Staff name'
```

The command prints a one-use local invitation link. Give it to that staff member through an appropriate private channel; this implementation does not send email. Staff open it and choose their own passphrase (14–128 characters). The token is in the fragment, is removed from browser history before requests, and is never put in an HTTP URL or request log. No permanent default/demo password is installed by the application. Browser-testing used a disposable account, which is revoked after testing.

To revoke access immediately, including active sessions:

```sh
.venv/bin/python -m editor.backend.manage revoke --email staff@example.com
```

For a passphrase reset, revoke the account and issue a fresh invitation for the same email. The staff member chooses the new passphrase. Passwords are not emailed or displayed by an administrator.

State defaults to ignored `editor/.state/backend/`. It contains a private SQLite database, a server CSRF key, the isolated staging repository and immutable release snapshots. The directory is mode 700; database/key files are mode 600. Back it up privately before moving to another server. Do not place this directory in a public static folder or a Git repository. Local HTTP is accepted only for loopback. Hosted configurations require an HTTPS origin.

## Staff workflow

1. Sign in and edit using the existing text/photo/video controls. Local auto-save, undo, recovery, desktop/mobile preview and backups continue to work.
2. **Save draft to staff account** stores a private server draft without publishing. **Open saved staff draft** restores that account's saved draft after confirmation. Local draft storage is separated by staff account.
3. **Publish to staging** requires review and a clear staging-only confirmation. The server independently validates every changed field and uploaded file, checks the content hash and Git revision, then builds/commits the staging update.
4. The interface reports queued/checking/building and shows the staging link only when a build has actually completed and been activated. Failed/conflicting operations do not pretend to be published.
5. **Staging history** restores a previous verified release as a new validated staging update. Restore is subject to the same revision checks, field restrictions and build pipeline.
6. **Load the published staging content** refreshes the editor baseline. Download a backup before discarding a local draft you want to keep.

The separate staging site is protected by staff sign-in. Staging pages show a visible “not the live website” banner. Account drafts are manual saves; the automatic indicator still describes browser-local saving. A saved staff draft can become stale after another publish; it is not silently applied over a newer site version.

## GitHub App setup — the remaining owner action

The owner must create/install the dedicated App. Existing Pages CMS authorization and this task's connected GitHub tool do not supply a private key for this new server, and are not reused as a staff credential.

1. Open [GitHub's new App registration](https://github.com/settings/apps/new). Use the reviewed [App manifest](deploy/github-app-manifest.json) as the settings reference: private App; website/homepage Our Little Village; webhook inactive; no user OAuth, callback or account permissions needed.
2. Grant repository permissions **Contents: read and write**, **Actions: read-only**, and the automatically required **Metadata: read-only**. Do not grant Administration, Workflows write, Pages write or organization/account permissions.
3. Install it under RosarioNoel-FS with **Only select repositories → our-little-village**, and no other repository. The server refuses an all-repositories installation or a selected installation containing more than that single repository. It first inspects installation scope with a metadata-only token, then requests a short-lived write token explicitly narrowed to the one verified repository ID. Staff never receive either token.
4. Generate the App's private key and put it directly in the hosting secret store or a read-only mounted server file, mode 400 or 600. Do not paste the private key into chat, browser code, a README, GitHub content or a public environment file. Configure its file path, the App ID and installation ID using the exact names in [staging.env.example](deploy/staging.env.example).
5. The reviewed staging source/workflow has been installed on `staging/visual-cms` in the same website repository, and its first real GitHub Actions build passed. Future setup should retain that branch and workflow. The workflow is `.github/workflows/visual-cms-staging.yml`. This is a one-time owner/developer setup operation: the runtime App deliberately has no Workflows-write permission and cannot install or modify workflows. Keep `main`, CNAME and the existing production CMS workflow unchanged.
6. Deploy the service on a dedicated HTTPS editor/staging hostname with durable private storage, using the supplied container and reverse-proxy examples. Set `OLV_PUBLISH_MODE=github-staging`. Create staff invitations on that server; invitation origins then point to that HTTPS domain.

The App's Contents permission is repository-wide at GitHub's permission level; the **server** restricts staff writes to the allowed JSON fields/media and staging branch. App credentials must remain protected. Repository branch rules should prevent the App from bypassing production-main review; do not grant it a bypass role. Do not interpret a repository-scoped App token as inherently field- or branch-scoped.

When configured, the server creates a batch commit with the expected parent, rechecks the head and advances the fixed staging ref with `force=false`. A competing normal update fails instead of being overwritten. GitHub runs the staging-only workflow. That workflow has **Contents read-only**, optimizes/builds with the existing scripts, and uploads an immutable artifact; it never writes a commit, invokes GitHub Pages or deploys production. The backend verifies the exact workflow path, branch, commit, successful result, artifact name/checksum, archive paths and embedded site/revision marker before activating the protected staging site. A commit or a successful save is not shown as a deployment. Older builds cannot replace a newer branch revision.

GitHub HTTPS uses a current pinned CA certificate bundle with verification enabled; an administrator may supply a trusted custom CA bundle through `SSL_CERT_FILE`. Certificate checks are never disabled. The App token stays in server memory and is refreshed before expiry. There is no personal-token or owner-OAuth fallback. Backend configuration has no “all repositories,” repository picker, raw GitHub URL or production branch option.

## Hosting artifacts

- [Dockerfile](deploy/Dockerfile): Python/Gunicorn runtime, FFmpeg/Git/OpenSSL, non-root service account.
- [Caddyfile.example](deploy/Caddyfile.example): dedicated HTTPS reverse proxy with a 110 MB request bound.
- [staging.env.example](deploy/staging.env.example): server-only configuration names; no secrets.
- Root `.dockerignore` excludes state, databases, `.env` files, PEM keys, Git metadata and preview scratch files.

Build the container from this repository root, supply a private writable volume for `/var/lib/olv`, mount the App key read-only, and keep the container's HTTP port behind the HTTPS proxy. Use one Gunicorn worker with threads as supplied; publishing also has an interprocess file lock. No shared/public hosting was configured during implementation. The Docker/reverse-proxy artifacts have not been deployed or tested against an external hosting provider.

The hosting administrator must provision TLS, persistent encrypted storage/backups and the dedicated hostname. Retain release snapshots according to the owner's storage/restore policy; this version does not silently delete history. The hosting service must allow the GitHub API and signed artifact-download domains. No additional broad app connection is required for staff.

## Validation and security boundaries

```sh
.venv/bin/python -m unittest editor.backend.security_checks -v
python3 -m unittest discover -s editor -p 'test_*.py' -v
node --test editor/model.test.js
node --check editor/app.js
```

Backend checks cover invitation use/expiry, password hashing, session expiry/revocation, CSRF/origin/host checks, HTTPS cookie attributes, rate limits, account draft isolation, protected fields/path/type rejection, arbitrary URLs/HTML/duplicate JSON, real image/video decoding, safe generated media names, atomic staging publish, actual image/video publishing, restore, conflicts, failed builds, idempotent retries, one-repository token narrowing, RSA JWT signatures, artifact revision binding/checksum and unsafe ZIP rejection. Together with preview tests, the suite has **34 tests**.

Passwords use scrypt with a unique salt; sessions use random opaque tokens stored as hashes, eight-hour absolute expiry and one-hour idle expiry, HttpOnly/SameSite=Strict cookies and Secure/__Host cookies on HTTPS. Changing requests require the exact configured Origin plus session-bound CSRF. Client-provided identity headers, repository names and field registries are never trusted. New image/video bytes are decoded on the server; client MIME, dimensions, duration, byte count and filename are not trusted. New filenames are content hashes under `assets/work/`. JSON is merged through only exact registered scalar paths, preserving protected and unknown fields. Existing validated JSON/media scripts are reused.

Sign-in and publishing failures are deliberately generic. Logs do not contain passphrases, invitation tokens, App private keys or installation tokens. Audit records contain account IDs, actions and job references. The original site's inline animation scripts require an inline-compatible CSP on its embedded/static pages; uploaded text is escaped and HTML uploads are not accepted.

This is a working, test-covered staging implementation, **not a claim of a completed external security audit or live GitHub App deployment**. Before any future production feature, verify the configured GitHub App end-to-end on hosted staging, test a restore there, review account/backup operations and separately authorize a production release. No production enable switch has been added here.
