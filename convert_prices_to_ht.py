from mon_atelier import app, db
from mon_atelier.routes import DetailRetouche

def convert_prices():
    """
    Script pour convertir tous les prix des prestations de TTC à HT.
    """
    with app.app_context():
        tva_rate = app.config.get('TVA_RATE', 0.20)
        if tva_rate is None:
            print("ERREUR : Le taux de TVA n'est pas défini dans la configuration.")
            return

        prestations = DetailRetouche.query.all()
        if not prestations:
            print("Aucune prestation à convertir.")
            return

        print(f"Début de la conversion de {len(prestations)} prix (TTC vers HT) avec un taux de TVA de {tva_rate * 100}%...")

        count = 0
        for pres in prestations:
            if pres.prix is not None and pres.prix > 0:
                prix_ttc = pres.prix
                prix_ht = prix_ttc / (1 + tva_rate)
                pres.prix = round(prix_ht, 2) # On arrondit à 2 décimales
                count += 1
        
        db.session.commit()
        print(f"✅ Conversion terminée. {count} prix ont été mis à jour en HT.")

if __name__ == '__main__':
    convert_prices()
