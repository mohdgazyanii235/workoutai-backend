import os
from authlib.integrations.starlette_client import OAuth

# Load the Google credentials from the .env file
GOOGLE_CLIENT_ID = os.getenv("CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
print(GOOGLE_CLIENT_ID)

# Create the OAuth instance
oauth = OAuth()

# Register the Google client
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)