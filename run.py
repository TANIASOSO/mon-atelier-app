
from mon_atelier import app, db

# Create database tables if they don't exist
with app.app_context():
    db.create_all()
    
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
