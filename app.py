import os
import json
import operator
from flask import Flask, request, jsonify, Response, redirect, session, render_template
import requests
import spotipy
import spotipy.util as util
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import pandas as pd
import io
from flask_cors import CORS
from flask_session import Session

app = Flask(__name__)

SESSION_TYPE = 'filesystem'
app.config.from_object(__name__)
Session(app)

# app.config["SESSION_PERMANENT"] = True
# app.config["SESSION_TYPE"] = "filesystem"
# app.config['SESSION_COOKIE_SAMESITE'] = "None"
# app.config['SECRET_KEY'] = "SOME_STRING"


CORS(app, origins='http://localhost:3000',
     methods=['GET', 'POST'], headers=['Content-Type'])

# Spotify API credentials
SPOTIPY_CLIENT_ID = os.environ.get(
    'SPOTIFY_CLIENT_ID') or '17f711fbadc7470ebfcca93ac8a6c5f3'
SPOTIPY_CLIENT_SECRET = os.environ.get(
    'SPOTIFY_CLIENT_SECRET') or '840e6450776e47cfba11bae15983b9fb'
SPOTIPY_REDIRECT_URI = 'http://localhost:8000/callback/'
SCOPE = 'user-library-read playlist-modify-public playlist-read-private'
CACHE = '.spotipyoauthcache'
client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)


@app.context_processor
def handle_context():
    '''Inject object into jinja2 templates.'''
    return dict(io=io, pd=pd, operator=operator)


@app.route('/')
def home():
    # session.clear()
    return render_template('index.html')


@app.route('/verify', methods=['GET'])
def verify():
    # Don't reuse a SpotifyOAuth object because they store token info and you could leak user tokens if you reuse a SpotifyOAuth object
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET, redirect_uri=SPOTIPY_REDIRECT_URI, scope=SCOPE)
    url = sp_oauth.get_authorize_url()
    return redirect(url)


@app.route("/callback/")
def callback():
    global token
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET, redirect_uri=SPOTIPY_REDIRECT_URI, scope=SCOPE)

    code = request.args.get('code')
    token = sp_oauth.get_access_token(code)
    session["token"] = token["access_token"]
    session["playlist_df"] = pd.DataFrame()

    return redirect("/")


@app.route('/playlist/', methods=["GET"])
def get_playlist():
    if "token" not in session:
        return jsonify({'error': 'Access token missing'}), 401

    access_token = session["token"]
    headers = {'Authorization': f'Bearer {access_token}'}
    playlist_id = request.args.get('playlist_id')

    url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'

    response = requests.get(url, headers=headers)

    if response.status_code == 401:  # Token Expired
        session.clear()
        return jsonify({'Error': "Token has expired"}), 401

    if response.status_code != 200:
        return (response.text, response.status_code, response.headers.items())

    tracks = response.json()['items']

    track_ids = []
    track_names = []

    for i in range(len(tracks)):
        track_ids.append(tracks[i]["track"]["id"])
        track_names.append(tracks[i]["track"]["name"])

    audio_features = sp.audio_features(track_ids)
    playlist_df = pd.DataFrame(audio_features, index=track_names)
    playlist_df = playlist_df.drop(
        ["type", "uri", "track_href", "analysis_url", "time_signature"], axis=1)
    playlist_df.to_csv("data.csv")
    playlist_df.reset_index(inplace=True)
    # playlist_df = playlist_df.to_string()
    session["playlist_df"] = playlist_df
    return redirect("/")


if __name__ == '__main__':
    app.run(port=8000, debug=True)
