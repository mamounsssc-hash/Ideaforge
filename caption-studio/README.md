# CliPro Caption Studio (Remotion)

Premium animated captions — word‑by‑word reveal, a coloured **highlight box**
behind the spoken word (the Submagic look), a fixed colour for important words,
Arabic + English. Rendered with [Remotion](https://www.remotion.dev)
(free for individuals and teams of 3 or fewer).

## One‑time setup
1. Install **Node.js** (LTS) from https://nodejs.org — install like any program.
2. Open this `caption-studio` folder in a terminal (address bar → type `cmd`).
3. Run once:  `npm install`
   (Downloads the libraries. The **first render** also downloads a browser
   ~150 MB — one time only. On slow internet this can take a while.)

## Preview live (recommended while designing)
Run:  `npm run studio`
A window opens where you can watch the captions and tweak `input.json` live.

## Render a final video
1. Put your clip in `public\clip.mp4` (vertical 9:16, **no burned captions**).
2. In `input.json` set `"video": "clip.mp4"` and its `durationInSeconds`,
   and paste the `words` (each `{text, start, end}` in seconds) + `keywords`.
3. Double‑click **`render.bat`** (or run `npm run render`).
4. Your captioned video appears in `out\captioned.mp4`.

## Styling (edit `input.json` → `style`)
- `activeBox`: `true` = coloured box behind the spoken word.
- `active`: the box / spoken‑word colour.
- `keyword`: fixed colour for important words (listed in `keywords`).
- `primary`: normal word colour · `font`: `"cairo"` (Arabic) or `"anton"` (English).
- `maxWords`, `fontSize`, `uppercase`, `bottomPct`.

> The CliPro app can generate `input.json` + the un‑captioned clip for you —
> that integration is the next step. For now you can test with the sample
> `input.json` (leave `"video": ""` to preview captions on a dark background).
