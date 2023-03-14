Spotify Playlist Generator Web App

This is a web application that generates a new Spotify playlist for a user based on their input playlist using a machine algorithm. The front end of the application is built with React and the back end is built with Flask.
Prerequisites

To run this application, you need to have the following:

    Node.js and npm installed on your computer
    Python 3.x installed on your computer
    A Spotify account

Installation

Clone the repository to your local machine:

    git clone https://github.com/your-username/spotify-playlist-generator.git

Install the dependencies for the front end:

    cd client
    npm install

Install the dependencies for the back end:

    cd ..
    pip install -r requirements.txt

Create a Spotify Developer account and create a new app. Then, set the Redirect URI to http://localhost:5000/callback in the app settings.

Create a .env file in the root directory of the project and add the following lines:

    SPOTIPY_CLIENT_ID=your_client_id
    SPOTIPY_CLIENT_SECRET=your_client_secret
    SPOTIPY_REDIRECT_URI=http://localhost:5000/callback

Replace your_client_id and your_client_secret with the Client ID and Client Secret from your Spotify app.
Usage

Start the back end server:

    python server.py

In a separate terminal window, start the front end server:

    cd client
    npm start

Open your web browser and navigate to http://localhost:3000

Log in to your Spotify account and enter the username and playlist name of the playlist you want to generate a new playlist from.

Click "Generate Playlist" and wait for the algorithm to finish.

The generated playlist will be displayed on the page. You can click "Save Playlist" to save it to your Spotify account.


License

This project is licensed under the MIT License - see the LICENSE file for details.
