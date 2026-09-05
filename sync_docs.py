import os
import json
import io
import re
import urllib.parse
import pypandoc
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
FOLDER_ID = os.environ['GDRIVE_FOLDER_ID']
CREDS_JSON = os.environ['GOOGLE_CREDENTIALS']

creds_dict = json.loads(CREDS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

def clean_google_redirects(text):
    """Unwraps Google Docs redirect URLs to their clean original destination."""
    def unwrap(match):
        raw_url = match.group(1)
        parsed = urllib.parse.urlparse(raw_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        if 'q' in query_params:
            return query_params['q'][0]
        return raw_url

    # Matches https://www.google.com/url?q=... strings
    pattern = r'https://www\.google\.com/url\?q=([^&"\'\s>]+)[^"\'\s>]*'
    return re.sub(pattern, unwrap, text)

def clean_markdown_styles(text):
    """Strips Google Docs inline CSS attributes, raw href tags, and leftover spans."""
    # Unwrap Google redirect links first
    text = clean_google_redirects(text)

    # Removes patterns like [Text]{style="..."} -> Text
    text = re.sub(r'\[([^\]]+)\]\{style="[^"]*?"\}', r'\1', text)
    # Removes dangling style tags like ]{style="..."} or style="..."
    text = re.sub(r'\]?\{style="[^"]*?"\}', '', text)
    text = re.sub(r'style="[^"]*?"', '', text)
    # Removes leftover raw href wrappers like href="..."
    text = re.sub(r'href="[^"]*?"', '', text)

    return text

def download_folder(folder_id, local_path):
    os.makedirs(local_path, exist_ok=True)
    query = f"'{folder_id}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])

    for item in items:
        name = item['name'].replace('/', '-')
        if item['mimeType'] == 'application/vnd.google-apps.folder':
            download_folder(item['id'], os.path.join(local_path, name))
        elif item['mimeType'] == 'application/vnd.google-apps.document':
            request = drive_service.files().export_media(fileId=item['id'], mimeType='text/html')
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            html_content = fh.getvalue().decode('utf-8')
            
            # Convert HTML from Google Docs to Markdown
            md_content = pypandoc.convert_text(html_content, 'gfm', format='html')
            
            # Post-process and strip out residual style tags and clean links
            clean_md = clean_markdown_styles(md_content)
            
            file_path = os.path.join(local_path, f"{name}.md")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(clean_md)

if __name__ == '__main__':
    download_folder(FOLDER_ID, 'docs')
    
    index_path = os.path.join('docs', 'index.md')
    if not os.path.exists(index_path):
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write("# Welcome to Jahk's Library of Possibility\n\nUse the navigation bar above or the sidebar to browse homebrew options.\n")
