# Age-edit spec (Step 2)

Produce the single-dimension counterfactual `V′`: the same conversation with ONLY the
patient's age changed (`age_from` → `age_to`) and the words the age directly entails
(life-stage nouns, age-tied relations). Minimality is the whole premise — if the edit must
touch clinical content to stay coherent, the item is not cleanly age-mutable and should be
dropped.

**Design: find/replace, not full echo.** We do not ask the model to regenerate the whole
conversation (fragile for small models; can silently drop content). Instead:

1. **Deterministic primary swap** (in Python): replace the detected age string
   (`age_str`, e.g. `"39 year old"`) with its age-swapped form (`"72 year old"`).
2. **Optional LLM extras**: the model returns a short list of *literal* `{find, replace}`
   pairs for any other age mentions / entailed life-stage words. Each `find` is verified to
   be an exact substring before it is applied; non-matching suggestions are ignored.

The prompt is embedded in [`edit.py`](edit.py) (`EDIT_PROMPT`); this file is the spec.

## Guards (enforced in `edit.py`)
- **Changed something:** ≥1 replacement applied, else `ok=False` (the age wasn't edited).
- **Minimality:** character-level diff fraction ≤ `--max-change-frac` (default 0.25), else
  `ok=False`. A large diff means the edit rippled beyond the age dimension.

Downstream steps still run on flagged items, but report `analyze.py` results with flagged
items excluded (or hand-corrected) — note the count.
