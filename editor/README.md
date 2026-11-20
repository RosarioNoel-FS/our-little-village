# Our Little Village visual editor — local draft preview

Ready for staff testing. Open **http://127.0.0.1:4173/** on this Mac while the preview server is running.

To restart, double-click `Start Editor.command` in the repository's top folder, or run from that folder:

```sh
python3 editor/serve.py --open
```

Requires Python 3.10+; no Python or JavaScript package installation is needed to use the editor. Keep the Terminal window open. Control-C stops the preview. If the port is already in use, the existing preview may still be running; open the URL above. For a separate port use `--port 4174`, noting that drafts are tied to the browser origin, including its port.

## Try it

1. Choose a page at the top. Click a heading in the website, change its words, and select **Apply to preview**. Headings support the existing `*accent*` convention.
2. Click a photo or looping video. **Replace video** accepts MP4 (H.264) or WebM. Uploaded videos are checked for real format, browser decoding, size (20 MB), duration (2 minutes) and resolution (up to 4K); local video bytes are capped at 60 MB per draft. A built-in playback preview, original/draft review, automatic recovery and Revert/Undo are available. MOV needs to be exported to MP4 first. Clip replacements keep existing looping, muted/inline behavior and respect paused/reduced motion.

   For photos, choose one from this computer or the existing library. Check its actual crop in the page and inspect the full photo in the controls. Write a short description and apply it.
3. Switch between **Desktop** (1280 CSS pixels) and **Mobile** (390 CSS pixels). The preview scales to fit the editor; it retains its true internal viewport size.
4. Open **Review changes** to compare original and draft content. Try Undo, a per-field Revert, or Discard all changes.
5. Refresh after the saved indicator appears. Your draft, uploaded photos/videos, selected field and unfinished words recover automatically in the same browser.
6. Download a draft backup. **Restore draft backup** accepts a backup made against this exact content version. It asks before replacing the current local draft.

Use **Find something to edit** to search the page's words, photos and videos. Editable content supports Tab and Enter/Space; editing controls use normal keyboard navigation. On narrow screens the editing controls appear below the preview. Changes save in IndexedDB, not to website files. Use the same browser URL (`127.0.0.1`, not a different hostname) to recover the same draft. Private browsing, clearing browser data or switching browsers can remove or hide local drafts; use backups for safekeeping. Undo history lasts for the current tab session; per-field Revert remains available after recovery.

## Deliberate limits

This is a local draft-only prototype. **There is no sign-in, content-write API, GitHub credential, publish endpoint, workflow trigger or deployment integration.** The server binds only to `127.0.0.1`; it is not a staff-accessible hosted service. Do not expose this development server to a network. Publishing is disabled in the interface, and POST requests are unsupported.

Editing covers the existing visible text, images and image descriptions for all six category pages and the home “What we do” area: 349 exact field paths, including 51 replaceable image placements and 12 looping video placements. Blank optional content remains hidden; this preview replaces existing content rather than adding or removing blocks. Image descriptions may be edited through the corresponding photo controls. Video replacement applies separately to the six category-page hero loops and the six home-panel loops; replacing one placement does not overwrite a shared media file or automatically change another placement. The opening film and the contact-page loop stay protected. No timeline editing, transcoding, sound editing or poster editing is included. Text is required, bounded in length and escaped; arbitrary HTML is rejected. Accent markup is supported only where the existing generator supports it. Image uploads are decoded and checked against JPEG/PNG/WebP signatures, limited to 5 MB each, 50 megapixels and approximately 16 MB of photo bytes per draft. Cropping controls inspect images; they do not change site layout or persist CSS changes.

Navigation, link destinations, SEO, contact details, branding, the opening film, contact-page media, testimonials, colors, section order, card structure and animation code are protected. External links in the embedded preview do not leave the editor. Original animation scripts remain in place; changed text updates immediately without replaying its letter entrance animation. Home opens at its supported section and skips the protected intro film in the preview only.

## Implementation

- `cms/build.py`: optional `OLV_EDITOR_PREVIEW=1` bindings. Each content string carries its exact JSON Pointer from the JSON loader through existing templates. Explicit text/image contexts emit stable `data-cms` paths. No text matching or positional DOM inference is used. `OLV_EDITOR_OUTPUT` directs output to a separate folder. Normal builds are byte-identical to the checked-in site.
- `editor/serve.py`: regenerates annotated pages into ignored `editor/.preview/`, validates every binding against a narrow path policy and serves only whitelisted assets/pages plus a read-only bootstrap manifest.
- `editor/field-registry.json`: reviewable snapshot of all supported JSON pointers, source files, labels, kinds, lengths and matching alt paths. Runtime registry is regenerated from the current content and explicit bindings.
- `editor/model.js`: field validation, draft recovery validation, safe accent rendering, image/video signatures, video limits and review data.
- `editor/app.js`: accessible controls, local drafts, backup/restore, image validation, review and undo.
- `editor/bridge.js`: origin/source-checked messages, click/keyboard selection, escaped text and image updates. The bridge is injected only into preview copies.

The baseline hash covers all seven JSON documents. If they change, recovery/restore refuses to apply the stale draft, preserves a download of it and offers a fresh start. This is conflict detection for local drafts, not a replacement for eventual GitHub SHA checks. Use one editing tab at a time; simultaneous tabs do not merge local drafts.

## Verification

From the repository root:

```sh
python3 -m unittest discover -s editor -p 'test_*.py' -v
node --test editor/model.test.js
node --check editor/app.js
```

Node 20.11+ is needed only for developer checks. Tested with Python 3.12.2 and Node 26.13.0. See `TEST_EVIDENCE.md` for observed browser results and limitations.

## Optional video content model

Category JSON may include a `video` string (JSON Pointer `/video`). Each home panel may include its own `video` string, for example `/panels/private/video`. Sources must match `assets/work/<safe-filename>.mp4` or `.webm`, optionally with a leading slash. When these optional keys are absent, the generator and editor use the original theme clip. Existing JSON documents have not been changed merely to add defaults; normal public builds remain byte-identical. The runtime registry exposes explicit defaults for editing. A future backend must allow an `add` for these exact optional keys while preserving other content and shape.

Home loops were originally created dynamically by inline JavaScript. Preview bindings are attached explicitly to their existing arch frames. For saved home source overrides, the generator emits `data-video-src` and conditionally references `assets/video-sources.js`; the original script still creates the video and controls its intersection playback. Default builds omit these additions. Category templates use the validated optional source directly. No text or positional selector inference is involved.

Existing image/text drafts keep their baseline content hash and still recover after this editor update. Binary media is validated again during recovery and backup restore; video decoding is checked before applying it. Large drafts may reach a browser storage quota, in which case the interface reports the save failure and offers a backup rather than claiming it saved. Backups support up to 110 MB. Browser codec support still matters; a valid MP4 container with an unsupported codec is rejected with an export-to-H.264 message.

## Staff sign-in and staging publishing

A separate protected backend has now been implemented. The draft-only server described above stays available and cannot publish. For independent staff invitations, account drafts, secure field/media validation, local staging publish/build/restore, the repository-only GitHub App adapter and the remaining owner configuration, see [backend/README.md](backend/README.md). The new local staff service uses port 4180; the original draft-only preview uses port 4173.

The real App installation and dedicated HTTPS hosting remain unconfigured. Production publishing remains disabled in both modes. The original preview/video work and this backend have not changed production main or the existing production CMS workflow.
