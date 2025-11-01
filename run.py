from mon_atelier import app, db
from mon_atelier.routes import seed_data  
from dotenv import load_dotenv
load_dotenv()

with app.app_context():
    db.create_all()
    seed_data()  
    
__all__ = ['app']

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
