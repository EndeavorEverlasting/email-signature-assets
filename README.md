# Email Signature Assets

Public image assets for email signatures.

- `Fading_Set_Notation_Symbol.gif` — Career Presence mathematical brace animation.
- `Title_Loading_Ellipsis_Down.gif` — Work-signature sequential fading ellipsis
  (`.` → `..` → `...`) plus a down-right arrow. In the Work layout the cue sits
  in the left (~100px) column above the employer logo and aims at the obsolete
  title on the right.

## Regenerate the Work cue

Requires Python 3 + Pillow:

```bash
python scripts/generate_title_loading_gif.py -o Title_Loading_Ellipsis_Down.gif
```

The generator self-checks that early frames light the first, then first+second, then all three dots before the arrow pulse. Copy the resulting file into `Email-Signature/client/public/Title_Loading_Ellipsis_Down.gif` so both repos share the same Git blob.
