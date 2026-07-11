# Facebook Group Autoposter

A lightweight tool to automate posting messages and images to multiple Facebook groups using Playwright.

---

## Setup

1. **Install Python**:
   * Download and install Python from the [Official Python Website](https://www.python.org/downloads/).
   * *Important:* Check the box that says **"Add Python to PATH"** during setup.
2. Install dependencies:
   ```bash
   pip install playwright
   playwright install chromium
   ```
2. Export your Facebook cookies as a JSON array using the **Cookie-Editor** browser extension (available for [Chrome/Brave](https://chromewebstore.google.com/detail/hlkenndednhfkekhgcdicdfddnkalmdm?utm_source=item-share-cb) and [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/)).
3. Save the exported JSON content into a file named `facebook-cookies.json` inside a `sessions/` directory.

---

## Configuration

### Target Groups
List your target Facebook group URLs in `groups.json`:
```json
[
  "https://web.facebook.com/share/g/group_id_1/",
  "https://web.facebook.com/share/g/group_id_2/"
]
```

### Content Templates
Define your post content and optional image attachments in `contents.json`:
```json
[
  {
    "text": "Your post text goes here",
    "image": "images/example.jpg"
  }
]
```

### Settings
Adjust delays, shuffle preferences, and Discord webhook configurations directly at the top of `configs.py`.

---

## Run

```bash
python main.py
```
