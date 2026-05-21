# UPDATE-8: Replace favicon with the new SWEEPSTAKELADS 2026 set

The favicon files in `assets/` are a leftover from the previous Euros 2024
build of this app and still show that branding in browser tabs and bookmarks.
A new favicon set generated for the 2026 World Cup app is sitting in the
repo-root temp folder `favicon_io-3/`. This update swaps the new set in,
removes the temp folder, and is otherwise zero-code.

Dash auto-serves `assets/favicon.ico` as `/favicon.ico` (see `app.py` line 429
— no `index_string` override, no `meta_tags` `link` entries). That's the only
file the browser actually fetches today. The other six files in the set
(`favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png`,
`android-chrome-192x192.png`, `android-chrome-512x512.png`,
`site.webmanifest`) are not currently linked from `<head>`, but they belong
with the set and we keep them in `assets/` for parity and for any future
wiring (e.g. PWA install, mobile bookmark icons). Today's swap therefore
takes effect via the `.ico` file; the PNGs and webmanifest are housekeeping.

---

## Branch

`feat/new-favicon` off `main`. Single PR. Merge after CI is green and after
confirming the new icon shows in a hard-refreshed browser tab locally.

---

## Scope

**In:**

- Replace these six files in `assets/` with the matching files from
  `favicon_io-3/` (overwrite):
  - `favicon.ico`
  - `favicon-16x16.png`
  - `favicon-32x32.png`
  - `apple-touch-icon.png`
  - `android-chrome-192x192.png`
  - `android-chrome-512x512.png`
- `site.webmanifest` — byte-for-byte identical between the two folders
  (verified via `diff -q`), so technically no action is needed. Copy it
  anyway so the swap is atomic and there's no risk of a half-swapped state.
- Delete the temp folder `favicon_io-3/` entirely after the copy is done.
- `updates_documentation/UPDATE-8.md` — this file, for the documentation
  trace.

**Out:**

- Any change to `app.py`. Dash auto-serves `assets/favicon.ico` from the
  `assets/` directory; no `index_string` override or `<link>` tag is needed.
  The other PNGs and the webmanifest are unreferenced today and stay that
  way.
- `index_string` customisation to add `<link rel="apple-touch-icon" ...>`
  etc. Tempting, but explicitly out — keep this update a pure asset swap.
  If we later want PWA install / proper mobile home-screen icons, that's a
  separate PR with its own spec.
- `scraper.py`, `scoring.py`, `tournament.py`, `assets/s1.css`,
  `assets/*.csv`, any test file. None of these have any favicon dependency.
- `CLAUDE.md` edits. The favicon files aren't mentioned in the architecture
  notes today; adding a one-line note is optional and probably noise.
  Skip it.

---

## Files to change

### 1. Copy the six image files from `favicon_io-3/` to `assets/`, overwriting

From the repo root:

```bash
cp favicon_io-3/favicon.ico                  assets/favicon.ico
cp favicon_io-3/favicon-16x16.png            assets/favicon-16x16.png
cp favicon_io-3/favicon-32x32.png            assets/favicon-32x32.png
cp favicon_io-3/apple-touch-icon.png         assets/apple-touch-icon.png
cp favicon_io-3/android-chrome-192x192.png   assets/android-chrome-192x192.png
cp favicon_io-3/android-chrome-512x512.png   assets/android-chrome-512x512.png
cp favicon_io-3/site.webmanifest             assets/site.webmanifest
```

(The last line is a no-op content-wise; included for completeness so the
implementer doesn't have to think about it.)

### 2. Delete the temp folder

```bash
rm -rf favicon_io-3/
```

Verify with `ls` that `favicon_io-3/` is gone from the repo root.

### 3. Stage the changes

`git status` should now show:

- Modified: `assets/favicon.ico`
- Modified: `assets/favicon-16x16.png`
- Modified: `assets/favicon-32x32.png`
- Modified: `assets/apple-touch-icon.png`
- Modified: `assets/android-chrome-192x192.png`
- Modified: `assets/android-chrome-512x512.png`
- (Possibly unchanged: `assets/site.webmanifest` — if git sees no diff, that's
  fine; the source and destination are byte-identical.)
- Deleted (untracked): `favicon_io-3/` and its seven contained files —
  these were never committed, they only show in `git status` as removals
  from the untracked list, not as `git rm`s.
- New: `updates_documentation/UPDATE-8.md`

Also, the implementer should check for and clean up these untracked stale
backup files seen in the initial `git status` if (and only if) they're sure
they don't need them — but **default to leaving them alone**, this update
is just the favicon swap:

- `assets/fixtures.csv.bak`
- `assets/last_updated.txt.bak`

These are out of scope for this PR. Mentioned only so the implementer
doesn't accidentally stage them.

---

## Tests

`uv run pytest -q` must stay green. No test touches favicon files, so this
is a no-op for the suite — but run it anyway to confirm nothing's broken.

```bash
uv run pytest -q
```

There are no new tests to add. Testing image-file replacement via pytest is
overkill; visual verification (next section) is the right gate.

---

## Visual verification (do this before opening the PR)

1. **Clear local browser cache or use a private window.** Favicons are
   cached aggressively — even a hard refresh (Cmd-Shift-R) sometimes doesn't
   bust the icon cache in Chrome. The most reliable check is a fresh
   incognito/private window.
2. `uv run python app.py` — open `http://127.0.0.1:8050/` in a private
   window.
3. Look at the **browser tab** — the icon next to the title
   "SWEEPSTAKELADS 2026" should be the new design, not the old Euros 2024
   one.
4. Visit `http://127.0.0.1:8050/favicon.ico` directly — the browser should
   render the new `.ico` file. (This is the canonical proof that Dash is
   serving the replacement.)
5. Open DevTools → Network tab, reload, filter to `favicon` — confirm a
   200 response and the file size matches the new file (`15406 bytes` for
   `favicon.ico`; same as the old file by coincidence, but the byte
   contents differ — easier to confirm visually).
6. Optional: visit `http://127.0.0.1:8050/assets/apple-touch-icon.png` etc.
   in the address bar — each should render the new design. Not strictly
   necessary since nothing in `<head>` links to them, but confirms the
   asset copy worked.

If the tab icon stubbornly shows the old icon:

- It's almost certainly the browser cache. Try a different browser, or
  Chrome's "Clear browsing data → Cached images and files" for the last
  hour.
- Confirm `assets/favicon.ico` on disk is the new file via
  `file assets/favicon.ico` (ICO format) and compare bytes with
  `cmp favicon_io-3/favicon.ico assets/favicon.ico` — should report no
  output (identical). **At this point in the spec the temp folder has been
  deleted**, so this check is only valid *during* implementation; skip it
  after step 2.

---

## CLAUDE.md updates

None required. The favicon files are part of the standard `assets/` static
serving and aren't called out in the architecture notes today. Adding a
bullet about "we have a favicon" is noise. Skip.

If the implementer wants to add a single line under
**Key assets** for completeness, this is acceptable but optional:

> | `assets/favicon.ico` (+ PNG / webmanifest variants) | Browser tab icon, auto-served by Dash from `assets/` |

User's call; default to skipping.

---

## Verification before opening the PR

1. `uv run pytest -q` — green.
2. `git status` shows exactly the modified files listed in section 3 above
   plus the new spec file. No stray edits.
3. `ls favicon_io-3` returns "No such file or directory" — the temp folder
   is gone.
4. The PR diff (use `git diff --stat`) shows:
   - `assets/favicon.ico` modified (binary)
   - `assets/favicon-16x16.png` modified (binary)
   - `assets/favicon-32x32.png` modified (binary)
   - `assets/apple-touch-icon.png` modified (binary)
   - `assets/android-chrome-192x192.png` modified (binary)
   - `assets/android-chrome-512x512.png` modified (binary)
   - `assets/site.webmanifest` either unchanged or shown but with zero
     line-level changes (it's byte-identical to the existing copy)
   - `updates_documentation/UPDATE-8.md` added
5. **No code files** in the diff: no `.py`, no `.css`, no `.csv`, no test
   files. If anything else shows up, something went wrong.

---

## Ship

1. Commit on `feat/new-favicon` (e.g.
   `chore: replace favicon with SWEEPSTAKELADS 2026 set (UPDATE-8)`).
2. Push, open PR, wait for CI, merge.
3. Auto-deploy runs on merge per `.github/workflows/deploy.yml`.
4. After deploy, browse to `https://sweepstakelads.stomlins.com/` in a
   private window and confirm the tab icon is the new design. Same caching
   caveat applies — incognito/private window is the most reliable check.
5. No cache invalidation needed app-side. The Cloudflare edge may cache
   the old favicon for a short while; if it persists after a few minutes,
   purge `/favicon.ico` from the Cloudflare cache via the dashboard.
   Usually unnecessary.

---

## Things to flag while implementing

- **Browser favicon cache is aggressive.** Don't trust a single
  Cmd-Shift-R. Use a private window. If you've been testing in the same
  Chrome profile a lot, the icon you see may be stuck on the old version
  even though the file on disk is correct.
- **Dash auto-serving relies on the file being directly in `assets/`.** Do
  not nest the new files under `assets/favicons/` or similar — that breaks
  the auto-serve. Keep the flat layout.
- **Don't add `<link rel="icon">` etc. to `index_string`.** Tempting,
  because it would also pick up the apple-touch-icon and the manifest, but
  this update is explicitly a pure asset swap. If we want proper PWA / Apple
  home-screen icons later, that's a separate, considered change.
- **`site.webmanifest` is byte-identical between source and destination.**
  Copying it is a no-op but safe. If git reports it as modified, something's
  off with line endings or trailing newlines — confirm with `diff -q` and
  if truly identical the copy is harmless.
- **Don't touch the `.bak` files.** `assets/fixtures.csv.bak` and
  `assets/last_updated.txt.bak` appear as untracked in `git status` but
  are out of scope for this PR. Leave them.
- **Don't stage the temp folder.** `favicon_io-3/` was never tracked. After
  `rm -rf favicon_io-3/`, it simply disappears from `git status` —
  there's no `git rm` to run.
- **The new `favicon.ico` happens to be the same size as the old one (15406
  bytes).** That's a coincidence; the file contents differ. Don't use file
  size as a sanity check — visual inspection is the only reliable signal.

---

## Out of scope (do not expand the PR)

- Wiring the apple-touch-icon, android-chrome icons, or webmanifest into
  `<head>` via `index_string`. Separate, future PR with its own spec if
  desired.
- A new app-icon design or any image-editing work. The new set in
  `favicon_io-3/` is the final asset — drop it in as-is.
- Cleaning up the `.bak` files in `assets/`. Separate housekeeping pass.
- Adding a `CLAUDE.md` table row for the favicon set. Optional and
  defaulted to "skip" above.
- Cloudflare cache purge unless the post-deploy check actually shows the
  stale icon for more than a few minutes.
