# Trae Preview: Inputs/Textareas Render Right-to-Left Unexpectedly

## Summary
- In the Trae IDE preview pane, typing inside `input` and `textarea` fields on the admin create page renders as right-to-left (RTL) even when the page markup explicitly sets left-to-right (LTR).
- Opening the exact same URL in a normal browser tab shows correct LTR behavior. This indicates the preview environment is injecting or inheriting text direction settings that override the page's styles.

## Impacted Page(s)
- `http://localhost:8000/gerencial/votacao/create/?proposicao_id=2270800`
- Template: `templates/admin/voting/votacao_create.html`

## Environment
- OS: Windows (user dev machine)
- Framework: Django (development server)
- Server command: `python manage.py runserver localhost:8000 --settings=votebem.settings.production`
- Trae IDE: Preview pane used to render the page; external browser renders correctly

## Reproduction Steps
1. Start the dev server: `python manage.py runserver localhost:8000 --settings=votebem.settings.production`.
2. Open the create page in the Trae preview: `http://localhost:8000/gerencial/votacao/create/?proposicao_id=2270800`.
3. Click into the `Título da Votação` (`#titulo`) and `Resumo` (`#resumo`) fields and begin typing:
   - Caret appears on the right.
   - Characters flow right-to-left.
4. Open the same URL in an external browser window (outside of Trae).
   - Caret appears on the left.
   - Characters flow left-to-right as expected.

## Expected vs. Observed
- Expected: Inputs and textareas should respect the page’s LTR settings (`dir="ltr"`, `direction: ltr`) and render LTR text flow.
- Observed (Trae preview only): Fields render with RTL text direction despite explicit LTR markup/styles.

## Relevant Markup and Styles
- The create page sets LTR explicitly in several places:
  - Container: `<div class="create-container" dir="ltr">`
  - Search input: `<input id="proposicao_search" ... dir="ltr" style="direction: ltr; text-align: left;">`
  - Textareas: `<textarea id="titulo" ... dir="ltr">` and `<textarea id="resumo" ... dir="ltr">`
- JavaScript also sanitizes potential bidi control characters when filling fields from search results:
  - `sanitizeBidi(str).replace(/[\u200E\u200F\u202A-\u202E\u2066-\u2069]/g, '')`

## Diagnostic Notes and Hypotheses
- The discrepancy suggests the Trae preview host page or wrapper is:
  - Setting `dir="rtl"` on a parent element (e.g., `html`/`body`) or iframe container; or
  - Injecting global CSS (e.g., `input, textarea { direction: rtl; }`) or applying a locale-based CSS reset; or
  - Using `unicode-bidi` or similar CSS in the preview shell that affects nested content.
- A simple check inside the preview (`getComputedStyle(document.querySelector('#titulo')).direction`) likely returns `rtl` while the external browser returns `ltr`.

## Workarounds (Applied in Project)
- Explicit LTR attributes and styles on the create page:
  - Add `dir="ltr"` to `.create-container` and the search input.
  - Apply `direction: ltr; text-align: left;` inline to critical inputs.
  - Sanitize bidi control characters before setting field values via JS.
- These mitigate the issue but the preview should not override direction globally.

## Requested Fix
- Ensure the Trae preview wrapper does not override nested page text direction:
  - Do not set `dir="rtl"` or global `direction: rtl` on `html`, `body`, `iframe`, `input`, or `textarea` inside the preview.
  - Avoid injecting CSS resets that affect text direction unless explicitly configured.
  - If locale or UI language toggles affect direction, scope it to the preview chrome, not the embedded app DOM.
- Consider adding a preview setting to force neutral LTR defaults or isolate the app’s styles.

## Additional Context
- Behavior is isolated to the Trae preview; external browsers are correct.
- User expectation: Preview should match the browser rendering for dev parity.

## Contact
- If more diagnostic details are helpful, we can provide DOM snapshots or run computed-style comparisons within the preview.