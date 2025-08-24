from mon_atelier import app, db
from mon_atelier.routes import seed_data  # Ajoute cette ligne

with app.app_context():
    db.create_all()
    seed_data()  # Ajoute cette ligne pour remplir la base au démarrage

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
