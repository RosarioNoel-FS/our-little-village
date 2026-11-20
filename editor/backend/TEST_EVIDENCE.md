# Staff backend verification — November 20, 2026

## Completed locally

The original draft preview remains separate on port 4173. The new protected staff service runs on port 4180 under Gunicorn 27.0.1 with one threaded worker and persistent private SQLite/release storage.

A disposable invited test account was created outside the browser using the owner provisioning code. In the browser:

1. Anonymous access to the staff editor redirected to its own sign-in screen; no GitHub sign-in was presented.
2. Signed in with the existing disposable account. The editor showed the authenticated staff name and a staging-only publish target.
3. Changed the birthday heading to `Birthday *Staff Test*`, applied/reviewed it, and saved a staff account draft.
4. Published after the staging confirmation. The UI reported a completed local build and exposed the separate staging link.
5. Opened `/staging/parties.html` independently and verified the changed heading plus the “not the live website” banner.
6. Restarted the backend; the staff session persisted. A stale local draft was preserved for recovery rather than silently overwriting the newer staging version.
7. Opened Staging history, restored the earlier release, waited for a new successful build and independently verified the original birthday heading returned.
8. Loaded the published staging content into the editor without a stale empty-draft recovery prompt.

All browser publish/restore operations affected only the backend's isolated local repository, which has no remote. Browser-test credentials are test fixtures, not a default installation account. The disposable browser account is revoked after verification; the owner receives an independent local invitation to set their own staff passphrase.

## Automated checks

**34 tests** pass: 17 backend checks, 9 generator/preview Python checks, and 8 client model checks. These include:

- Single-use/expired invitations, scrypt password hashes, hashed session tokens, idle/absolute expiry and revocation.
- Host/Origin/CSRF enforcement, anonymous denial, rate limits, HttpOnly/SameSite cookies, and Secure/__Host cookies with an HTTPS origin.
- Account draft separation and no public signup, repository picker or administrative account API.
- Protected path/field/type rejection, duplicate JSON rejection, safe escaping, approved local media and real server-side image/video decoding.
- Real local commits, image optimization, generated HTML builds, actual photo/video replacement publishing, restore, failed-build retention, stale revision conflicts and idempotent retries.
- Exact App installation/token scope, no broad write-token creation on a misconfigured installation, fixed staging branch, no forced ref updates and protected repository paths.
- Real RSA JWT signing/verification, private-key file permissions, exact workflow/commit selection, failed build handling, mandatory artifact checksum, archive traversal rejection, and immutable remote snapshot revisions when a newer head appears.
- Original public generated HTML remains byte-identical for unchanged content. Existing text/photo/video previews, draft recovery and model restrictions still pass.

Run commands are in README.md. GitHub protocol calls use controlled fixtures in backend tests. This is not a third-party penetration test, a cross-browser matrix or a claim of tested credentials that were not provided.

## Actual GitHub staging setup/build

Prepared the `staging/visual-cms` branch in `RosarioNoel-FS/our-little-village` using the owner-authorized repository connection. The existing production `main` remained at `bd1004a258479594984062a26e4dc7069073d98e`; its CMS workflow, Pages settings, CNAME and content were not changed. No other repository/deployment was modified.

The [first staging workflow run](https://github.com/RosarioNoel-FS/our-little-village/actions/runs/44775438153) succeeded for staging seed commit `a695efbbefc2f9544e7df80b02c3a30c40fcc6c7`. Its 15,719,613-byte artifact was downloaded through the connected repository tool. SHA-256 matched GitHub's digest `2b129bac5d88017e02976587ed86dbb0309c8c897fece4c4e3dc71d4a81acba1`. The backend's actual archive validator accepted all paths, required content files and the exact site/branch/revision marker.

This proves the staging workflow/build/artifact path. It does **not** prove authentication with the new dedicated App: no real App ID, installation ID or private key was available. The owner connection used for setup is not stored in the backend or used for staff publishing.

A local Python CA-bundle issue was corrected by using pinned certifi with TLS verification enabled. An HTTPS request to GitHub then returned 200; no certificate verification was bypassed.

## Remaining external configuration

The owner must create and install the dedicated private App only on the website repository and configure its private key through the server secret store. Dedicated HTTPS hosting, persistent private storage and an editor/staging hostname must also be provisioned. Container/reverse-proxy/configuration artifacts are supplied but have not been deployed to a hosting provider. The configured App-to-GitHub staff publish and restore must be tested there before any future production feature. Production publishing remains unsupported and disabled.
