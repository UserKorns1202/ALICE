import webbrowser
from googlesearch import search
from googleapiclient.discovery import build
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from alice_secrets import YOUTUBE_API_KEY

# Google API Key and YouTube API setup
youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Function to search YouTube and open the first result
def search_youtube(query):
    request = youtube_service.search().list(
        q=query,
        part='snippet',
        type='video',
        maxResults=1  # Open the top result directly
    )
    response = request.execute()
    for item in response['items']:
        video_url = f"https://www.youtube.com/watch?v={item['id']['videoId']}"
        print(f"Opening YouTube video: {video_url}")
        webbrowser.open(video_url)

# Function to search the web and open the first result
def search_web(query):
    for result in search(query, num_results=1):  # Open the top result directly
        print(f"Opening webpage: {result}")
        try:
            webbrowser.open(result)
        except Exception as e:
            print(f"Error opening webpage: {e}")
            # Fallback to manually opening the URL using the default browser
            browser_path = webbrowser.get().name
            if "opera" in browser_path.lower():
                print("Detected Opera GX. Attempting to open with default browser.")
                os.system(f'start {result}')
        break

# Example function to let ALICE handle search commands
def handle_search_command(command):
    if "youtube" in command.lower():
        query = command.replace("youtube search for", "").strip()
        search_youtube(query)
    elif "web" in command.lower() or "internet" in command.lower():
        query = command.replace("search the web for internet", "").strip()
        search_web(query)
    else:
        print("Sorry, I didn't understand the command.")
