# Fichier : seed_prices.py

from mon_atelier import app, db
from mon_atelier.routes import seed_data

print("--- Début du script d'initialisation des tarifs ---")

# On utilise le contexte de l'application pour pouvoir interagir avec la base de données
with app.app_context():
    # Crée les tables si elles n'existent pas (par sécurité)
    db.create_all()
    
    # Appelle la fonction qui remplit les catégories et les tarifs
    print("Appel de la fonction seed_data pour les prestations...")
    seed_data()

print("--- Script terminé. Les tarifs devraient être dans la base de données. ---")