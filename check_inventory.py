from mon_atelier import app, db
from mon_atelier.routes import Fourniture

# Script de vérification de l'inventaire
if __name__ == '__main__':
    with app.app_context():
        fournitures = Fourniture.query.all()
        if not fournitures:
            print("Aucune fourniture trouvée dans la base de données.")
        else:
            print(f"{len(fournitures)} fournitures trouvées :")
            for f in fournitures:
                print(f"- {f.reference if hasattr(f, 'reference') else ''} | {f.nom} | Quantité : {f.quantite}")
