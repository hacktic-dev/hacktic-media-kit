# Hacktic Media Kit site

A static, responsive HTML version of the Hacktic media kit, ready for GitHub Pages.

## Deploy to GitHub Pages

1. Create a GitHub repository (for example `hacktic-media-kit`).
2. Put the contents of this folder in the repository root.
3. Commit and push to the `main` branch.
4. On GitHub, open **Settings → Pages**.
5. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
6. Choose the `main` branch and `/ (root)` folder, then click **Save**.
7. After GitHub finishes deploying, the Pages URL will appear in the same settings page.

Because all asset paths are relative, this works both at `username.github.io` and at project URLs such as `username.github.io/hacktic-media-kit/`.

## Edit the site

- Main content: `index.html`
- Styling: `styles.css`
- Images: `assets/`

The current channel figures are written directly into `index.html`, so updating them is just a text edit.

## Local preview

Open `index.html` directly in a browser, or serve the folder locally with any static HTTP server, for example:

```bash
python -m http.server 8080
```

Then visit `http://localhost:8080`.
