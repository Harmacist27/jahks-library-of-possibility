import os
import json
import io
import pypandoc
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
FOLDER_ID = os.environ['GDRIVE_FOLDER_ID']
CREDS_JSON = os.environ['GDRIVE_SERVICE_ACCOUNT_KEY']

creds_dict = json.loads(CREDS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

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
            # Convert HTML from Google Docs into clean Markdown while keeping tables and formatting
            md_content = pypandoc.convert_text(html_content, 'md', format='html')
            
            file_path = os.path.join(local_path, f"{name}.md")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

if __name__ == '__main__':
    download_folder(FOLDER_ID, 'docs')
