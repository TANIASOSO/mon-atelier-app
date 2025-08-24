from datetime import date, datetime, timedelta, time
from flask import render_template
from flask import request, redirect, url_for, jsonify, flash
from mon_atelier import app, db, twilio_client
from babel.dates import format_date
from collections import Counter, defaultdict

# --- MODÈLES DE BASE DE DONNÉES ---
retouche_fournitures = db.Table('retouche_fournitures',
    db.Column('detail_retouche_id', db.Integer, db.ForeignKey('detail_retouche.id'), primary_key=True),
    db.Column('fourniture_id', db.Integer, db.ForeignKey('fourniture.id'), primary_key=True)
)

class Fourniture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    reference = db.Column(db.String(50), nullable=True) # CORRECTION : unique=False pour permettre plusieurs champs vides
    couleur = db.Column(db.String(50), nullable=True)
    quantite = db.Column(db.Integer, default=0)

class DetailRetouche(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prix = db.Column(db.Float, nullable=True)
    sous_categorie_id = db.Column(db.Integer, db.ForeignKey('sous_categorie.id'), nullable=False)
    fournitures = db.relationship('Fourniture', secondary=retouche_fournitures, lazy='subquery',
        backref=db.backref('details_retouche', lazy=True))
    
    def __repr__(self):
        return f'<DetailRetouche {self.nom}>'
    
class Employe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=True)
    couleur = db.Column(db.String(10), nullable=True)  # Pour affichage planning

    def __repr__(self):
        return f'<Employe {self.nom}>'

class PresenceEmploye(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employe_id = db.Column(db.Integer, db.ForeignKey('employe.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    present = db.Column(db.Boolean, default=True)
    employe = db.relationship('Employe', backref='presences')

class CongeEmploye(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employe_id = db.Column(db.Integer, db.ForeignKey('employe.id'), nullable=False)
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)
    motif = db.Column(db.String(100), nullable=True)
    employe = db.relationship('Employe', backref='conges')

class PlanningShift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    heure_debut = db.Column(db.Time, nullable=False)
    heure_fin = db.Column(db.Time, nullable=False)
    tache = db.Column(db.String(100), nullable=True) # Par ex: 'Accueil', 'Atelier', 'Caisse'
    employe_id = db.Column(db.Integer, db.ForeignKey('employe.id'), nullable=True) (nullable)

    def __repr__(self):
        return f'<PlanningShift {self.employe.nom} le {self.date}>'
    
class Categorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)
    sous_categories = db.relationship('SousCategorie', backref='categorie', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Categorie {self.nom}>'

class SousCategorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    categorie_id = db.Column(db.Integer, db.ForeignKey('categorie.id'), nullable=False)
    details_retouches = db.relationship('DetailRetouche', backref='sous_categorie', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<SousCategorie {self.nom}>'
    
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    numero_telephone = db.Column(db.String(20), nullable=False, unique=True)  # Un numéro de téléphone unique
    retouches = db.relationship('Retouche', backref='client', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Client {self.nom} - {self.numero_telephone}>'
    
class Retouche(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    prix = db.Column(db.Float, nullable=True) 
    description = db.Column(db.Text, nullable=True)
    statut = db.Column(db.String(20), default='En cours')
    date_echeance = db.Column(db.Date, nullable=True)
    essayage_boutique = db.Column(db.Boolean, default=False)  # Nouveau champ
    
    detail_retouche_id = db.Column(db.Integer, db.ForeignKey('detail_retouche.id'), nullable=True)
    detail = db.relationship('DetailRetouche', backref='retouches')

    def __repr__(self):
        return f'<Retouche {self.id} pour {self.nom_client}>'


# --- CRÉATION INITIALE DE LA BASE DE DONNÉES ---

# --- PAGES WEB (LES ROUTES) ---

    from datetime import timedelta
@app.route("/")
def index():
    semaine = int(request.args.get('semaine', 0))
    today = date.today()
    days_since_tuesday = (today.weekday() - 1 + 7) % 7
    start_of_current_week = today - timedelta(days=days_since_tuesday)
    start_week = start_of_current_week + timedelta(weeks=semaine)
    end_week = start_week + timedelta(days=4)
    employes = Employe.query.order_by(Employe.nom).all()
    shifts_semaine = PlanningShift.query.filter(
        PlanningShift.date >= start_week, 
        PlanningShift.date <= end_week
    ).all()
    schedule_data = {emp.id: {} for emp in employes}
    for shift in shifts_semaine:
        if shift.date not in schedule_data.get(shift.employe_id, {}):
            schedule_data[shift.employe_id][shift.date] = []
        schedule_data[shift.employe_id][shift.date].append(shift)
    week_dates = [start_week + timedelta(days=i) for i in range(5)]
    jours_fr = ['Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
    # Ajout des congés si utilisés dans le template
    conges = CongeEmploye.query.filter(CongeEmploye.date_debut <= end_week, CongeEmploye.date_fin >= start_week).all()
    return render_template('index.html', 
                           employes=employes,
                           schedule_data=schedule_data,
                           week_dates=week_dates,
                           jours_fr=jours_fr,
                           semaine=semaine,
                           conges=conges)

# --- Route de gestion globale présence/congé ---
@app.route('/gestion_presence_conge', methods=['GET', 'POST'])
def gestion_presence_conge():
    # Récupérer la liste des employés
    employes = Employe.query.all()
    from datetime import date
    selected_employe_id = request.form.get('employe_id')
    selected_date = request.form.get('date')
    if not selected_date:
        selected_date = date.today().strftime('%Y-%m-%d')
    if request.method == 'POST' and selected_employe_id:
        return redirect(url_for('modifier_presence_conge', employe_id=selected_employe_id, date=selected_date))
    return render_template('gestion_presence_conge.html', employes=employes, selected_date=selected_date)

# --- NOUVELLE ROUTE POUR AJOUTER UN SHIFT AU PLANNING EMPLOYÉ ---
@app.route('/planning/shift/ajouter', methods=['POST'])
def ajouter_shift():
    from datetime import datetime, time
    employe_id = 1
    date_str = request.form.get('date')
    heure_debut_str = request.form.get('heure_debut')
    heure_fin_str = request.form.get('heure_fin')
    tache = request.form.get('tache')
    # Vérification des champs obligatoires
    if not all([employe_id, date_str, heure_debut_str, heure_fin_str]):
        return redirect(request.referrer or url_for('index'))
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    heure_debut_obj = time.fromisoformat(heure_debut_str)
    heure_fin_obj = time.fromisoformat(heure_fin_str)
    nouveau_shift = PlanningShift(
        employe_id=employe_id,
        date=date_obj,
        heure_debut=heure_debut_obj,
        heure_fin=heure_fin_obj,
        tache=tache
    )
    db.session.add(nouveau_shift)
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route("/ajouter", methods=['GET', 'POST'])
def ajouter_retouche():
    if request.method == 'POST':
        date_str = request.form.get('date_echeance')
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        nom_client_form = request.form.get('nom_client')
        numero_telephone_form = request.form.get('numero_telephone')

        # On cherche ou on crée le client
        client = Client.query.filter_by(numero_telephone=numero_telephone_form).first()
        if not client:
            client = Client(nom=nom_client_form, numero_telephone=numero_telephone_form)
            db.session.add(client)
            db.session.flush() # Important pour obtenir un ID avant le commit
        else:
            if client.nom != nom_client_form:
                client.nom = nom_client_form

        detail_ids = request.form.getlist('detail_retouche_id[]')
        prixs = request.form.getlist('prix[]')
        descriptions = request.form.getlist('description[]')
        quantites = request.form.getlist('quantite[]')
        essayage_boutique = request.form.get('essayage_boutique') == 'on'  # Nouveau champ
        
        retouches_creees = []
        total_ht = 0.0

        for i in range(len(detail_ids)):
            detail_id = detail_ids[i]
            detail = DetailRetouche.query.get(detail_id) if detail_id else None
            prix_val = prixs[i] if i < len(prixs) else None
            prix_retouche = None
            try:
                if prix_val:
                    prix_retouche = float(prix_val)
            except (ValueError, TypeError):
                pass
            if prix_retouche is None:
                prix_retouche = detail.prix if detail else 0.0

            description = descriptions[i] if i < len(descriptions) else ""
            quantite = int(quantites[i]) if i < len(quantites) and quantites[i] else 1

            for _ in range(quantite):
                if detail:
                    for fourniture in detail.fournitures:
                        fourniture.quantite -= 1
                nouvelle_retouche = Retouche(
                    client_id=client.id,
                    prix=prix_retouche,
                    description=description,
                    date_echeance=date_obj,
                    detail_retouche_id=detail.id if detail else None,
                    essayage_boutique=essayage_boutique  # Nouveau champ
                )
                db.session.add(nouvelle_retouche)
                retouches_creees.append(nouvelle_retouche)
                if prix_retouche:
                    total_ht += prix_retouche
        db.session.commit()

        # Calcul de la TVA et du total
        tva_rate = app.config['TVA_RATE']
        montant_tva = total_ht * tva_rate
        total_ttc = total_ht + montant_tva
        
        # On utilise l'ID de la première retouche comme numéro de ticket
        numero_ticket = retouches_creees[0].id if retouches_creees else None
        
        now = datetime.now()
        date_formatee = format_date(now, format='full', locale='fr_FR')
        return render_template('ticket.html', 
                               client=client,
                               retouches=retouches_creees,
                               total_ht=total_ht,
                               montant_tva=montant_tva,
                               total_ttc=total_ttc,
                               tva_rate=tva_rate,
                               numero_ticket=numero_ticket,
                               now=now,
                               date_formatee=date_formatee)
    
    # Le code pour la méthode GET ne change pas
    clients = Client.query.all()
    categories = Categorie.query.all()
    date_selectionnee = request.args.get('date') 
    return render_template('ajouter_retouche.html', 
                           categories=categories, 
                           clients=clients,
                           date_selectionnee=date_selectionnee)


# --- ROUTES MANQUANTES RÉINTÉGRÉES ET MISES À JOUR ---

@app.route("/planning", methods=['GET', 'POST'])
@app.route("/planning", methods=['GET', 'POST'])
def planning():
    semaine = int(request.args.get('semaine', 0))
    today = date.today()
    days_since_tuesday = (today.weekday() - 1 + 7) % 7
    start_of_current_week = today - timedelta(days=days_since_tuesday)
    start_week = start_of_current_week + timedelta(weeks=semaine)
    end_week = start_week + timedelta(days=4)

    # Récupérer toutes les retouches de la semaine
    retouches = db.session.query(db.Model).session.query(Retouche).filter(
        Retouche.date_echeance >= start_week,
        Retouche.date_echeance <= end_week
    ).all()

    # Groupement par client puis par jour
    # Regrouper toutes les retouches de la semaine par client et par type de retouche (additionner les quantités)
    planning_resume = defaultdict(lambda: defaultdict(int))  # {client: {nom_retouche: quantite_totale}}
    for r in retouches:
        if r.client and r.detail:
            planning_resume[r.client.nom][r.detail.nom] += 1

    # On veut une seule case par client, donc on prépare une liste de tuples (client, liste de dicts retouches)
    planning_resume_list = []
    for client, retouches_dict in planning_resume.items():
        items = [
            {'nom': nom, 'quantite': quantite}
            for nom, quantite in retouches_dict.items()
        ]
        planning_resume_list.append((client, items))

    return render_template('planning.html', semaine=semaine, start_week=start_week, planning_resume=planning_resume_list)

@app.route("/retouche/<int:id>", methods=['GET', 'POST'])
def detail_retouche(id):
    retouche = Retouche.query.get_or_404(id)
    if request.method == 'POST':
        nouveau_statut = request.form.get('statut')
        if nouveau_statut:
            retouche.statut = nouveau_statut
            db.session.commit()
            if nouveau_statut == 'Terminée':
                try:
                    # ... (logique d'envoi de SMS) ...
                    pass
                except Exception as e:
                    print(f"Erreur SMS: {e}")
            return redirect(request.referrer or url_for('index'))
    return render_template('retouche_detail.html', retouche=retouche)


@app.route('/retouche/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_retouche(id):
    retouche = Retouche.query.get_or_404(id)
    if request.method == 'POST':
        # Correction gestion client
        client_id = request.form.get('client_id')
        numero_telephone = request.form.get('numero_telephone')
        if client_id:
            client = Client.query.get(client_id)
            if client:
                retouche.client_id = client.id
        elif numero_telephone:
            client = Client.query.filter_by(numero_telephone=numero_telephone).first()
            if client:
                retouche.client_id = client.id

        retouche.prix = float(request.form.get('prix')) if request.form.get('prix') else None
        retouche.description = request.form.get('description')
        retouche.statut = request.form.get('statut')
        retouche.essayage_boutique = request.form.get('essayage_boutique') == 'on'

        detail_id = request.form.get('detail_retouche_id')
        retouche.detail_retouche_id = int(detail_id) if detail_id else None

        date_str = request.form.get('date_echeance')
        retouche.date_echeance = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None

        db.session.commit()
        return redirect(url_for('detail_retouche', id=retouche.id))

    # Pour GET, on prépare les données pour les menus déroulants
    categories = Categorie.query.all()
    return render_template('modifier_retouche.html', retouche=retouche, categories=categories)

# --- ROUTES API POUR LES MENUS DÉROULANTS DYNAMIQUES ---

@app.route('/api/sous_categories/<int:categorie_id>')
def api_get_sous_categories(categorie_id):
    sous_categories = SousCategorie.query.filter_by(categorie_id=categorie_id).all()
    return jsonify([{'id': sc.id, 'nom': sc.nom} for sc in sous_categories])

@app.route('/api/details_retouche/<int:sous_categorie_id>')
def api_get_details_retouche(sous_categorie_id):
    details = DetailRetouche.query.filter_by(sous_categorie_id=sous_categorie_id).all()
    return jsonify([{'id': d.id, 'nom': d.nom, 'prix': d.prix} for d in details])

@app.route('/aujourdhui')
def vue_aujourdhui():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    retouches_du_jour = Retouche.query.join(Client).filter(
        Retouche.date_echeance >= today, 
        Retouche.date_echeance < tomorrow
    ).order_by(Client.nom).all()

    retouches_par_client = {}
    for retouche in retouches_du_jour:
        nom_client = retouche.client.nom
        if nom_client not in retouches_par_client:
            retouches_par_client[nom_client] = []
        
        # LA CORRECTION EST ICI : On crée un dictionnaire propre pour le JavaScript
        retouche_data = {
            'id': retouche.id,
            'statut': retouche.statut,
            'description': retouche.description,
            'detail': None
        }
        if retouche.detail:
            retouche_data['detail'] = {
                'nom': retouche.detail.nom,
                'sous_categorie': {
                    'categorie': {
                        'nom': retouche.detail.sous_categorie.categorie.nom
                    }
                }
            }
        retouches_par_client[nom_client].append(retouche_data)

    return render_template('aujourdhui.html', 
                           retouches_par_client=retouches_par_client, 
                           date_jour=today)


@app.route('/retouche/update_status/<int:retouche_id>', methods=['POST'])
def update_status(retouche_id):
    retouche = Retouche.query.get_or_404(retouche_id)
    nouveau_statut = request.form.get('statut')

    if nouveau_statut:
        retouche.statut = nouveau_statut
        db.session.commit()

        # --- BLOC D'ENVOI DE SMS ---
        if nouveau_statut == 'Terminée':
            print(f"Tentative d'envoi de SMS pour la retouche #{retouche.id}...")
            try:
                if retouche.client and retouche.client.numero_telephone:
                    # Formatage du numéro pour Twilio (ex: 0612345678 -> +33612345678)
                    numero_original = retouche.client.numero_telephone
                    if not numero_original.startswith('+'):
                        numero_final = '+33' + numero_original.lstrip('0')
                    else:
                        numero_final = numero_original
                    
                    message_body = (
                        "Bonjour,\n"
                        "Votre vêtement est prêt veuillez confirmer la réception du message\n"
                        "Cordialement,\n"
                        "Paula Couture\n"
                        "0479688584"
                    )
                    
                    message = twilio_client.messages.create(
                        body=message_body,
                        from_=app.config['TWILIO_PHONE_NUMBER'],
                        to=numero_final
                    )
                    print(f"SMS envoyé avec succès à {retouche.client.nom} au {numero_final}")
                    flash(f"Statut mis à jour et SMS envoyé à {retouche.client.nom}.", "success")
                else:
                    print("ERREUR : Client ou numéro de téléphone manquant.")
                    flash("Statut mis à jour, mais le SMS n'a pas pu être envoyé (client ou numéro manquant).", "warning")
            
            except Exception as e:
                print(f"ERREUR lors de l'envoi du SMS : {e}")
                flash(f"Statut mis à jour, mais une erreur est survenue lors de l'envoi du SMS : {e}", "danger")
    
    # Redirige vers la page précédente (la page de détail de la retouche)
    return redirect(request.referrer or url_for('detail_retouche', id=retouche_id))

# --- ROUTES POUR LA PAGE PARAMÈTRES ---

@app.route('/parametres')
def parametres():
    categories = Categorie.query.order_by(Categorie.nom).all()
    employes = Employe.query.order_by(Employe.nom).all()
    fournitures = Fourniture.query.order_by(Fourniture.nom).all()
    return render_template('parametres.html', categories=categories, employes=employes, fournitures=fournitures)

@app.route('/parametres/categorie/ajouter', methods=['POST'])
def ajouter_categorie():
    nom = request.form.get('nom')
    if nom:
        db.session.add(Categorie(nom=nom))
        db.session.commit()
    return redirect(url_for('parametres'))

@app.route('/parametres/sous_categorie/ajouter', methods=['POST'])
def ajouter_sous_categorie():
    nom = request.form.get('nom')
    categorie_id = request.form.get('categorie_id')
    if nom and categorie_id:
        db.session.add(SousCategorie(nom=nom, categorie_id=categorie_id))
        db.session.commit()
    return redirect(url_for('parametres'))

# Dans votre fichier app.py (ou équivalent)

@app.route('/parametres/detail/ajouter', methods=['POST'])
def ajouter_detail_retouche():
    nom = request.form.get('nom')
    prix_str = request.form.get('prix')
    prix = float(prix_str) if prix_str else None
    sous_categorie_id = request.form.get('sous_categorie_id')
    
    # Récupérer les IDs des fournitures sélectionnées
    fourniture_ids = request.form.getlist('fournitures')
    nouveau_detail = DetailRetouche(
        nom=nom,
        prix=prix,
        sous_categorie_id=sous_categorie_id
    )

    # Si des fournitures ont été sélectionnées
    if fourniture_ids:
        # Récupérer les objets Fourniture depuis la base de données
        fournitures_a_lier = Fourniture.query.filter(Fourniture.id.in_(fourniture_ids)).all()
        # Lier les fournitures (pas de décrémentation du stock ici)
        for fourniture in fournitures_a_lier:
            nouveau_detail.fournitures.append(fourniture)
    
    db.session.add(nouveau_detail)
    db.session.commit()
    
    flash('Le détail de la retouche a été ajouté avec succès.', 'success')
    return redirect(url_for('parametres'))

@app.route('/parametres/supprimer/<string:type>/<int:id>', methods=['POST'])
def supprimer_parametre(type, id):
    if type == 'categorie':
        item = Categorie.query.get_or_404(id)
    elif type == 'sous_categorie':
        item = SousCategorie.query.get_or_404(id)
    elif type == 'detail':
        item = DetailRetouche.query.get_or_404(id)
    else:
        return "Type invalide", 404
    
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('parametres'))

@app.route('/parametres/employe/ajouter', methods=['POST'])
def ajouter_employe():
    nom = request.form.get('nom')
    role = request.form.get('role')
    couleur = request.form.get('couleur')
    if nom and role and couleur:
        nouvel_employe = Employe(nom=nom, role=role, couleur=couleur)
        db.session.add(nouvel_employe)
        db.session.commit()
    return redirect(url_for('parametres'))

@app.route('/parametres/employe/supprimer/<int:employe_id>', methods=['POST'])
def supprimer_employe(employe_id):
    employe_a_supprimer = Employe.query.get_or_404(employe_id)
    db.session.delete(employe_a_supprimer)
    db.session.commit()
    return redirect(url_for('parametres'))

@app.route('/parametres/categorie/modifier/<int:id>', methods=['POST'])
def modifier_categorie(id):
    categorie = Categorie.query.get_or_404(id)
    nouveau_nom = request.form.get('nom')
    if nouveau_nom:
        categorie.nom = nouveau_nom
        db.session.commit()
    return redirect(url_for('parametres'))

@app.route('/parametres/sous_categorie/modifier/<int:id>', methods=['POST'])
def modifier_sous_categorie(id):
    sous_categorie = SousCategorie.query.get_or_404(id)
    nouveau_nom = request.form.get('nom')
    if nouveau_nom:
        sous_categorie.nom = nouveau_nom
        db.session.commit()
    return redirect(url_for('parametres'))

# Dans votre fichier app.py (ou équivalent)

@app.route('/parametres/detail/modifier/<int:detail_id>', methods=['POST'])
def modifier_detail_retouche(detail_id):
    detail = DetailRetouche.query.get_or_404(detail_id)
    
    # Récupérer les données du formulaire
    detail.nom = request.form.get('nom')
    prix_str = request.form.get('prix')
    detail.prix = float(prix_str) if prix_str else None
    
    # --- LOGIQUE DE MISE À JOUR DE L'INVENTAIRE ---
    
    # 1. Obtenir l'ensemble des IDs des fournitures actuelles
    ids_actuels = {fourniture.id for fourniture in detail.fournitures}
    
    # 2. Obtenir l'ensemble des IDs des fournitures soumises par le formulaire
    ids_soumis = {int(id) for id in request.form.getlist('fournitures')}
    
    # 3. Trouver les fournitures à retirer (celles qui étaient là mais ne le sont plus)
    ids_a_retirer = ids_actuels - ids_soumis
    if ids_a_retirer:
        fournitures_a_retirer = Fourniture.query.filter(Fourniture.id.in_(ids_a_retirer)).all()
        for f in fournitures_a_retirer:
            f.quantite += 1 # On "remet" l'article en stock
            
    # 4. Trouver les fournitures à ajouter (celles qui n'étaient pas là mais le sont maintenant)
    ids_a_ajouter = ids_soumis - ids_actuels
    if ids_a_ajouter:
        fournitures_a_ajouter = Fourniture.query.filter(Fourniture.id.in_(ids_a_ajouter)).all()
        for f in fournitures_a_ajouter:
            if f.quantite > 0:
                f.quantite -= 1 # On "consomme" l'article du stock

    # 5. Mettre à jour la liste des fournitures pour la retouche
    detail.fournitures = Fourniture.query.filter(Fourniture.id.in_(ids_soumis)).all()
    
    db.session.commit()
    flash('Le détail de la retouche a été mis à jour.', 'success')
    return redirect(url_for('parametres'))

@app.route('/parametres/fourniture/ajouter', methods=['POST'])
def ajouter_fourniture():
    nom = request.form.get('nom')
    reference = request.form.get('reference')
    quantite = request.form.get('quantite', 0, type=int)
    if nom:
        nouvelle_fourniture = Fourniture(nom=nom, reference=reference, quantite=quantite)
        db.session.add(nouvelle_fourniture)
        db.session.commit()
    return redirect(url_for('parametres'))

@app.route('/parametres/fourniture/modifier/<int:id>', methods=['POST'])
def modifier_fourniture(id):
    fourniture = Fourniture.query.get_or_404(id)
    fourniture.nom = request.form.get('nom')
    fourniture.reference = request.form.get('reference')
    fourniture.quantite = request.form.get('quantite', type=int)
    db.session.commit()
    return redirect(url_for('parametres'))

@app.route('/inventaire')
def inventaire():
    fournitures = Fourniture.query.order_by(Fourniture.nom).all()
    return render_template('inventaire.html', fournitures=fournitures)

@app.route('/ajouter_presence_conge', methods=['POST'])
def ajouter_presence_conge():
    from datetime import datetime, timedelta
    employe_id = request.form.get('employe_id')
    type_ = request.form.get('type')
    date_debut_str = request.form.get('date_debut')
    date_fin_str = request.form.get('date_fin')
    motif = request.form.get('motif')
    if not (employe_id and date_debut_str and date_fin_str and type_):
        return jsonify({'success': False, 'error': 'Champs manquants.'})
    employe = Employe.query.get(employe_id)
    if not employe:
        return jsonify({'success': False, 'error': 'Employé introuvable.'})
    date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
    date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
    # Supprimer présence/congé existant sur la période pour cet employé
    for d in (date_debut + timedelta(days=n) for n in range((date_fin-date_debut).days+1)):
        PresenceEmploye.query.filter_by(employe_id=employe_id, date=d).delete()
        CongeEmploye.query.filter(CongeEmploye.employe_id==employe_id, CongeEmploye.date_debut<=d, CongeEmploye.date_fin>=d).delete()
    event = None
    if type_ == 'presence':
        # Ajouter une présence pour chaque jour de la période
        for d in (date_debut + timedelta(days=n) for n in range((date_fin-date_debut).days+1)):
            db.session.add(PresenceEmploye(employe_id=employe_id, date=d, present=True))
        event = {
            'title': 'Présent',
            'start': date_debut_str,
            'end': (date_fin + timedelta(days=1)).strftime('%Y-%m-%d'),
            'color': employe.couleur or '#48c774',
            'allDay': True
        }
    elif type_ == 'conge':
        conge = CongeEmploye(employe_id=employe_id, date_debut=date_debut, date_fin=date_fin, motif=motif)
        db.session.add(conge)
        event = {
            'title': motif or 'Congé',
            'start': date_debut_str,
            'end': (date_fin + timedelta(days=1)).strftime('%Y-%m-%d'),
            'color': '#f14668',
            'allDay': True
        }
    else:
        return jsonify({'success': False, 'error': 'Type inconnu.'})
    db.session.commit()
    return jsonify({'success': True, 'event': event})


@app.route('/calendrier_annuel/<int:employe_id>')
def calendrier_annuel(employe_id):
    employe = Employe.query.get_or_404(employe_id)
    
    # Récupérer les données de présence pour l'année
    shifts = PlanningShift.query.filter_by(employe_id=employe_id).all()
    presences = PresenceEmploye.query.filter_by(employe_id=employe_id, present=True).all()
    conges = CongeEmploye.query.filter_by(employe_id=employe_id).all()
    
    events = []
    
    # Formater les shifts (présence avec tâche)
    for shift in shifts:
        events.append({
            'title': shift.tache or 'Présence',
            'start': shift.date.isoformat(),
            'backgroundColor': employe.couleur or '#3788d8',
            'borderColor': employe.couleur or '#3788d8'
        })

    # Formater les présences simples (sans écraser les shifts)
    shift_dates = {s.date for s in shifts}
    for presence in presences:
        if presence.date not in shift_dates:
            events.append({
                'title': 'Présent',
                'start': presence.date.isoformat(),
                'backgroundColor': employe.couleur or '#3788d8',
                'borderColor': employe.couleur or '#3788d8'
            })
        
    # Formater les congés
    for conge in conges:
        end_date = conge.date_fin + timedelta(days=1)
        events.append({
            'title': conge.motif or 'Congé',
            'start': conge.date_debut.isoformat(),
            'end': end_date.isoformat(),
            'display': 'background',
            'backgroundColor': '#ff9f89',
            'borderColor': '#ff9f89'
        })

    print(events)

    return render_template('calendrier_annuel.html', employe=employe, events=events)

# --- FONCTION POUR ALIMENTER LA BASE DE DONNÉES (VERSION FINALE ET COMPLÈTE) ---
def seed_data():
    # On vérifie si des données existent déjà pour ne pas les recréer
    if DetailRetouche.query.first():
        print("La base de données contient déjà des prestations.")
        return

    print("Création de la nouvelle grille tarifaire...")

    # --- 1. Création des CATÉGORIES ---
    cat_pantalon = Categorie(nom="Pantalon")
    cat_robe_jupe = Categorie(nom="Robe & Jupe")
    cat_veste = Categorie(nom="Veste & Manteau")
    cat_haut = Categorie(nom="Haut (Chemise, T-shirt)")
    cat_divers = Categorie(nom="Divers")
    db.session.add_all([cat_pantalon, cat_robe_jupe, cat_veste, cat_haut, cat_divers])
    db.session.commit()

    # --- 2. Création des SOUS-CATÉGORIES ---
    # Pantalon
    sc_p_ourlet = SousCategorie(nom="Ourlet", categorie_id=cat_pantalon.id)
    sc_p_taille = SousCategorie(nom="Taille & Côtés", categorie_id=cat_pantalon.id)
    sc_p_fermeture = SousCategorie(nom="Fermeture", categorie_id=cat_pantalon.id)
    sc_p_reparation = SousCategorie(nom="Réparation & Divers", categorie_id=cat_pantalon.id)
    # Robe & Jupe
    sc_rj_ourlet = SousCategorie(nom="Ourlet", categorie_id=cat_robe_jupe.id)
    sc_rj_taille = SousCategorie(nom="Taille & Côtés", categorie_id=cat_robe_jupe.id)
    sc_rj_fermeture = SousCategorie(nom="Fermeture", categorie_id=cat_robe_jupe.id)
    sc_rj_reparation = SousCategorie(nom="Réparation & Divers", categorie_id=cat_robe_jupe.id)
    # Veste & Manteau
    sc_v_manches = SousCategorie(nom="Manches", categorie_id=cat_veste.id)
    sc_v_ourlet = SousCategorie(nom="Ourlet Bas", categorie_id=cat_veste.id)
    sc_v_fermeture = SousCategorie(nom="Fermeture & Doublure", categorie_id=cat_veste.id)
    sc_v_reprise = SousCategorie(nom="Reprise & Cintrâge", categorie_id=cat_veste.id)
    # Haut
    sc_h_manches = SousCategorie(nom="Manches", categorie_id=cat_haut.id)
    sc_h_ourlet = SousCategorie(nom="Ourlet Bas", categorie_id=cat_haut.id)
    sc_h_reprise = SousCategorie(nom="Reprise & Cintrâge", categorie_id=cat_haut.id)
    # Divers
    sc_d_reparation = SousCategorie(nom="Réparation", categorie_id=cat_divers.id)
    sc_d_confection = SousCategorie(nom="Confection & Spéciaux", categorie_id=cat_divers.id)

    db.session.add_all([
        sc_p_ourlet, sc_p_taille, sc_p_fermeture, sc_p_reparation,
        sc_rj_ourlet, sc_rj_taille, sc_rj_fermeture, sc_rj_reparation,
        sc_v_manches, sc_v_ourlet, sc_v_fermeture, sc_v_reprise,
        sc_h_manches, sc_h_ourlet, sc_h_reprise,
        sc_d_reparation, sc_d_confection
    ])
    db.session.commit()

    # --- 3. Création des DÉTAILS de retouches (les prestations) ---
    db.session.add_all([
        # Pantalon
        DetailRetouche(nom="Ourlet simple", prix=9.00, sous_categorie_id=sc_p_ourlet.id),
        DetailRetouche(nom="Ourlet invisible", prix=11.00, sous_categorie_id=sc_p_ourlet.id),
        DetailRetouche(nom="Ourlet revers", prix=12.00, sous_categorie_id=sc_p_ourlet.id),
        DetailRetouche(nom="Supplément talonette", prix=2.00, sous_categorie_id=sc_p_ourlet.id),
        DetailRetouche(nom="Reprise taille/côté costume homme", prix=17.00, sous_categorie_id=sc_p_taille.id),
        DetailRetouche(nom="Elargir taille/côtés", prix=25.00, sous_categorie_id=sc_p_taille.id),
        DetailRetouche(nom="Reprise taille/côté", prix=23.00, sous_categorie_id=sc_p_taille.id),
        DetailRetouche(nom="Changement fermeture", prix=18.00, sous_categorie_id=sc_p_fermeture.id),
        DetailRetouche(nom="Changement doublure", prix=30.00, sous_categorie_id=sc_p_fermeture.id),
        DetailRetouche(nom="Fuselage", prix=24.00, sous_categorie_id=sc_p_reparation.id),
        DetailRetouche(nom="Fuselage demi", prix=16.00, sous_categorie_id=sc_p_reparation.id),
        DetailRetouche(nom="Changement poche", prix=15.00, sous_categorie_id=sc_p_reparation.id),

        # Robe & Jupe
        DetailRetouche(nom="Changement fermeture", prix=19.00, sous_categorie_id=sc_rj_fermeture.id),
        DetailRetouche(nom="Changement élastiques taille", prix=18.00, sous_categorie_id=sc_rj_taille.id),
        DetailRetouche(nom="Reprendre/élargir la taille/côtés", prix=25.00, sous_categorie_id=sc_rj_taille.id),
        DetailRetouche(nom="Reprendre/élargir les côtés + taille", prix=28.00, sous_categorie_id=sc_rj_taille.id),
        DetailRetouche(nom="Ourlet piqué (sans doublure)", prix=19.00, sous_categorie_id=sc_rj_ourlet.id),
        DetailRetouche(nom="Ourlet piqué (avec doublure)", prix=27.00, sous_categorie_id=sc_rj_ourlet.id),
        DetailRetouche(nom="Ourlet invisible (sans doublure)", prix=22.00, sous_categorie_id=sc_rj_ourlet.id),
        DetailRetouche(nom="Reprise bretelles simple", prix=12.00, sous_categorie_id=sc_rj_reparation.id),
        DetailRetouche(nom="Reprise bretelles complexe", prix=18.00, sous_categorie_id=sc_rj_reparation.id),
        DetailRetouche(nom="Reprise épaules", prix=25.00, sous_categorie_id=sc_rj_reparation.id),
        DetailRetouche(nom="Changement doublure", prix=35.00, sous_categorie_id=sc_rj_fermeture.id),

        # Veste & Manteau
        DetailRetouche(nom="Bas manches simple (sans fente, bouton, doublure)", prix=17.00, sous_categorie_id=sc_v_manches.id),
        DetailRetouche(nom="Bas manches avec doublure / déplacement poignet", prix=20.00, sous_categorie_id=sc_v_manches.id),
        DetailRetouche(nom="Bas manches costume doublé", prix=25.00, sous_categorie_id=sc_v_manches.id),
        DetailRetouche(nom="Ourlet bas veste/manteau", prix=40.00, sous_categorie_id=sc_v_ourlet.id),
        DetailRetouche(nom="Changer fermeture", prix=42.00, sous_categorie_id=sc_v_fermeture.id),
        DetailRetouche(nom="Changer doublure (selon travail)", prix=85.00, sous_categorie_id=sc_v_fermeture.id),
        DetailRetouche(nom="Reprise/cintrage sans doublure", prix=25.00, sous_categorie_id=sc_v_reprise.id),
        DetailRetouche(nom="Reprise/cintrage avec doublure", prix=30.00, sous_categorie_id=sc_v_reprise.id),

        # Haut (Chemise, T-shirt)
        DetailRetouche(nom="Manches bas simple", prix=17.00, sous_categorie_id=sc_h_manches.id),
        DetailRetouche(nom="Manches bas avec poignet", prix=24.00, sous_categorie_id=sc_h_manches.id),
        DetailRetouche(nom="Ourlet bas", prix=17.00, sous_categorie_id=sc_h_ourlet.id),
        DetailRetouche(nom="Reprise/cintrage T-shirt, Top", prix=16.00, sous_categorie_id=sc_h_reprise.id),
        DetailRetouche(nom="Reprise/cintrage chemise sans doublure", prix=19.00, sous_categorie_id=sc_h_reprise.id),
        DetailRetouche(nom="Reprise/cintrage chemise avec doublure", prix=23.00, sous_categorie_id=sc_h_reprise.id),
        DetailRetouche(nom="Reprise épaule", prix=28.00, sous_categorie_id=sc_h_reprise.id),

        # Divers
        DetailRetouche(nom="Accros", prix=8.00, sous_categorie_id=sc_d_reparation.id),
        DetailRetouche(nom="Coudière", prix=16.00, sous_categorie_id=sc_d_reparation.id),
        DetailRetouche(nom="Curseur", prix=7.00, sous_categorie_id=sc_d_reparation.id),
        DetailRetouche(nom="Changement élastique taille", prix=17.00, sous_categorie_id=sc_d_reparation.id),
        DetailRetouche(nom="Remplacement bouton, pression, crochet", prix=6.00, sous_categorie_id=sc_d_reparation.id),
        DetailRetouche(nom="Pause ou retirer épaulettes", prix=16.00, sous_categorie_id=sc_d_reparation.id),
        DetailRetouche(nom="Ourlet rideau/nappe", prix=15.00, sous_categorie_id=sc_d_confection.id),
    ])
    
    db.session.commit()
    print("Nouvelle grille tarifaire chargée avec succès.")

@app.route('/modifier_planning_employe', methods=['GET', 'POST'])
def modifier_planning_employe():
    from datetime import timedelta, datetime
    # Afficher le planning de tous les employés sur le même calendrier
    employes = Employe.query.order_by(Employe.nom).all()
    events = []
    for employe in employes:
        presences = PresenceEmploye.query.filter_by(employe_id=employe.id, present=True).all()
        conges = CongeEmploye.query.filter_by(employe_id=employe.id).all()
        for p in presences:
            events.append({
                'title': f"{employe.nom} (Présent)",
                'start': p.date.strftime('%Y-%m-%d'),
                'end': p.date.strftime('%Y-%m-%d'),
                'color': employe.couleur or '#48c774',
                'allDay': True
            })
        for c in conges:
            events.append({
                'title': f"{employe.nom} (Congé : {c.motif})" if c.motif else f"{employe.nom} (Congé)",
                'start': c.date_debut.strftime('%Y-%m-%d'),
                'end': (c.date_fin + timedelta(days=1)).strftime('%Y-%m-%d'),
                'color': '#ff69b4',  # Rose pour les congés
                'allDay': True
            })
    return render_template('modifier_planning_employe.html', employes=employes, events=events)



@app.route('/calendrier_mensuel/<int:employe_id>')
def calendrier_mensuel(employe_id):
    employe = Employe.query.get_or_404(employe_id)
    # Récupérer le mois et l'année depuis les paramètres GET
    from datetime import datetime
    today = date.today()
    mois = int(request.args.get('mois', today.month))
    annee = int(request.args.get('annee', today.year))
    # Premier et dernier jour du mois
    from calendar import monthrange
    premier_jour = date(annee, mois, 1)
    dernier_jour = date(annee, mois, monthrange(annee, mois)[1])
    presences = PresenceEmploye.query.filter_by(employe_id=employe_id).filter(
        PresenceEmploye.date >= premier_jour, PresenceEmploye.date <= dernier_jour).all()
    conges = CongeEmploye.query.filter_by(employe_id=employe_id).filter(
        CongeEmploye.date_fin >= premier_jour, CongeEmploye.date_debut <= dernier_jour).all()
    events = []
    for p in presences:
        events.append({
            'title': 'Présent',
            'start': p.date.strftime('%Y-%m-%d'),
            'end': p.date.strftime('%Y-%m-%d'),
            'color': '#48c774'
        })
    for c in conges:
        events.append({
            'title': c.motif or 'Congé',
            'start': c.date_debut.strftime('%Y-%m-%d'),
            'end': (c.date_fin + timedelta(days=1)).strftime('%Y-%m-%d'),
            'color': '#f14668'
        })
    return render_template('calendrier_mensuel.html', employe=employe, events=events, mois=mois, annee=annee)

# --- LANCEMENT DE L'APPLICATION ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # On vérifie si la base de données est vide avant de la remplir
        if not Categorie.query.first():
            seed_data()

    # Mode développement
    print("Serveur de développement lancé sur http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

@app.route('/api/events_employe')
def api_events_employe():
    from datetime import timedelta
    employe_id = request.args.get('employe_id')
    if not employe_id:
        return jsonify([])
    employe = Employe.query.get(employe_id)
    if not employe:
        return jsonify([])
    presences = PresenceEmploye.query.filter_by(employe_id=employe_id, present=True).all()
    conges = CongeEmploye.query.filter_by(employe_id=employe_id).all()
    events = []
    for p in presences:
        events.append({
            'title': 'Présent',
            'start': p.date.strftime('%Y-%m-%d'),
            'end': p.date.strftime('%Y-%m-%d'),
            'color': employe.couleur or '#48c774',
            'allDay': True
        })
    for c in conges:
        events.append({
            'title': c.motif or 'Congé',
            'start': c.date_debut.strftime('%Y-%m-%d'),
            'end': (c.date_fin + timedelta(days=1)).strftime('%Y-%m-%d'),
            'color': '#f14668',
            'allDay': True
        })
    return jsonify(events)

@app.route('/planning-employe', endpoint='planning_employe')
def planning_employe():
    # Récupérer tous les employés
    employes = Employe.query.all()
    # Récupérer toutes les présences
    presences = PresenceEmploye.query.filter_by(present=True).all()
    # Récupérer tous les congés
    conges = CongeEmploye.query.all()

    events = []
    # Ajouter les présences (un jour = un event)
    for presence in presences:
        events.append({
            'title': f"Présent - {presence.employe.nom}",
            'start': presence.date.strftime('%Y-%m-%d'),
            'end': presence.date.strftime('%Y-%m-%d'),
            'color': presence.employe.couleur or '#7ed957',
            'allDay': True,
            'type': 'presence',
            'employe': presence.employe.nom
        })
    # Ajouter les congés (période = event)
    for conge in conges:
        events.append({
            'title': f"Congé - {conge.employe.nom}",
            'start': conge.date_debut.strftime('%Y-%m-%d'),
            'end': (conge.date_fin + timedelta(days=1)).strftime('%Y-%m-%d'),  # FullCalendar exclut le dernier jour
            'color': '#ff7675',
            'allDay': True,
            'type': 'conge',
            'employe': conge.employe.nom
        })
        return render_template('planning_employe.html', events=events)

@app.route('/planning/retouches')
def planning_retouches_mensuel():
    return render_template('planning_retouches_mensuel.html')

@app.route('/api/retouche_events')
def api_retouche_events():
    # 1. On regroupe toutes les retouches par client et par date
    grouped_retouches = defaultdict(list)
    all_retouches = Retouche.query.order_by(Retouche.id).all()
    for r in all_retouches:
        if r.date_echeance and r.client:
            grouped_retouches[(r.date_echeance, r.client)].append(r)

    # 2. On crée un événement de calendrier unique pour chaque groupe
    events = []
    for (date, client), retouches_list in grouped_retouches.items():
        # On compte les types de retouches pour faire un résumé
        summary_counter = Counter(
            r.detail.nom for r in retouches_list if r.detail
        )
        # On transforme ce résumé en une liste de textes
        summary_text_list = [f"{count} x {name}" for name, count in summary_counter.items()]
        # On vérifie si TOUTES les retouches du lot sont terminées
        is_all_terminated = all(r.statut == 'Terminée' for r in retouches_list)
        events.append({
            'title': client.nom,
            'start': date.strftime('%Y-%m-%d'),
            'url': url_for('detail_retouche', id=retouches_list[0].id),
            'className': 'tache-terminee' if is_all_terminated else '',
            'extendedProps': {
                'summary': summary_text_list
            }
        })
    return jsonify(events)


# Nouvelle route pour réimprimer le ticket d'une retouche
@app.route('/ticket/<int:retouche_id>/reimprimer')
def reimprimer_ticket(retouche_id):
    retouche = Retouche.query.get_or_404(retouche_id)
    client = retouche.client
    total_ht = retouche.prix or 0.0
    tva_rate = app.config.get('TVA_RATE', 0.2)
    montant_tva = total_ht * tva_rate
    total_ttc = total_ht + montant_tva
    now = datetime.now()
    date_formatee = format_date(now, format='full', locale='fr_FR')
    return render_template(
        'ticket.html',
        client=client,
        retouches=[retouche],
        total_ht=total_ht,
        montant_tva=montant_tva,
        total_ttc=total_ttc,
        tva_rate=tva_rate,
        numero_ticket=retouche.id,
        now=now,
        date_formatee=date_formatee
    )

@app.route('/api/shifts_events')
def api_shifts_events():
    shifts = PlanningShift.query.all()
    events = []
    for shift in shifts:
        employe = Employe.query.get(shift.employe_id)
        events.append({
            'title': shift.tache or 'Événement',
            'start': f"{shift.date}T{shift.heure_debut}",
            'end': f"{shift.date}T{shift.heure_fin}",
            'color': employe.couleur if employe and employe.couleur else '#a18aff'
        })
    return jsonify(events)

@app.route('/retouche/<int:id>/supprimer', methods=['POST'])
def supprimer_retouche(id):
    retouche = Retouche.query.get_or_404(id)
    db.session.delete(retouche)
    db.session.commit()
    flash('La retouche a bien été supprimée.', 'success')
    return redirect(url_for('planning_retouches_mensuel'))
