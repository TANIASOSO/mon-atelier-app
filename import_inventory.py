import csv
from mon_atelier import app, db
from mon_atelier.routes import Fourniture

with app.app_context():
    db.create_all()
    with open('inventaire.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        headers = next(reader, None)
        for row in reader:
            # Ignore les colonnes vides à la fin
            row = [cell for cell in row if cell.strip() != '']
            print(f"Ligne lue : {row}")
            if len(row) < 4:
                print("Ligne ignorée (pas assez de colonnes)")
                continue
            try:
                reference, nom, couleur, quantite = row[:4]
                mapping = {
                    'reference': reference,
                    'nom': nom,
                    'couleur': couleur,
                    'quantite': quantite
                }
                print(f"Mapping utilisé pour insertion : {mapping}")
                fourniture = Fourniture(reference=reference, nom=nom, couleur=couleur, quantite=int(quantite))
                db.session.add(fourniture)
            except Exception as e:
                print(f"Erreur lors de l'insertion de la ligne {row} : {e}")
        try:
            db.session.commit()
            print("Commit réussi.")
        except Exception as e:
            print(f"Erreur lors du commit : {e}")