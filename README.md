# Peter&Alexander Media

Photography and video portfolio. A static site: no server code, served by GitHub Pages.

## Updating

Originals live outside this repository. After adding, removing or reordering photos or videos:

```bash
python3 build.py
```

This remakes the web-sized copies in `images/` and `videos/` and regenerates `js/data.js`.
Menu structure, gallery order, highlights and the About text are set in `content.json`.
Then commit and push.

Requires macOS (it uses `sips`, `qlmanage` and the Swift compiler for video conversion).
