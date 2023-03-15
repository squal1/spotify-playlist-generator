import io
import os
import operator
import requests
import spotipy
import pandas as pd

from flask import Flask, request, jsonify, redirect, session, render_template, url_for
from flask_cors import CORS
from flask_session import Session
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from sklearn.ensemble._forest import RandomForestClassifier

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


def get_user():
    access_token = session["token"]
    headers = {'Authorization': f'Bearer {access_token}'}
    url = 'https://api.spotify.com/v1/me'
    response = requests.get(url, headers=headers)
    return response.json()["id"]


@app.context_processor
def handle_context():
    '''Inject object into jinja2 templates.'''
    return dict(io=io, pd=pd, operator=operator)


@app.route('/')
def home():
    # session.clear()
    if not session.get("step"):
        session["step"] = "1"
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
    session["user_id"] = get_user()
    session["step"] = "2"

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
    session["playlist_df"] = playlist_df
    session["step"] = "3"

    return redirect("/")


@app.route("/favorite-songs", methods=["POST"])
def favoriteSongs():
    ratings = [0 for _ in range(100)]
    selected_songs = request.form.to_dict()
    for key, value in selected_songs.items():
        ratings[int(key)] = 5
    session["ratings"] = ratings
    session["step"] = "4"

    return redirect("/")


@app.route("/least-favorite-songs", methods=["POST"])
def leastFavoriteSongs():
    ratings = session["ratings"]
    selected_songs = request.form.to_dict()
    for i in range(len(ratings)):
        if str(i) in selected_songs.keys():
            ratings[i] = 1
            continue
        elif ratings[i] == 0:
            ratings[i] = 3

    playlist_df = session["playlist_df"]
    playlist_df['ratings'] = ratings
    playlist_df.to_csv("data_w_rating.csv")
    session["step"] = "5"
    rec_playlist_df = get_recommendations()
    session["rec_playlist"] = rec_playlist_df
    build_model()
    return redirect("/")


def get_recommendations():
    redirect("/")
    rec_tracks = []
    playlist_df = session["playlist_df"]

    for i in playlist_df['id'].values.tolist():
        rec_tracks += sp.recommendations(seed_tracks=[i],
                                         limit=20)['tracks']
    rec_track_ids = []
    rec_track_names = []
    for i in rec_tracks:
        rec_track_ids.append(i['id'])
        rec_track_names.append(i['name'])

    rec_features = []
    for i in range(0, len(rec_track_ids)):
        rec_audio_features = sp.audio_features(rec_track_ids[i])
        for track in rec_audio_features:
            rec_features.append(track)

    rec_playlist_df = pd.DataFrame(rec_features, index=rec_track_ids)
    rec_playlist_df = rec_playlist_df.drop(
        ["type", "uri", "track_href", "analysis_url", "time_signature"], axis=1)
    return rec_playlist_df


def build_model():
    train_df = session["playlist_df"]
    train_x = train_df.drop(["index", "id", "ratings"], axis=1)
    train_y = train_df[["ratings"]]

    model = RandomForestClassifier(n_estimators=100, criterion='gini')
    model.fit(train_x, train_y)

    rec_list_df = session["rec_playlist"]
    rec_list_df = rec_list_df.drop(["id"], axis=1)

    predictions = model.predict(rec_list_df)
    rec_list_df['ratings'] = predictions

    rec_list_df = rec_list_df.sort_values('ratings', ascending=False)
    rec_list_df = rec_list_df.reset_index()

    recs_to_add = rec_list_df[rec_list_df['ratings']
                              == 5]['index'].values.tolist()

    print(recs_to_add)
    playlist_recs = sp.user_playlist_create(session["user_id"],
                                            name=f'Recommended Songs for Playlist by AI')

    # for i in range(len(recs_to_add[:100])):
    #     try:
    #         sp.user_playlist_add_tracks(
    #             session["user_id"], playlist_recs['id'], recs_to_add[i])
    #     except:
    #         continue
    sp.user_playlist_add_tracks(
        session["user_id"], playlist_recs['id'], recs_to_add)


if __name__ == '__main__':
    app.run(port=8000, debug=True)
