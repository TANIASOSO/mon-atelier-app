# 🚀 Déploiement sur Railway

## Étapes de déploiement :

### 1. Préparer le code
- ✅ Tous les fichiers sont prêts
- ✅ requirements.txt configuré
- ✅ Procfile créé
- ✅ railway.json configuré

### 2. Créer un compte Railway
1. Allez sur https://railway.app
2. Connectez-vous avec GitHub
3. Cliquez sur "New Project"

### 3. Déployer depuis GitHub
1. **Option A - Via GitHub (recommandée) :**
   - Poussez votre code sur GitHub
   - Dans Railway : "Deploy from GitHub repo"
   - Sélectionnez votre repository

2. **Option B - Via CLI :**
   ```bash
   npm install -g @railway/cli
   railway login
   railway init
   railway up
   ```

### 4. Configuration des variables d'environnement
Dans le dashboard Railway, ajoutez :
- `SECRET_KEY` : Générez une clef sécurisée
- `FLASK_ENV` : production

### 5. Base de données (optionnel)
Si vous voulez une base PostgreSQL :
- Dans Railway : "New" → "Database" → "PostgreSQL"
- Railway configurera automatiquement DATABASE_URL

### 6. Domaine personnalisé (optionnel)
- Dans Settings → Domains
- Ajoutez votre domaine personnalisé

## 🔧 Commandes utiles Railway CLI :
```bash
railway status          # Voir le statut
railway logs            # Voir les logs
railway open            # Ouvrir l'app
railway variables       # Gérer les variables
```

## 🐛 Dépannage :
- Vérifiez les logs avec `railway logs`
- Assurez-vous que Gunicorn est installé
- Vérifiez les variables d'environnement

## 💡 Avantages Railway :
- Déploiement automatique depuis GitHub
- Base de données PostgreSQL gratuite
- SSL automatique
- Domaines personnalisés
- Scaling automatique