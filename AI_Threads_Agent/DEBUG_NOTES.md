# Debug Notes

## 2026-06-07

### Issue 1: `pick_top_article()` crashed before article selection
- Symptom: running `python agent.py --dry-run` failed with `UnboundLocalError: local variable 'prompt' referenced before assignment`.
- Root cause: `processors/ai_filter.py` called `prompt.replace(...)` before `prompt` had ever been assigned.
- Fix: rewrote `processors/ai_filter.py` so article selection and post generation build prompts directly, parse JSON safely, and fall back to deterministic logic when the model call fails.

### Issue 2: publish flow hard-failed when `IMGUR_CLIENT_ID` was missing
- Symptom: running `python agent.py` stopped at image upload with `ValueError: IMGUR_CLIENT_ID is not configured`.
- Root cause: `publishers/threads.py` required Imgur as the only way to obtain a public image URL for Threads.
- Fix: added a fallback uploader. The publisher now tries Imgur first, and if Imgur is unavailable it uploads anonymously to Catbox and continues publishing to Threads.

### Validation
- `python agent.py --dry-run`: passed
- `python agent.py`: passed
- Successful Threads post ID: `18074521577668207`

### Environment notes
- Required and present: `DEEPSEEK_API_KEY`, `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`
- Optional but missing: `IMGUR_CLIENT_ID`
- Current behavior without Imgur: automatic Catbox fallback
