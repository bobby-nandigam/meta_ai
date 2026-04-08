from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle
import os

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    creds = None

    if os.path.exists('credentials/gmail_token.pickle'):
        with open('credentials/gmail_token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials/gmail_credentials.json', SCOPES)
        creds = flow.run_local_server(
    host='localhost',
    port=8080,
    authorization_prompt_message='Please visit this URL: {url}',
    success_message='Authentication successful! You can close this window.',
    open_browser=True
)

        with open('credentials/gmail_token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds

def test_gmail():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(userId='me', maxResults=5).execute()
    print(results)

if __name__ == "__main__":
    test_gmail()
