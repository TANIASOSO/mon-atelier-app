from mon_atelier import app, db
from dotenv import load_dotenv
import os

load_dotenv()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
