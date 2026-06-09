# Deploy on PythonAnywhere — Step by Step

## Step 1 — Create Free Account
Go to https://www.pythonanywhere.com → Sign up free (no credit card)

## Step 2 — Upload ZIP
1. Click "Files" tab
2. Click "Upload a file"
3. Upload: Event_management_platform_v4.zip

## Step 3 — Extract & Install
Click "Bash" to open console, then run:
```bash
unzip Event_management_platform_v4.zip
mv Event_management_platform_updated eventhub
cd eventhub
pip install -r requirements.txt
```

## Step 4 — Edit database.py
Open database.py and replace YOURUSERNAME with your actual username:
```python
DB_PATH = "/home/YOURUSERNAME/eventhub/event.db"
```

## Step 5 — Create Web App
1. Click "Web" tab
2. Click "Add a new web app"
3. Click "Next"
4. Choose "Flask"
5. Choose "Python 3.10"
6. Set path: /home/YOURUSERNAME/eventhub/app.py
7. Click "Next"

## Step 6 — Fix WSGI File
1. On the Web tab, click the WSGI file link
2. Delete everything in it
3. Paste this (replace YOURUSERNAME):

import sys
import os
sys.path.insert(0, '/home/YOURUSERNAME/eventhub')
os.environ['DB_PATH'] = '/home/YOURUSERNAME/eventhub/event.db'
from app import app as application

4. Click Save

## Step 7 — Set Static Files
On Web tab, under "Static files":
- URL: /static/
- Path: /home/YOURUSERNAME/eventhub/static

## Step 8 — Reload & Done!
Click the green "Reload" button
Your app is live at: YOURUSERNAME.pythonanywhere.com

## Admin Login
Email: admin@gmail.com
Password: admin123
