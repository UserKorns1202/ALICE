import webbrowser
import time
import pyautogui
from ytmusicapi import YTMusic
import os
from urllib.parse import quote_plus

# Initialize YTMusic API.
# If an authenticated headers JSON (created via YTMusic.setup) is present,
# use it to access the account's library (playlists, likes, etc.).
AUTH_HEADERS = os.path.join(os.path.dirname(__file__), "headers_auth.json")
if os.path.exists(AUTH_HEADERS):
    try:
        ytmusic = YTMusic(AUTH_HEADERS)
        authenticated = True
    except Exception:
        # Fall back to unauthenticated instance if headers are invalid
        ytmusic = YTMusic()
        authenticated = False
else:
    ytmusic = YTMusic()
    authenticated = False

def search_and_play_song(song_name: str) -> str:
    """Search for a song and open it in YouTube Music."""
    try:
        results = ytmusic.search(song_name, filter='songs')
        if results:
            video_id = results[0]['videoId']
            url = f"https://music.youtube.com/watch?v={video_id}"
            webbrowser.open(url)
            return f"Playing '{results[0]['title']}' by {results[0]['artists'][0]['name']} on YouTube Music."
        else:
            return f"No song found for '{song_name}'."
    except Exception as e:
        return f"Error searching song: {e}"

def play_playlist(playlist_name: str) -> str:
    """Search for a playlist and open it in YouTube Music."""
    try:
        # If authenticated, prefer searching the user's library playlists
        if authenticated:
            try:
                lib_pl = ytmusic.get_library_playlists(limit=200)
                for p in lib_pl:
                    title = (p.get('title') or '').lower()
                    if playlist_name.lower() in title:
                        pid = p.get('playlistId') or p.get('browseId')
                        if pid:
                            url = f"https://music.youtube.com/playlist?list={pid}"
                            webbrowser.open(url)
                            return f"Playing playlist '{p.get('title')}' from your library on YouTube Music."
            except Exception:
                # If library access fails, fall back to public search
                pass

        # Public search fallback (unauthenticated)
        results = ytmusic.search(playlist_name, filter='playlists')
        if results:
            # Try to find a usable playlist id in any result
            for r in results:
                pid = r.get('browseId') or r.get('playlistId') or r.get('id')
                title = r.get('title') or r.get('playlistName') or playlist_name
                if pid:
                    url = f"https://music.youtube.com/playlist?list={pid}"
                    webbrowser.open(url)
                    return f"Playing playlist '{title}' on YouTube Music."
            # If none of the search hits expose an ID we can use, open the search results page
            q = quote_plus(playlist_name)
            search_url = f"https://music.youtube.com/search?q={q}"
            webbrowser.open(search_url)
            return f"Opened search results for playlist '{playlist_name}' on YouTube Music." 
        # No results at all -> open search page as fallback
        q = quote_plus(playlist_name)
        search_url = f"https://music.youtube.com/search?q={q}"
        webbrowser.open(search_url)
        return f"Opened search results for playlist '{playlist_name}' on YouTube Music (no direct match found)."
    except Exception as e:
        return f"Error searching playlist: {e}"

def skip_song() -> str:
    """Skip to the next song (assumes YouTube Music is open in browser)."""
    try:
        # Bring browser to focus (assuming Chrome or default)
        pyautogui.hotkey('alt', 'tab')  # May need adjustment
        time.sleep(0.5)
        pyautogui.press('n')  # Next song key in YouTube
        return "Skipped to next song."
    except Exception as e:
        return f"Error skipping song: {e}"

def pause_play() -> str:
    """Pause or play the current song."""
    try:
        pyautogui.press('k')  # Play/pause key in YouTube
        return "Toggled play/pause."
    except Exception as e:
        return f"Error toggling play: {e}"

def set_volume(level: int) -> str:
    """Set volume (0-100). Note: This is approximate via keys."""
    try:
        current = 50  # Assume default
        if level > current:
            presses = (level - current) // 5
            for _ in range(presses):
                pyautogui.press('up')
        else:
            presses = (current - level) // 5
            for _ in range(presses):
                pyautogui.press('down')
        return f"Volume set to approximately {level}%."
    except Exception as e:
        return f"Error setting volume: {e}"