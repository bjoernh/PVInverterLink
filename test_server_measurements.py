from flask import Flask, request
import json

app = Flask(__name__)


@app.route("/api/opendtu/measurements", methods=["POST"])
def receive_data():
    print("\n=== Received OpenDTU Data ===")
    data = request.json
    print(json.dumps(data, indent=2))
    return {"status": "success"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
