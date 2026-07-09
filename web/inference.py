from flask import Flask, render_template
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("audio_chunk")
def handle_audio_chunk(audio_data):
    print(f"Audio diterima: {len(audio_data)} bytes")


@socketio.on("recording_stopped")
def handle_recording_stopped():
    print("Rekaman browser dihentikan.")

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
    )