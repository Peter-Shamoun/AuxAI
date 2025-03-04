from flask import Flask, request, jsonify, redirect  # Import Flask components for building the web app.
from flask_cors import CORS  # Import CORS to enable cross-origin resource sharing.
import spotipy  # Import Spotipy to interact with the Spotify API.
from spotipy.oauth2 import SpotifyOAuth  # Import SpotifyOAuth for managing Spotify authentication.
from dotenv import load_dotenv  # Import load_dotenv to load environment variables from a .env file.
import os  # Import os to access environment variables.

# Load environment variables from the .env file.
load_dotenv()  # This reads the .env file and adds the variables to the environment.

# Retrieve the Spotify API credentials from the environment variables.
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')  
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')

# Create the Flask application instance.
app = Flask(__name__)
# Enable CORS for the app to allow requests from different origins.
CORS(app)

# Now, these credentials are loaded dynamically from your .env file,
# ensuring that sensitive information isn't hard-coded in your source code.

# Create a SpotifyOAuth instance to handle the OAuth flow.
# The scope defines the permissions your application is requesting.
sp_oauth = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-library-read user-library-modify user-read-playback-state user-modify-playback-state"
)

# Instantiate the Spotipy client using the SpotifyOAuth manager.
# Note: This client will later use the cached token provided by our custom OAuth endpoints.
sp = spotipy.Spotify(auth_manager=sp_oauth)

def require_authentication():
    """
    Helper function to check whether a valid token exists.
    Returns a tuple (authenticated, token_info):
      - authenticated: Boolean indicating if a valid token is available.
      - token_info: The token details if available, or None otherwise.
    """
    token_info = sp_oauth.get_cached_token()  # Check the cache for a valid token.
    if not token_info:
        # No valid token is available.
        return False, None
    return True, token_info

@app.route('/login')
def login():
    """
    Endpoint to initiate the Spotify OAuth authentication process.
    This redirects the user to Spotify's authorization page.
    """
    # Generate the Spotify authorization URL using our OAuth manager.
    auth_url = sp_oauth.get_authorize_url()
    # Redirect the user to Spotify's login/authorization page.
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """
    OAuth callback endpoint.
    Spotify will redirect the user to this URL after they authorize your app.
    This endpoint handles the exchange of the authorization code for an access token.
    """
    # Retrieve the authorization code from the query parameters.
    code = request.args.get('code')
    # Also check if Spotify returned an error.
    error = request.args.get('error')
    if error:
        # If there is an error, return it as a JSON response with a 400 status code.
        return jsonify({'error': error}), 400
    if code:
        # Exchange the authorization code for an access token.
        token_info = sp_oauth.get_access_token(code)
        if token_info:
            # If successful, inform the client that authentication is complete.
            return jsonify({'status': 'Authenticated successfully.'})
    # If we reach here, authentication failed unexpectedly.
    return jsonify({'error': 'Authentication failed.'}), 400

@app.route('/search', methods=['GET'])
def search_songs():
    """
    Endpoint to search for songs on Spotify based on a query parameter.
    Returns only the important information for each track.
    """
    # Verify that the user is authenticated by checking for a valid token.
    authenticated, _ = require_authentication()
    if not authenticated:
        # If not authenticated, instruct the user to log in.
        return jsonify({'error': 'User not authenticated. Please log in via /login.'}), 401

    # Retrieve the query parameter 'q' from the request URL.
    query = request.args.get('q')
    if not query:
        # Return an error if the query parameter is missing.
        return jsonify({'error': 'Missing query parameter'}), 400

    # Use the Spotify API to search for tracks matching the provided query.
    results = sp.search(q=query, type='track')

    # Extract the list of track items from the API response.
    tracks = results.get("tracks", {}).get("items", [])
    simplified_tracks = []

    # Loop through each track in the result and extract the most important details.
    for track in tracks:
        # Construct a dictionary with key details for each track.
        track_info = {
            "id": track.get("id"),  # Unique track identifier.
            "name": track.get("name"),  # Name of the track.
            "artists": [  # List of artists for the track.
                {
                    "id": artist.get("id"),  # Unique artist identifier.
                    "name": artist.get("name"),  # Name of the artist.
                    "href": artist.get("href")  # Link to the artist's Spotify profile.
                } for artist in track.get("artists", [])
            ],
            "album": {  # Album information.
                "id": track.get("album", {}).get("id"),  # Unique album identifier.
                "name": track.get("album", {}).get("name"),  # Album name.
                "release_date": track.get("album", {}).get("release_date"),  # Album release date.
                "total_tracks": track.get("album", {}).get("total_tracks"),  # Total number of tracks in the album.
                "images": track.get("album", {}).get("images"),  # List of album cover images.
                "href": track.get("album", {}).get("href"),  # Link to the album's Spotify page.
            },
            "href": track.get("href"),  # API endpoint for this track.
            "uri": track.get("uri"),  # Spotify URI for this track.
            "preview_url": track.get("preview_url"),  # URL to a 30-second preview of the track.
            "popularity": track.get("popularity"),  # Popularity score of the track.
            "duration_ms": track.get("duration_ms")  # Duration of the track in milliseconds.
        }
        # Add the simplified track information to our list.
        simplified_tracks.append(track_info)

    # Return the list of simplified track details as a JSON response.
    return jsonify(simplified_tracks)


@app.route('/track/<id>', methods=['GET'])
def get_track_details(id):
    """
    Endpoint to retrieve detailed information about a specific track using its Spotify ID.
    """
    # Ensure the user is authenticated.
    authenticated, _ = require_authentication()
    if not authenticated:
        return jsonify({'error': 'User not authenticated. Please log in via /login.'}), 401

    try:
        # Use the Spotify API client to fetch track details.
        track = sp.track(id)
        return jsonify(track)
    except spotipy.exceptions.SpotifyException as e:
        # If an error occurs (e.g., invalid track ID), return an error message.
        return jsonify({'error': str(e)}), 400

@app.route('/playlists', methods=['GET'])
def get_playlists():
    """
    Endpoint to retrieve the current user's playlists.
    """
    # Verify authentication.
    authenticated, _ = require_authentication()
    if not authenticated:
        return jsonify({'error': 'User not authenticated. Please log in via /login.'}), 401

    # Fetch the user's playlists using the Spotify API.
    playlists = sp.current_user_playlists()
    return jsonify(playlists)

@app.route('/playlists/<id>/tracks', methods=['POST'])
def add_to_playlist(id):
    """
    Endpoint to add tracks to a specified playlist.
    The request must include a JSON payload with a 'track_ids' list.
    """
    # Check for a valid authentication token.
    authenticated, _ = require_authentication()
    if not authenticated:
        return jsonify({'error': 'User not authenticated. Please log in via /login.'}), 401

    # Extract the list of track IDs from the request JSON payload.
    track_ids = request.json.get('track_ids')
    if not track_ids:
        return jsonify({'error': 'Missing track_ids parameter'}), 400

    try:
        # Use the Spotify API to add the provided track IDs to the specified playlist.
        sp.playlist_add_items(id, track_ids)
        return jsonify({'status': 'success'})
    except spotipy.exceptions.SpotifyException as e:
        # If an error occurs during the API call, return the error details.
        return jsonify({'error': str(e)}), 400

@app.route('/play', methods=['PUT'])
def play_song():
    """
    Endpoint to start playback of a specified track.
    The request must include a JSON payload with a 'track_id'.
    """
    # Confirm that the user is authenticated.
    authenticated, _ = require_authentication()
    if not authenticated:
        return jsonify({'error': 'User not authenticated. Please log in via /login.'}), 401

    # Retrieve the track ID from the JSON payload.
    track_id = request.json.get('track_id')
    if not track_id:
        return jsonify({'error': 'Missing track_id parameter'}), 400

    try:
        # Initiate playback for the specified track using its Spotify URI.
        sp.start_playback(uris=[f'spotify:track:{track_id}'])
        return jsonify({'status': 'success'})
    except spotipy.exceptions.SpotifyException as e:
        return jsonify({'error': str(e)}), 400

@app.route('/queue', methods=['POST'])
def queue_song():
    """
    Endpoint to add a track to the user's playback queue.
    The request must include a JSON payload with a 'track_id'.
    """
    # Ensure the user is authenticated.
    authenticated, _ = require_authentication()
    if not authenticated:
        return jsonify({'error': 'User not authenticated. Please log in via /login.'}), 401

    # Extract the track ID from the request JSON payload.
    track_id = request.json.get('track_id')
    if not track_id:
        return jsonify({'error': 'Missing track_id parameter'}), 400

    try:
        # Add the track to the user's playback queue.
        sp.add_to_queue(track_id)
        return jsonify({'status': 'success'})
    except spotipy.exceptions.SpotifyException as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    """
    Entry point for running the Flask development server.
    - The server runs on port 5000.
    - Debug mode is enabled to provide detailed error logs.
    - The reloader is disabled to avoid conflicts with Spotipy's OAuth local server.
    """
    app.run(debug=True, use_reloader=False)
