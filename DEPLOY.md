# Deploying WikiBattle to PythonAnywhere

## Prerequisites

- A PythonAnywhere account (free tier works)
- A Groq API key from https://console.groq.com
- A Supabase project (free tier) from https://supabase.com for card effect caching

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

### 3. Set up Supabase (card effect cache)

1. Create a free project at https://supabase.com
2. Go to the **SQL Editor** and run:

```sql
CREATE TABLE card_effects_cache (
  key TEXT PRIMARY KEY,
  card_type TEXT NOT NULL,
  effects_data JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE card_effects_cache ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access" ON card_effects_cache
  FOR ALL USING (true) WITH CHECK (true);
```

3. Go to **Settings > API** and note down:
   - **Project URL** (e.g. `https://abcdef.supabase.co`)
   - **anon public** key

### 4. Configure the web app

Go to the **Web** tab on PythonAnywhere:

1. Click **Add a new web app**
2. Choose **Manual configuration** (not Flask)
3. Select **Python 3.10**

### 5. Set the WSGI file

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

### 6. Set the virtualenv path

In the Web tab under **Virtualenv**, enter:

```
/home/YOUR_USERNAME/.virtualenvs/wikibattle
```

### 7. Set environment variables

In the Web tab, go to the **Environment variables** section and add:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | `gsk_your_key_here` |
| `SUPABASE_URL` | `https://your-project-id.supabase.co` |
| `SUPABASE_KEY` | `your_anon_public_key` |

### 8. Configure static files

In the Web tab under **Static files**, add:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/YOUR_USERNAME/wikibattle/client/` |

This lets PythonAnywhere serve CSS and JS directly without hitting Flask.

### 9. Reload

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
export SUPABASE_URL=https://your-project-id.supabase.co
export SUPABASE_KEY=your_anon_public_key
python app.py
```

The Supabase env vars are optional locally - without them, card effects won't
be cached but the game works fine (every card calls Groq fresh).

Then open http://localhost:5000 in your browser.
