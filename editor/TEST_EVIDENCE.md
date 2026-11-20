# Verification evidence — November 20, 2026

Source inspected: `RosarioNoel-FS/our-little-village`, main/feature branch at `bd1004a`. The claimed `feature/visual-editor-text-images` branch exists and matched main at checkout. Work is isolated on local branch `preview/local-draft-editor`; no push or deployment was performed.

## Automated checks

The initial text/image suite passed seven Python tests and six Node tests (13 total); the video follow-up below expands this to 17:

- Every supported existing visible nonempty content string has an explicit path binding on all seven editable areas.
- Protected fields (destinations, layout flags, SEO, other pages, invalid/prototype paths) cannot be registered or edited.
- Every image binding points to existing approved media and its exact associated alt-description path.
- Normal builds reproduce all nine checked-in generated pages byte for byte, including home, contact and privacy.
- Preview bindings occur only inside the supported home section; contact has none.
- Existing generator image-path restrictions and HTML escaping remain effective.
- HTTP routes serve the preview, deny hidden/repository files and expose no publish/write endpoint (POST returns 501).
- Client validation accepts every baseline field, rejects non-string values, empty required text, excessive length, HTML, unclosed accent markup and unapproved image sources.
- JPEG/PNG/WebP signatures are distinguished from renamed/non-image files.
- Recovery preserves validated changes and rejects stale baselines, protected paths and unsafe media data.

JavaScript syntax checks passed. Image optimizer and publishing workflow files are unchanged; the optimizer was not run against the original media directory.

## Browser checks observed in the Codex in-app browser

- Click-selected the birthday heading, changed it to `Birthday *Magic*`, applied it and saw the rendered heading and review count change. Refresh recovered the heading.
- Changed the home section heading to `What *we create*`; saw the exact heading update within the existing home page. Reverted it.
- Independently applied `Preview *test*` to the heading on **Birthday Parties, Private Events, Weekly Classes, Creative Arts, Special Events and GO OLV**. Waited for each rendered heading to become `Preview test`; reverted each afterward.
- Uploaded the existing local `parties-b.jpg` as a new draft photo. The selected in-page image used a decoded JPEG data URL. Applied an alt description; refreshed, then confirmed the recovered image loaded and the exact alt text persisted.
- Checked the full-photo inspection control and returned the image and description to their originals.
- Enter/keyboard selection opened the editing controls. Entering `<b>Not allowed</b>` showed the plain-text error and did not apply it.
- Review displayed original and draft words. Downloaded a draft backup, reverted its change, restored the downloaded JSON through the file chooser and confirmation, and verified the restored heading. Undo restored the previous local draft.
- At a 390 × 844 editor viewport, the document width and scroll width both measured 390 pixels: no horizontal overflow. The mobile preview's actual internal width measured 390 CSS pixels. Desktop uses 1280 CSS pixels and scales to fit. Tested the 1440 × 1000 editor breakpoint as well.
- All test changes were reverted. The handoff starts with zero applied changes. Undo history is cleared by refresh.

Screenshot: `../../editor-preview.png` shows the original birthday page with the heading selected and large editing controls. The browser's default viewport was restored after responsive testing.

## Limits

These checks validate a local draft preview, not a hosted authenticated CMS. Authentication, server-side publishing authorization, GitHub commit conflicts and actual Actions/Pages build states remain integration work and were not claimed as tested. No production publish was attempted. No real phone hardware test, cross-browser matrix, screen-reader audit or pixel-by-pixel animation comparison was performed. The original animation code and public generated HTML remain unchanged.


## Video replacement follow-up

The user expanded the original scope to allow replacing existing looping videos. No timeline or layout editing was added. Source inspection found six category-page loops sourced from the theme name and six home-panel loops created dynamically in the existing inline script. The opening film and contact-page loop remain outside the registry.

The expanded suite passes **17 tests: nine Python and eight Node**. Added coverage checks all 12 exact video paths/defaults, preservation of the original content hash for existing drafts, optional-source rendering on both templates, rejection of arbitrary/traversal/MOV sources, MP4/WebM signatures, MIME mismatches, file byte limits, duration/resolution limits, invalid audio-only dimensions, cross-kind media rejection and corrupted recovered video data. Normal builds still reproduce all nine original HTML outputs byte for byte.

Observed browser results:

- On Private Events, selected the loop and used **Replace video** to upload the existing local `assets/work/art.mp4` as a new draft. Browser decoded it as a 540 × 960, 4.7-second clip. Confirmed the actual embedded source was a `data:video/mp4` URL, readyState 4, with no media error.
- Started playback in the inspector; confirmed `paused=false`, advancing currentTime, muted, loop and inline attributes. The in-page replacement also played with the same attributes.
- Refreshed the editor and confirmed the uploaded video source and duration recovered, with readyState 4 and no media error.
- Tested Revert and Undo. Review displayed separate native players labeled Original video and Draft video.
- On Home, selected the Private Events looping video through the accessible field list, applied the existing `art.mp4` clip, and confirmed the exact home binding's video source changed to `/site/assets/work/art.mp4`, duration 4.7, with no media error. Refresh recovered that replacement. Reverted it afterward.
- Confirmed the Private Events loop is keyboard selectable and its replacement controls work with a true 390-CSS-pixel mobile preview.
- Wrapped selection around the existing video frame rather than the native video itself so unloaded/decorative clips remain keyboard-editable and do not expose a disabled native media button as their editing affordance.

All follow-up test replacements were reverted before handoff. The active server returned HTTP 200. A prior coordinator curl failure was traced to a loopback network sandbox denial, while the server remained listening; it was not a server outage. `../../video-editor-preview.png` shows the updated controls. Video-capable draft backup data is validated by the recovery tests; a separate large-video backup/download stress test and a cross-browser codec matrix were not performed. The previous image/text backup restore was browser-tested.
