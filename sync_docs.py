import os
import json
import io
import re
import urllib.parse
from bs4 import BeautifulSoup
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

def demote_headers(md_text):
    """
    Shifts Markdown headers down by 1 level (# -> ##, ## -> ###)
    so MkDocs treats top-level Doc titles as H2s in the TOC sidebar.
    """
    lines = md_text.splitlines()
    new_lines = []
    for line in lines:
        if line.startswith('#'):
            # Convert '# Header' to '## Header', '## Header' to '### Header', etc.
            new_lines.append('#' + line)
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)

def clean_google_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    for a in soup.find_all('a'):
        href = a.get('href', '')
        if 'google.com/url?q=' in href:
            parsed = urllib.parse.urlparse(href)
            query_params = urllib.parse.parse_qs(parsed.query)
            if 'q' in query_params:
                clean_url = query_params['q'][0]
                a['href'] = clean_url
        if 'style' in a.attrs:
            del a['style']

    for td in soup.find_all(['td', 'th']):
        for br in td.find_all('br'):
            br.replace_with(' ')

    for tag in soup.find_all(True):
        if 'style' in tag.attrs:
            del tag['style']

    return str(soup)

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
            
            raw_html = fh.getvalue().decode('utf-8')
            cleaned_html = clean_google_html(raw_html)
            
            # Convert HTML to Markdown
            md_content = pypandoc.convert_text(cleaned_html, 'gfm', format='html')
            
            # Demote header levels automatically for MkDocs TOC compatibility
            formatted_md = demote_headers(md_content)
            
            file_path = os.path.join(local_path, f"{name}.md")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_md)

if __name__ == '__main__':
    download_folder(FOLDER_ID, 'docs')
    
    index_path = os.path.join('docs', 'index.md')
    if not os.path.exists(index_path):
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write("# Welcome to Jahk's Library of Possibility\n\nUse the navigation bar above or the sidebar to browse homebrew options.\n")
