# Hacktic Media Kit site

A static, responsive HTML version of the Hacktic media kit, ready for GitHub Pages.

## Deploy to GitHub Pages

1. Create a GitHub repository (for example `hacktic-media-kit`).
2. Put the contents of this folder in the repository root.
3. Commit and push to the `master` branch.
4. On GitHub, open **Settings → Pages**.
5. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
6. Choose the `master` branch and `/ (root)` folder, then click **Save**.
7. After GitHub finishes deploying, the Pages URL will appear in the same settings page.

Because all asset paths are relative, this works both at `username.github.io` and at project URLs such as `username.github.io/hacktic-media-kit/`.

## Edit the site

- Main content: `index.html`
- Styling: `styles.css`
- Images: `assets/`

The headline channel figures (subscribers, last-28-days views, lifetime views)
and the three "Proven track record" video view counts are refreshed automatically
once a day from YouTube. See "Automated YouTube stats" below. The audience-age
figure and all other copy are static.

## Local preview

Open `index.html` directly in a browser, or serve the folder locally with any static HTTP server, for example:

```bash
python -m http.server 8080
```

Then visit `http://localhost:8080`.

## Automated YouTube stats

The three headline numbers in the hero are updated daily by a scheduled GitHub
Action that reads from the YouTube APIs and writes a small `stats.json` file at
the repository root. The page loads that JSON in the browser and formats the
values; if the file is missing or fails to load, the hard-coded fallback values
remain visible.

```
YouTube APIs -> scheduled GitHub Action -> stats.json -> index.html
```

`stats.json` contains only public, non-sensitive numbers (subscriber count,
views, dates). Credentials never appear in the website, in `stats.json`, or in
logs — they exist only as GitHub Actions repository secrets.

### One-time Google Cloud / OAuth setup

Do this once, locally, as the owner of the Hacktic YouTube channel.

1. **Create or select a Google Cloud project** at
   <https://console.cloud.google.com/>.

2. **Enable the APIs** (APIs & Services → Library):
   - YouTube Data API v3
   - YouTube Analytics API

3. **Configure the OAuth consent screen** (APIs & Services → OAuth consent
   screen). For your own account, the "External" type in "Testing" mode is fine.
   Add your own Google account as a test user.

4. **Create the OAuth client** (APIs & Services → Credentials → Create
   credentials → OAuth client ID). Choose application type **Desktop app**, then
   download the JSON and save it as `client_secret.json` in this folder. This file
   is git-ignored — never commit it.

5. **Authorize the channel once** by running (requires the dependencies in
   `requirements.txt`):

   ```bash
   python -m pip install -r requirements.txt
   python authorize_youtube.py client_secret.json
   ```

   A browser opens; sign in as the Hacktic channel owner and approve the
   requested read-only scopes. The script then prints the refresh token and the
   channel ID(s) owned by that account. The client id and secret are the values
   inside the downloaded `client_secret.json`.

   The refresh token is long-lived and grants read access to your channel.
   Treat it like a password. **Never commit it**, and never paste it into the
   website, JavaScript, or README.

6. **Create the GitHub repository secrets** (Settings → Secrets and variables →
   Actions → New repository secret):

   | Secret name             | Value                                            |
   |-------------------------|--------------------------------------------------|
   | `YOUTUBE_CLIENT_ID`     | Client id from `client_secret.json`              |
   | `YOUTUBE_CLIENT_SECRET` | Client secret from `client_secret.json`          |
   | `YOUTUBE_REFRESH_TOKEN` | Refresh token printed by `authorize_youtube.py`  |
   | `YOUTUBE_CHANNEL_ID`    | Channel id (optional, see below)                 |

   `YOUTUBE_CHANNEL_ID` is optional: if it is empty or missing, the script uses
   the channel of the authenticated account (`mine=true`).

7. **Finding the channel ID (if needed):** with the channel owner signed in,
   visit <https://studio.youtube.com> → Settings → Channel → Advanced settings;
   the channel id starts with `UC`. You can also let the script discover it
   automatically by leaving `YOUTUBE_CHANNEL_ID` empty.

8. **Verify it works:** open the **Actions** tab, select **Update YouTube
   stats**, then **Run workflow**. If it succeeds, a `stats.json` is committed
   and the hero numbers update after Pages redeploys. It also runs automatically
   once per day.
