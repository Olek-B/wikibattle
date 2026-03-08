# Deploying WikiBattle to PythonAnywhere

## Prerequisites

- A PythonAnywhere account (free tier works)
- A Groq API key from https://console.groq.com

## Steps

### 1. Upload the code

Option A - Git:
```bash
# In a PythonAnywhere Bash console:
cd ~
git clone <your-repo-url> wikibattle
```

Option B - Manual upload:
Upload the `wikibattle/` directory via PythonAnywhere's Files tab so it lives at `/home/YOUR_USERNAME/wikibattle/`.

### 2. Create a virtualenv

In a PythonAnywhere Bash console:

```bash
mkvirtualenv wikibattle --python=python3.10
pip install -r ~/wikibattle/server/requirements.txt
```

### 3. Configure the web app

Go to the **Web** tab on PythonAnywhere:

1. Click **Add a new web app**
2. Choose **Manual configuration** (not Flask)
3. Select **Python 3.10**

### 4. Set the WSGI file

In the Web tab, click on the WSGI configuration file link (something like `/var/www/YOUR_USERNAME_pythonanywhere_com_wsgi.py`).

Replace its entire contents with the contents of `wsgi.py`:

```python
import sys
import os

USERNAME = os.environ.get('USER', 'YOUR_USERNAME')
PROJECT_DIR = f'/home/{USERNAME}/wikibattle/server'

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from app import app, start_cleanup_thread

start_cleanup_thread()

application = app
```

### 5. Set the virtualenv path

In the Web tab under **Virtualenv**, enter:

```
/home/YOUR_USERNAME/.virtualenvs/wikibattle
```

### 6. Set environment variables

In the Web tab, go to the **Environment variables** section and add:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | `gsk_your_key_here` |

The card effect cache uses SQLite and is stored automatically at `/tmp/wikibattle_card_cache.db`.
No additional setup required.

### 7. Configure static files

In the Web tab under **Static files**, add:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/YOUR_USERNAME/wikibattle/client/` |

This lets PythonAnywhere serve CSS and JS directly without hitting Flask.

### 8. Reload

Click the **Reload** button on the Web tab.

Your game should now be live at `https://YOUR_USERNAME.pythonanywhere.com`.

## Troubleshooting

- **Error log**: Check the error log linked on the Web tab.
- **Import errors**: Make sure the virtualenv path is correct and `pip install` succeeded.
- **Groq API errors**: Verify the `GROQ_API_KEY` environment variable is set correctly.
- **Static files 404**: Make sure the static file mapping points to the `client/` directory.
- **Deck generation slow**: First game takes ~20 seconds while Wikipedia API calls complete. This is normal.

## Running locally

```bash
cd wikibattle/server
pip install -r requirements.txt
export GROQ_API_KEY=gsk_your_key_here
python app.py
```

The card effect cache uses SQLite automatically - no additional setup needed.

Then open http://localhost:5000 in your browser.
