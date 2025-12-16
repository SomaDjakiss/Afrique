import streamlit as st
from streamlit_javascript import st_javascript
import pymongo
from pymongo import MongoClient
import uuid
import random
import pandas as pd
import os
import altair as alt
from textblob import TextBlob
import numpy as np
from datetime import datetime, timedelta
import time
from PIL import Image
import base64
from itertools import combinations

# 🛠️ Configuration de la page
st.set_page_config(
    page_title="Wiki Survey - Afrique",
    layout="wide",
    page_icon="🗳️",
    initial_sidebar_state="collapsed"
)

# === Configuration MongoDB ===
#MONGO_URI = "mongodb://localhost:27017/"
MONGO_URI = "mongodb://mongo:JiwSbeZEXWiILqHARYsOnvkCOenDSKoY@shuttle.proxy.rlwy.net:28806"
DB_NAME = "Africas"

# --- Connexion à MongoDB ---
@st.cache_resource
def get_db_connection():
    """Obtenir une connexion à MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        return db
    except Exception as e:
        st.error(f"Erreur de connexion à MongoDB: {e}")
        return None

# === Création des collections et index ===
def init_database():
    """Initialiser la structure de la base MongoDB"""
    try:
        db = get_db_connection()

        # Créer les collections si elles n'existent pas
        collections = [
            "navigateur", "login", "question",
            "idees", "vote", "commentaire",
            "profil", "sentiment_analytics"
        ]

        for collection in collections:
            if collection not in db.list_collection_names():
                db.create_collection(collection)

        # Créer les index
        db.login.create_index("email", unique=True)
        db.idees.create_index("id_question")
        db.vote.create_index([("id_navigateur", 1), ("id_question", 1)])
        db.profil.create_index("id_navigateur", unique=True)
        db.sentiment_analytics.create_index("id_question", unique=True)

        # Insérer des données de test
        db.login.update_one(
            {"email": "admin@test.com"},
            {"$set": {
                "email": "admin@test.com",
                "mot_de_passe": "admin123",
                "date_creation": datetime.now()
            }},
            upsert=True
        )
        
        # Utilisateur avec droit d'image
        db.login.update_one(
            {"email": "yinnaasome@gmail.com"},
            {"$set": {
                "email": "yinnaasome@gmail.com",
                "mot_de_passe": "abc",
                "date_creation": datetime.now()
            }},
            upsert=True
        )

        print("✅ Base MongoDB initialisée avec succès")
        return True

    except Exception as e:
        print(f"❌ Erreur initialisation MongoDB: {e}")
        return False

# === Analyse de sentiment ===
def analyze_sentiment(text):
    """Analyser le sentiment d'un texte avec TextBlob"""
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity

        if polarity > 0.1:
            label = "Positif"
        elif polarity < -0.1:
            label = "Négatif"
        else:
            label = "Neutre"

        return polarity, label
    except:
        return 0.0, "Neutre"

def update_sentiment_analytics(question_id):
    """Mettre à jour les analytics de sentiment pour une question"""
    try:
        db = get_db_connection()

        # Calculer les stats pour les idées
        idees_stats_cursor = db.idees.aggregate([
            {"$match": {"id_question": question_id}},
            {"$group": {
                "_id": None,
                "avg_sentiment": {"$avg": "$sentiment_score"},
                "positifs": {"$sum": {"$cond": [{"$eq": ["$sentiment_label", "Positif"]}, 1, 0]}},
                "negatifs": {"$sum": {"$cond": [{"$eq": ["$sentiment_label", "Négatif"]}, 1, 0]}},
                "neutres": {"$sum": {"$cond": [{"$eq": ["$sentiment_label", "Neutre"]}, 1, 0]}}
            }}
        ])
        idees_stats = next(idees_stats_cursor, {})

        # Calculer les stats pour les commentaires
        commentaires_stats_cursor = db.commentaire.aggregate([
            {"$match": {"id_question": question_id}},
            {"$group": {
                "_id": None,
                "avg_sentiment": {"$avg": "$sentiment_score"},
                "positifs": {"$sum": {"$cond": [{"$eq": ["$sentiment_label", "Positif"]}, 1, 0]}},
                "negatifs": {"$sum": {"$cond": [{"$eq": ["$sentiment_label", "Négatif"]}, 1, 0]}},
                "neutres": {"$sum": {"$cond": [{"$eq": ["$sentiment_label", "Neutre"]}, 1, 0]}}
            }}
        ])
        commentaires_stats = next(commentaires_stats_cursor, {})

        # Insérer ou mettre à jour les analytics
        db.sentiment_analytics.update_one(
            {"id_question": question_id},
            {"$set": {
                "moyenne_sentiment_idees": idees_stats.get("avg_sentiment", 0),
                "moyenne_sentiment_commentaires": commentaires_stats.get("avg_sentiment", 0),
                "total_idees_positives": idees_stats.get("positifs", 0),
                "total_idees_negatives": idees_stats.get("negatifs", 0),
                "total_idees_neutres": idees_stats.get("neutres", 0),
                "total_commentaires_positifs": commentaires_stats.get("positifs", 0),
                "total_commentaires_negatifs": commentaires_stats.get("negatifs", 0),
                "total_commentaires_neutres": commentaires_stats.get("neutres", 0),
                "derniere_mise_a_jour": datetime.now()
            }},
            upsert=True
        )

    except Exception as e:
        st.error(f"Erreur mise à jour analytics: {e}")

# Initialisation de la base
if not init_database():
    st.error("❌ Erreur initialisation MongoDB")
    st.stop()

# Initialiser les clés nécessaires dans session_state
if "page" not in st.session_state:
    st.session_state["page"] = "home"

if "id_navigateur" not in st.session_state:
    st.session_state["id_navigateur"] = None

if "auth" not in st.session_state:
    st.session_state.auth = False

if "utilisateur_id" not in st.session_state:
    st.session_state.utilisateur_id = None

if "email" not in st.session_state:
    st.session_state.email = None

if "current_tab" not in st.session_state:
    st.session_state.current_tab = "home"

# --- ID navigateur ---
def get_navigateur_id():
    js_code = """
        const existing = localStorage.getItem("id_navigateur");
        if (existing) {
            existing;
        } else {
            const newId = crypto.randomUUID();
            localStorage.setItem("id_navigateur", newId);
            newId;
        }
    """
    return st_javascript(js_code)

def detect_navigateur():
    js_code = "navigator.userAgent;"
    agent = st_javascript(js_code)
    if agent:
        if "Chrome" in agent and "Edg" not in agent:
            return "Chrome"
        elif "Firefox" in agent:
            return "Firefox"
        elif "Edg" in agent:
            return "Edge"
        elif "Safari" in agent and "Chrome" not in agent:
            return "Safari"
    return "Inconnu"

def init_navigateur():
    if not st.session_state["id_navigateur"]:
        id_navigateur = get_navigateur_id()
        if id_navigateur and len(id_navigateur) > 100:
            id_navigateur = id_navigateur[:100]
        navigateur_nom = detect_navigateur()
        if id_navigateur:
            st.session_state["id_navigateur"] = id_navigateur
            db = get_db_connection()
            db.navigateur.update_one(
                {"id_navigateur": id_navigateur},
                {"$set": {
                    "id_navigateur": id_navigateur,
                    "navigateur": navigateur_nom,
                    "date_creation": datetime.now()
                }},
                upsert=True
            )

# Appel obligatoire
init_navigateur()

# =============================================================
# === FONCTIONS D'AUTHENTIFICATION ===
# =============================================================

def creer_compte():
    """Page de création de compte pour les nouveaux utilisateurs."""
    st.subheader("Créez votre compte pour proposer une question")
    db = get_db_connection()

    email_reg = st.text_input("Email", key="email_reg")
    mot_de_passe_reg = st.text_input("Mot de passe", type="password", key="pass_reg")
    mot_de_passe_conf = st.text_input("Confirmer le mot de passe", type="password", key="pass_conf")

    if st.button("Créer le compte", key="btn_creer_compte"):
        if not email_reg or not mot_de_passe_reg or not mot_de_passe_conf:
            st.error("Veuillez remplir tous les champs.")
            return

        if mot_de_passe_reg != mot_de_passe_conf:
            st.error("Les mots de passe ne correspondent pas.")
            return

        # Vérifier si l'email existe déjà
        if db.login.find_one({"email": email_reg}):
            st.error("Cet email est déjà utilisé. Veuillez vous connecter.")
            return

        # Enregistrer le nouvel utilisateur
        nouvel_utilisateur = {
            "email": email_reg,
            "mot_de_passe": mot_de_passe_reg,
            "date_creation": datetime.now()
        }
        user_id = db.login.insert_one(nouvel_utilisateur).inserted_id

        # Connexion automatique après la création
        st.session_state.auth = True
        st.session_state.utilisateur_id = str(user_id)
        st.session_state.email = email_reg
        st.success(f"✅ Compte créé et connexion réussie ! Bienvenue {st.session_state.email} !")
        time.sleep(1)
        st.rerun()

def login_page():
    """Interface de connexion pour les utilisateurs existants."""
    st.subheader("Connectez-vous pour proposer une question")
    db = get_db_connection()
    email = st.text_input("Email", key="email_login")
    mot_de_passe = st.text_input("Mot de passe", type="password", key="pass_login")

    if st.button("Se connecter", key="btn_login"):
        utilisateur = db.login.find_one({
            "email": email,
            "mot_de_passe": mot_de_passe
        })

        if utilisateur:
            st.session_state.auth = True
            st.session_state.utilisateur_id = str(utilisateur["_id"])
            st.session_state.email = utilisateur["email"]
            st.success(f"✅ Bienvenue {st.session_state.email} !")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Identifiants incorrects")

def authentication_flow():
    """Gère la connexion et la création de compte via des onglets"""
    tab_login, tab_register = st.tabs(["🔒 Se connecter", "✍️ Créer un compte"])

    with tab_login:
        login_page()

    with tab_register:
        creer_compte()

# =============================================================
# === FONCTIONS PRINCIPALES  ===
# =============================================================

def creer_question():
    st.header("✍️ Créer une nouvelle question")

    # Vérifier si l'utilisateur est connecté
    if not st.session_state.get("auth"):
        st.info("Veuillez vous connecter ou créer un compte pour proposer une question.")
        authentication_flow()
        return

    with st.form("form_question"):
        question = st.text_input("Votre question :", 
                               placeholder="Ex: Quelle est la priorité pour le développement de l'Afrique ?")
        idee1 = st.text_input("Idée 1 :", 
                            placeholder="Ex: Éducation gratuite pour tous")
        idee2 = st.text_input("Idée 2 :", 
                            placeholder="Ex: Monnaie unique africaine")
        
        submitted = st.form_submit_button("Créer la question")

        if submitted:
            if not question.strip():
                st.error("Veuillez saisir une question.")
                return
            if not idee1.strip() or not idee2.strip():
                st.error("Veuillez saisir deux idées pour la question.")
                return

            db = get_db_connection()

            # Insérer la question
            question_data = {
                "question": question.strip(),
                "createur_id": st.session_state.utilisateur_id,
                "createur_email": st.session_state.email,
                "date_creation": datetime.now()
            }
            question_id = db.question.insert_one(question_data).inserted_id

            # Analyser sentiment des idées
            score1, label1 = analyze_sentiment(idee1)
            score2, label2 = analyze_sentiment(idee2)

            # Insérer les idées
            db.idees.insert_many([
                {
                    "id_question": question_id,
                    "idee_texte": idee1.strip(),
                    "creer_par_utilisateur": "non",
                    "date_creation": datetime.now(),
                    "sentiment_score": float(score1),
                    "sentiment_label": label1
                },
                {
                    "id_question": question_id,
                    "idee_texte": idee2.strip(),
                    "creer_par_utilisateur": "non",
                    "date_creation": datetime.now(),
                    "sentiment_score": float(score2),
                    "sentiment_label": label2
                }
            ])

            # Mettre à jour les analytics
            update_sentiment_analytics(question_id)

            st.success("✅ Question et idées enregistrées avec succès !")
            st.balloons()
            time.sleep(2)
            st.rerun()

def get_vote_pairs(question_id, id_navigateur):
    """Obtenir toutes les paires d'idées non votées pour une question"""
    db = get_db_connection()
    
    # Récupérer toutes les idées pour cette question
    all_ideas = list(db.idees.find(
        {"id_question": question_id}, 
        {"_id": 1, "idee_texte": 1, "creer_par_utilisateur": 1}
    ))
    
    if len(all_ideas) < 2:
        return []
    
    # Générer toutes les combinaisons possibles de paires
    all_pairs = list(combinations(all_ideas, 2))
    
    # Récupérer les paires déjà votées par cet utilisateur
    user_votes = list(db.vote.find(
        {
            "id_navigateur": id_navigateur,
            "id_question": question_id
        },
        {"id_idee_gagnant": 1, "id_idee_perdant": 1}
    ))
    
    # Convertir en ensemble de tuples (id1, id2) pour comparaison rapide
    voted_pairs = set()
    for vote in user_votes:
        pair = tuple(sorted([vote["id_idee_gagnant"], vote["id_idee_perdant"]]))
        voted_pairs.add(pair)
    
    # Filtrer les paires non votées
    available_pairs = []
    for idea1, idea2 in all_pairs:
        pair_ids = tuple(sorted([idea1["_id"], idea2["_id"]]))
        if pair_ids not in voted_pairs:
            available_pairs.append((idea1, idea2))
    
    return available_pairs

def participer():
    """Interface de participation au vote avec logique Salganik corrigée"""
    st.header("🗳️ Participer aux votes")
    
    db = get_db_connection()

    # Récupérer toutes les questions
    all_questions = list(db.question.find({}, {"_id": 1, "question": 1, "date_creation": 1}).sort("date_creation", -1))

    if not all_questions:
        st.info("Aucune question disponible pour le moment.")
        return

    # Vérifier quelles questions ont encore des paires non votées
    questions_with_available_pairs = []
    for question in all_questions:
        available_pairs = get_vote_pairs(question["_id"], st.session_state.id_navigateur)
        if available_pairs:
            questions_with_available_pairs.append({
                "question": question,
                "available_pairs": len(available_pairs)
            })

    if not questions_with_available_pairs:
        st.success("🎉 Vous avez voté sur toutes les paires disponibles !")
        st.info("💡 De nouvelles idées ou questions apparaîtront ici lorsqu'elles seront créées.")
        afficher_formulaire_profil()
        return

    # Initialiser les variables de session pour cette page
    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0
    
    if 'current_pair_index' not in st.session_state:
        st.session_state.current_pair_index = 0
    
    if 'current_question_id' not in st.session_state:
        st.session_state.current_question_id = questions_with_available_pairs[0]["question"]["_id"]

    # Sélection de la question
    selected_question = None
    selected_question_data = None
    
    for i, q_data in enumerate(questions_with_available_pairs):
        if q_data["question"]["_id"] == st.session_state.current_question_id:
            selected_question = q_data["question"]
            selected_question_data = q_data
            st.session_state.current_question_index = i
            break
    
    if not selected_question:
        selected_question_data = questions_with_available_pairs[0]
        selected_question = selected_question_data["question"]
        st.session_state.current_question_id = selected_question["_id"]
        st.session_state.current_question_index = 0

    # Navigation entre questions
    if len(questions_with_available_pairs) > 1:
        col_nav = st.columns([2, 5, 2])
        with col_nav[0]:
            if st.button("◀️ Question précédente", 
                        disabled=st.session_state.current_question_index == 0, 
                        use_container_width=True,
                        key=f"btn_prev_question_{st.session_state.current_question_index}"):
                new_index = max(0, st.session_state.current_question_index - 1)
                st.session_state.current_question_index = new_index
                st.session_state.current_question_id = questions_with_available_pairs[new_index]["question"]["_id"]
                st.session_state.current_pair_index = 0
                st.rerun()
        
        with col_nav[1]:
            question_progress = (st.session_state.current_question_index + 1) / len(questions_with_available_pairs)
            st.info(f"Question {st.session_state.current_question_index + 1} sur {len(questions_with_available_pairs)}")
        
        with col_nav[2]:
            if st.button("Question suivante ▶️", 
                        disabled=st.session_state.current_question_index >= len(questions_with_available_pairs) - 1, 
                        use_container_width=True,
                        key=f"btn_next_question_{st.session_state.current_question_index}"):
                new_index = min(len(questions_with_available_pairs) - 1, st.session_state.current_question_index + 1)
                st.session_state.current_question_index = new_index
                st.session_state.current_question_id = questions_with_available_pairs[new_index]["question"]["_id"]
                st.session_state.current_pair_index = 0
                st.rerun()

    # Affichage de la question
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 1.5rem; border-radius: 10px; color: white; margin: 1rem 0;'>
        <h3 style='color: white; margin: 0;'>❓ {selected_question['question']}</h3>
    </div>
    """, unsafe_allow_html=True)

    question_id = selected_question["_id"]
    
    # Obtenir les paires disponibles pour cette question
    available_pairs = get_vote_pairs(question_id, st.session_state.id_navigateur)
    
    if not available_pairs:
        st.info("Vous avez voté sur toutes les paires pour cette question.")
        st.session_state.current_question_index += 1
        if st.session_state.current_question_index < len(questions_with_available_pairs):
            st.session_state.current_question_id = questions_with_available_pairs[st.session_state.current_question_index]["question"]["_id"]
            st.rerun()
        return
    
    # S'assurer que current_pair_index est valide
    if st.session_state.current_pair_index >= len(available_pairs):
        st.session_state.current_pair_index = 0
    
    # Sélectionner la paire actuelle
    current_pair = available_pairs[st.session_state.current_pair_index]
    idea1, idea2 = current_pair
    
    # Navigation entre paires
    if len(available_pairs) > 1:
        pair_cols = st.columns([1, 3, 1])
        with pair_cols[0]:
            if st.button("◀️ Paire précédente", 
                        disabled=st.session_state.current_pair_index == 0, 
                        use_container_width=True,
                        key=f"btn_prev_pair_{st.session_state.current_pair_index}"):
                st.session_state.current_pair_index = max(0, st.session_state.current_pair_index - 1)
                st.rerun()
        
        with pair_cols[1]:
            progress_value = (st.session_state.current_pair_index + 1) / len(available_pairs)
            # S'assurer que progress_value est entre 0 et 1
            progress_value = max(0.0, min(1.0, progress_value))
            st.progress(progress_value)
            st.caption(f"Paire {st.session_state.current_pair_index + 1} sur {len(available_pairs)}")
        
        with pair_cols[2]:
            if st.button("Paire suivante ▶️", 
                        disabled=st.session_state.current_pair_index >= len(available_pairs) - 1, 
                        use_container_width=True,
                        key=f"btn_next_pair_{st.session_state.current_pair_index}"):
                st.session_state.current_pair_index = min(len(available_pairs) - 1, st.session_state.current_pair_index + 1)
                st.rerun()

    # Affichage des deux idées pour le vote
    st.markdown("### 🤔 Quelle idée préférez-vous ?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style='border: 2px solid #4CAF50; border-radius: 10px; padding: 1.5rem; 
                    height: 100%; background-color: rgba(76, 175, 80, 0.1);'>
        """, unsafe_allow_html=True)
        st.markdown(f"#### 💡 Option A")
        
        # Afficher le type d'idée
        type_a = "Idée téléchargée" if idea1.get("creer_par_utilisateur") == "oui" else "Idée originale"
        st.caption(f"Type: {type_a}")
        
        st.markdown(f"**{idea1['idee_texte']}**")
        
        if st.button("✅ Choisir cette idée", 
                    key=f"vote_{question_id}_{str(idea1['_id'])[:10]}_{str(idea2['_id'])[:10]}_a", 
                    use_container_width=True, 
                    type="primary"):
            # Enregistrer le vote
            enregistrer_vote(idea1['_id'], idea2['_id'], question_id)
            
            # Passer à la paire suivante
            if st.session_state.current_pair_index < len(available_pairs) - 1:
                st.session_state.current_pair_index += 1
            else:
                # Si c'était la dernière paire, passer à la question suivante
                st.session_state.current_pair_index = 0
                st.session_state.current_question_index += 1
                if st.session_state.current_question_index < len(questions_with_available_pairs):
                    st.session_state.current_question_id = questions_with_available_pairs[st.session_state.current_question_index]["question"]["_id"]
            
            st.success("✅ Vote enregistré !")
            time.sleep(0.5)
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='border: 2px solid #2196F3; border-radius: 10px; padding: 1.5rem; 
                    height: 100%; background-color: rgba(33, 150, 243, 0.1);'>
        """, unsafe_allow_html=True)
        st.markdown(f"#### 💡 Option B")
        
        # Afficher le type d'idée
        type_b = "Idée téléchargée" if idea2.get("creer_par_utilisateur") == "oui" else "Idée originale"
        st.caption(f"Type: {type_b}")
        
        st.markdown(f"**{idea2['idee_texte']}**")
        
        if st.button("✅ Choisir cette idée", 
                    key=f"vote_{question_id}_{str(idea1['_id'])[:10]}_{str(idea2['_id'])[:10]}_b", 
                    use_container_width=True, 
                    type="primary"):
            # Enregistrer le vote
            enregistrer_vote(idea2['_id'], idea1['_id'], question_id)
            
            # Passer à la paire suivante
            if st.session_state.current_pair_index < len(available_pairs) - 1:
                st.session_state.current_pair_index += 1
            else:
                # Si c'était la dernière paire, passer à la question suivante
                st.session_state.current_pair_index = 0
                st.session_state.current_question_index += 1
                if st.session_state.current_question_index < len(questions_with_available_pairs):
                    st.session_state.current_question_id = questions_with_available_pairs[st.session_state.current_question_index]["question"]["_id"]
            
            st.success("✅ Vote enregistré !")
            time.sleep(0.5)
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)

    # Bouton "Les deux se valent"
    col_center = st.columns([1, 2, 1])
    with col_center[1]:
        if st.button("🤷 Les deux se valent", 
                    use_container_width=True,
                    key=f"egalite_{question_id}_{str(idea1['_id'])[:10]}_{str(idea2['_id'])[:10]}"):
            # Enregistrer un vote d'égalité (on peut choisir arbitrairement un gagnant)
            enregistrer_vote(idea1['_id'], idea2['_id'], question_id)
            
            # Passer à la paire suivante
            if st.session_state.current_pair_index < len(available_pairs) - 1:
                st.session_state.current_pair_index += 1
            else:
                # Si c'était la dernière paire, passer à la question suivante
                st.session_state.current_pair_index = 0
                st.session_state.current_question_index += 1
                if st.session_state.current_question_index < len(questions_with_available_pairs):
                    st.session_state.current_question_id = questions_with_available_pairs[st.session_state.current_question_index]["question"]["_id"]
            
            st.info("Vote d'égalité enregistré - nouvelle paire d'idées")
            time.sleep(0.5)
            st.rerun()

    # Section pour soumettre une nouvelle idée
    st.markdown("---")
    with st.expander("💡 Proposer une nouvelle idée pour cette question", expanded=False):
        st.info("""
        **Note importante :** Si vous soumettez une nouvelle idée :
        1. Elle sera ajoutée comme idée supplémentaire pour cette question
        2. Elle sera comparée avec toutes les autres idées existantes
        3. Vous pourrez continuer à voter normalement
        """)
        
        nouvelle_idee = st.text_area("Votre nouvelle idée :", height=100,
                                    placeholder="Proposez une idée innovante pour cette question...")
        
        if st.button("➕ Soumettre cette nouvelle idée", 
                    use_container_width=True,
                    key=f"btn_nouvelle_idee_{question_id}"):
            if nouvelle_idee.strip():
                # Analyser le sentiment
                score, label = analyze_sentiment(nouvelle_idee)
                
                # Insérer la nouvelle idée
                new_idea_id = db.idees.insert_one({
                    "id_question": question_id,
                    "id_navigateur": st.session_state.id_navigateur,
                    "idee_texte": nouvelle_idee.strip(),
                    "creer_par_utilisateur": "oui",
                    "date_creation": datetime.now(),
                    "sentiment_score": float(score),
                    "sentiment_label": label
                }).inserted_id
                
                # Mettre à jour analytics
                update_sentiment_analytics(question_id)
                
                st.success("✅ Votre idée a été ajoutée avec succès !")
                st.info("Cette idée sera maintenant incluse dans les comparaisons avec les autres idées.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Veuillez saisir une idée valide.")

    # Section pour ajouter un commentaire
    st.markdown("---")
    with st.expander("💬 Ajouter un commentaire sur cette question", expanded=False):
        st.info("Les commentaires vous permettent d'exprimer votre opinion sans participer au vote.")
        
        commentaire = st.text_area("Votre commentaire :", height=100,
                                  placeholder="Exprimez votre opinion sur cette question...")
        
        if st.button("📝 Ajouter ce commentaire", 
                    use_container_width=True,
                    key=f"btn_commentaire_{question_id}"):
            if commentaire.strip():
                # Analyser le sentiment
                score, label = analyze_sentiment(commentaire)
                
                # Insérer le commentaire
                db.commentaire.insert_one({
                    "id_navigateur": st.session_state.id_navigateur,
                    "id_question": question_id,
                    "commentaire": commentaire.strip(),
                    "date_creation": datetime.now(),
                    "sentiment_score": float(score),
                    "sentiment_label": label
                })
                
                # Mettre à jour analytics
                update_sentiment_analytics(question_id)
                
                st.success("✅ Commentaire ajouté avec succès !")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Veuillez saisir un commentaire valide.")

def enregistrer_vote(gagnant, perdant, question_id):
    """Enregistrer un vote dans la base de données"""
    db = get_db_connection()

    # Enregistrer le vote
    db.vote.insert_one({
        "id_navigateur": st.session_state.id_navigateur,
        "id_question": question_id,
        "id_idee_gagnant": gagnant,
        "id_idee_perdant": perdant,
        "date_vote": datetime.now()
    })

    # Mettre à jour les analytics
    update_sentiment_analytics(question_id)

def afficher_formulaire_profil():
    """Formulaire de profil utilisateur"""
    db = get_db_connection()

    if db.profil.find_one({"id_navigateur": st.session_state.id_navigateur}):
        return

    with st.expander("📝 Informations démographiques (optionnel)", expanded=False):
        st.info("Ces informations nous aident à mieux comprendre notre communauté. Tous les champs sont optionnels.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            pays = st.text_input("Pays de résidence", placeholder="Ex: Sénégal")
            age = st.number_input("Âge", min_value=10, max_value=120, value=25)
        
        with col2:
            sexe = st.selectbox("Genre", ["", "Homme", "Femme", "Autre", "Je préfère ne pas répondre"])
            fonction = st.text_input("Profession/Fonction", placeholder="Ex: Étudiant, Enseignant, Entrepreneur")
        
        if st.button("Enregistrer mes informations", 
                    use_container_width=True,
                    key="btn_enregistrer_profil"):
            db.profil.insert_one({
                "id_navigateur": st.session_state.id_navigateur,
                "pays": pays if pays else None,
                "age": age if age else None,
                "sexe": sexe if sexe else None,
                "fonction": fonction if fonction else None,
                "date_creation": datetime.now()
            })
            st.success("✅ Merci ! Vos informations ont été enregistrées.")
            time.sleep(1)
            st.rerun()

# =============================================================
# === VISUALISATIONS DE DONNÉES AMÉLIORÉES ===
# =============================================================

def afficher_visualisations():
    """Dashboard complet de visualisations de données"""
    st.title("📊 Visualisations de données")
    
    db = get_db_connection()
    
    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_questions = db.question.count_documents({})
        st.metric("📝 Questions", total_questions)
    
    with col2:
        total_votes = db.vote.count_documents({})
        st.metric("🗳️ Votes", total_votes)
    
    with col3:
        total_idees = db.idees.count_documents({})
        st.metric("💡 Idées", total_idees)
    
    with col4:
        total_users = db.navigateur.count_documents({})
        st.metric("👥 Participants", total_users)
    
    st.markdown("---")
    
    # Section avec graphiques expansibles
    st.markdown("### 📈 Graphiques interactifs")
    
    # Graphique 1: Idées téléchargées vs originales
    with st.expander("📊 Comparaison des idées téléchargées avec les idées originales", expanded=True):
        st.markdown("""
        **Description :** Ce graphique compare le nombre d'idées soumises par les utilisateurs 
        (téléchargées) avec les idées originales proposées lors de la création des questions.
        """)
        
        # Compter les idées par type
        pipeline_idees = [
            {"$group": {
                "_id": "$creer_par_utilisateur",
                "count": {"$sum": 1}
            }}
        ]
        
        resultats_idees = list(db.idees.aggregate(pipeline_idees))
        
        if resultats_idees:
            # Préparer les données
            data = []
            for result in resultats_idees:
                type_idee = "Idées téléchargées" if result["_id"] == "oui" else "Idées originales"
                total = sum(r["count"] for r in resultats_idees)
                pourcentage = (result["count"] / total) * 100 if total > 0 else 0
                data.append({
                    "Type": type_idee,
                    "Nombre": result["count"],
                    "Pourcentage": pourcentage
                })
            
            df_idees = pd.DataFrame(data)
            
            # Créer un graphique en barres
            bars = alt.Chart(df_idees).mark_bar().encode(
                x=alt.X('Type:N', title='Type d\'idée'),
                y=alt.Y('Nombre:Q', title='Nombre d\'idées'),
                color=alt.Color('Type:N', 
                              scale=alt.Scale(domain=['Idées originales', 'Idées téléchargées'],
                                            range=['#4CAF50', '#2196F3'])),
                tooltip=['Type:N', 'Nombre:Q', alt.Tooltip('Pourcentage:Q', format='.1f')]
            ).properties(
                width=600,
                height=400,
                title="Répartition des idées par type"
            )
            
            # Ajouter les étiquettes de valeur
            text = bars.mark_text(
                align='center',
                baseline='bottom',
                dy=-5
            ).encode(
                text='Nombre:Q'
            )
            
            chart = bars + text
            st.altair_chart(chart, use_container_width=True)
            
            # Afficher un tableau détaillé
            st.dataframe(df_idees[['Type', 'Nombre', 'Pourcentage']].round(1), use_container_width=True)
        else:
            st.info("Aucune donnée disponible pour ce graphique.")
    
    # Graphique 2: Nombre de votes par jour
    with st.expander("📅 Nombre de votes par jour", expanded=False):
        st.markdown("""
        **Description :** Évolution du nombre de votes enregistrés chaque jour.
        Permet d'identifier les périodes d'activité intense.
        """)
        
        # Calculer la période (derniers 30 jours)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        pipeline_votes = [
            {"$match": {"date_vote": {"$gte": thirty_days_ago}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_vote"}},
                "votes": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        resultats_votes = list(db.vote.aggregate(pipeline_votes))
        
        if resultats_votes:
            # Créer un DataFrame
            dates = []
            vote_counts = []
            
            for result in resultats_votes:
                dates.append(result["_id"])
                vote_counts.append(result["votes"])
            
            df_votes = pd.DataFrame({
                'Date': pd.to_datetime(dates),
                'Votes': vote_counts
            })
            
            # Créer un graphique en ligne
            line_chart = alt.Chart(df_votes).mark_line(point=True, color='#FF9800').encode(
                x=alt.X('Date:T', title='Date'),
                y=alt.Y('Votes:Q', title='Nombre de votes'),
                tooltip=['Date:T', 'Votes:Q']
            ).properties(
                width=700,
                height=400,
                title="Évolution des votes par jour (30 derniers jours)"
            )
            
            # Ajouter une zone sous la ligne
            area = alt.Chart(df_votes).mark_area(color='#FF9800', opacity=0.3).encode(
                x='Date:T',
                y='Votes:Q'
            )
            
            chart = line_chart + area
            st.altair_chart(chart, use_container_width=True)
            
            # Statistiques
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                st.metric("📊 Votes max par jour", max(vote_counts))
            with col_stats2:
                avg_votes = np.mean(vote_counts)
                st.metric("📈 Moyenne quotidienne", f"{avg_votes:.1f}")
            with col_stats3:
                st.metric("📉 Total sur la période", sum(vote_counts))
        else:
            st.info("Aucun vote enregistré dans les 30 derniers jours.")
    
    # Graphique 3: Nombre de questions soumises par jour
    with st.expander("📝 Nombre de questions soumises par jour", expanded=False):
        st.markdown("""
        **Description :** Évolution du nombre de questions créées chaque jour.
        Montre l'engagement des utilisateurs à créer du contenu.
        """)
        
        pipeline_questions = [
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_creation"}},
                "questions": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        resultats_questions = list(db.question.aggregate(pipeline_questions))
        
        if resultats_questions:
            # Créer un DataFrame
            dates = []
            question_counts = []
            
            for result in resultats_questions:
                dates.append(result["_id"])
                question_counts.append(result["questions"])
            
            df_questions = pd.DataFrame({
                'Date': pd.to_datetime(dates),
                'Questions': question_counts
            })
            
            # Créer un graphique en barres
            bars = alt.Chart(df_questions).mark_bar(color='#9C27B0').encode(
                x=alt.X('Date:T', title='Date'),
                y=alt.Y('Questions:Q', title='Nombre de questions'),
                tooltip=['Date:T', 'Questions:Q']
            ).properties(
                width=700,
                height=400,
                title="Questions soumises par jour"
            )
            
            st.altair_chart(bars, use_container_width=True)
            
            # Calculer les statistiques
            total_questions = sum(question_counts)
            avg_daily = total_questions / len(question_counts) if len(question_counts) > 0 else 0
            max_daily = max(question_counts) if question_counts else 0
            
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                st.metric("📊 Total de questions", total_questions)
            with col_stats2:
                st.metric("📈 Moyenne quotidienne", f"{avg_daily:.2f}")
            with col_stats3:
                st.metric("🔥 Jour record", max_daily)
        else:
            st.info("Aucune question disponible pour l'analyse.")
    
    # Graphique 4: Analyse de sentiment approfondie
    with st.expander("😊 Analyse de sentiment approfondie", expanded=False):
        st.markdown("""
        **Description :** Analyse détaillée des sentiments dans les idées et commentaires.
        """)
        
        # Sentiment des idées
        pipeline_sentiment_idees = [
            {"$match": {"sentiment_label": {"$exists": True}}},
            {"$group": {
                "_id": {"$concat": ["Idées - ", "$sentiment_label"]},
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$sentiment_score"}
            }}
        ]
        
        # Sentiment des commentaires
        pipeline_sentiment_commentaires = [
            {"$match": {"sentiment_label": {"$exists": True}}},
            {"$group": {
                "_id": {"$concat": ["Commentaires - ", "$sentiment_label"]},
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$sentiment_score"}
            }}
        ]
        
        resultats_idees = list(db.idees.aggregate(pipeline_sentiment_idees))
        resultats_comms = list(db.commentaire.aggregate(pipeline_sentiment_commentaires))
        
        if resultats_idees or resultats_comms:
            # Combiner les résultats
            all_data = resultats_idees + resultats_comms
            
            # Préparer les données
            data = []
            for result in all_data:
                parts = result["_id"].split(" - ")
                categorie = parts[0]
                sentiment = parts[1]
                
                data.append({
                    "Catégorie": categorie,
                    "Sentiment": sentiment,
                    "Nombre": result["count"],
                    "Score moyen": result["avg_score"]
                })
            
            df_sentiment = pd.DataFrame(data)
            
            # Graphique en barres groupées
            bars = alt.Chart(df_sentiment).mark_bar().encode(
                x=alt.X('Catégorie:N', title=''),
                y=alt.Y('Nombre:Q', title='Nombre'),
                color=alt.Color('Sentiment:N',
                              scale=alt.Scale(domain=['Positif', 'Neutre', 'Négatif'],
                                            range=['#4CAF50', '#FF9800', '#F44336'])),
                column='Sentiment:N',
                tooltip=['Catégorie:N', 'Sentiment:N', 'Nombre:Q', alt.Tooltip('Score moyen:Q', format='.3f')]
            ).properties(
                width=150,
                height=300,
                title="Distribution des sentiments par catégorie"
            )
            
            st.altair_chart(bars, use_container_width=True)
            
            # Graphique de dispersion score vs nombre
            scatter = alt.Chart(df_sentiment).mark_circle(size=200).encode(
                x=alt.X('Score moyen:Q', title='Score moyen de sentiment', scale=alt.Scale(domain=[-1, 1])),
                y=alt.Y('Nombre:Q', title='Nombre d\'éléments'),
                color=alt.Color('Sentiment:N',
                              scale=alt.Scale(domain=['Positif', 'Neutre', 'Négatif'],
                                            range=['#4CAF50', '#FF9800', '#F44336'])),
                size='Nombre:Q',
                tooltip=['Catégorie:N', 'Sentiment:N', 'Nombre:Q', 'Score moyen:Q']
            ).properties(
                width=600,
                height=400,
                title="Relation entre score de sentiment et volume"
            )
            
            st.altair_chart(scatter, use_container_width=True)
            
            # Tableau détaillé
            st.dataframe(df_sentiment[['Catégorie', 'Sentiment', 'Nombre', 'Score moyen']].round(3), 
                        use_container_width=True)
        else:
            st.info("Aucune analyse de sentiment disponible.")
    
    # Graphique 5: Participation par pays
    with st.expander("🌍 Participation par pays", expanded=False):
        st.markdown("""
        **Description :** Répartition géographique des participants.
        """)
        
        pipeline_pays = [
            {"$match": {"pays": {"$exists": True, "$ne": ""}}},
            {"$group": {
                "_id": "$pays",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        resultats_pays = list(db.profil.aggregate(pipeline_pays))
        
        if resultats_pays:
            df_pays = pd.DataFrame(resultats_pays)
            df_pays.columns = ['Pays', 'Participants']
            
            # Calculer les pourcentages
            total = df_pays['Participants'].sum()
            df_pays['Pourcentage'] = (df_pays['Participants'] / total * 100).round(1)
            
            # Créer un graphique en barres horizontales
            bars = alt.Chart(df_pays).mark_bar().encode(
                y=alt.Y('Pays:N', sort='-x', title=''),
                x=alt.X('Participants:Q', title='Nombre de participants'),
                color=alt.Color('Pays:N', legend=None),
                tooltip=['Pays:N', 'Participants:Q', alt.Tooltip('Pourcentage:Q', format='.1f')]
            ).properties(
                width=600,
                height=400,
                title="Top 10 des pays participants"
            )
            
            st.altair_chart(bars, use_container_width=True)
            
            # Afficher le tableau
            st.dataframe(df_pays, use_container_width=True)
        else:
            st.info("Aucune donnée de pays disponible.")
    
    # Graphique 6: Distribution par âge
    with st.expander("👥 Distribution par âge", expanded=False):
        st.markdown("""
        **Description :** Répartition des participants par tranche d'âge.
        """)
        
        pipeline_age = [
            {"$match": {"age": {"$exists": True, "$ne": None}}},
            {"$bucket": {
                "groupBy": "$age",
                "boundaries": [10, 20, 30, 40, 50, 60, 70, 80],
                "default": "80+",
                "output": {
                    "count": {"$sum": 1}
                }
            }}
        ]
        
        resultats_age = list(db.profil.aggregate(pipeline_age))
        
        if resultats_age:
            # Préparer les données
            age_ranges = ['10-19', '20-29', '30-39', '40-49', '50-59', '60-69', '70-79', '80+']
            age_data = []
            
            for i, result in enumerate(resultats_age):
                if i < len(age_ranges):
                    age_data.append({
                        'Tranche d\'âge': age_ranges[i],
                        'Participants': result['count']
                    })
            
            df_age = pd.DataFrame(age_data)
            
            # Créer un graphique en barres
            bars = alt.Chart(df_age).mark_bar(color='#673AB7').encode(
                x=alt.X('Tranche d\'âge:N', title='Tranche d\'âge'),
                y=alt.Y('Participants:Q', title='Nombre de participants'),
                tooltip=['Tranche d\'âge:N', 'Participants:Q']
            ).properties(
                width=600,
                height=400,
                title="Répartition des participants par tranche d'âge"
            )
            
            st.altair_chart(bars, use_container_width=True)
            
            # Statistiques
            total_participants = df_age['Participants'].sum()
            if total_participants > 0:
                avg_age = sum([int(r.split('-')[0]) * d for r, d in zip(df_age['Tranche d\'âge'], df_age['Participants'])]) / total_participants
                st.metric("📊 Âge moyen estimé", f"{avg_age:.1f} ans")
        else:
            st.info("Aucune donnée d'âge disponible.")

# =============================================================
# === FONCTIONS D'ANALYSE ===
# =============================================================

def voir_resultats():
    """Affiche les résultats des votes par question"""
    st.title("📊 Résultats des votes")
    
    db = get_db_connection()
    
    # Récupérer toutes les questions
    questions = list(db.question.find({}, {"_id": 1, "question": 1}).sort("date_creation", -1))
    
    if not questions:
        st.info("Aucune question disponible pour le moment.")
        return
    
    # Sélecteur de question
    question_options = {f"{q['question'][:80]}..." if len(q['question']) > 80 else q['question']: q['_id'] 
                       for q in questions}
    
    selected_question_text = st.selectbox(
        "🔍 Sélectionnez une question pour voir ses résultats :",
        options=list(question_options.keys()),
        index=0,
        key="select_question_results"
    )
    
    selected_question_id = question_options[selected_question_text]
    
    # Récupérer la question complète
    selected_question = db.question.find_one({"_id": selected_question_id})
    
    if selected_question:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 1.5rem; border-radius: 10px; color: white; margin: 1rem 0;'>
            <h3 style='color: white; margin: 0;'>❓ {selected_question['question']}</h3>
        </div>
        """, unsafe_allow_html=True)
    
    # Pipeline pour les résultats
    pipeline = [
        {"$match": {"id_question": selected_question_id}},
        {"$lookup": {
            "from": "idees",
            "localField": "id_idee_gagnant",
            "foreignField": "_id",
            "as": "idee_gagnant"
        }},
        {"$lookup": {
            "from": "idees",
            "localField": "id_idee_perdant",
            "foreignField": "_id",
            "as": "idee_perdant"
        }},
        {"$unwind": "$idee_gagnant"},
        {"$unwind": "$idee_perdant"},
        {"$group": {
            "_id": "$idee_gagnant._id",
            "idee_texte": {"$first": "$idee_gagnant.idee_texte"},
            "victoires": {"$sum": 1},
            "sentiment_score": {"$first": "$idee_gagnant.sentiment_score"},
            "sentiment_label": {"$first": "$idee_gagnant.sentiment_label"},
            "creer_par_utilisateur": {"$first": "$idee_gagnant.creer_par_utilisateur"}
        }},
        {"$lookup": {
            "from": "vote",
            "let": {"idee_id": "$_id"},
            "pipeline": [
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$id_question", selected_question_id]},
                            {"$eq": ["$id_idee_perdant", "$$idee_id"]}
                        ]
                    }
                }}
            ],
            "as": "defaites_votes"
        }},
        {"$addFields": {
            "defaites": {"$size": "$defaites_votes"}
        }},
        {"$project": {
            "idee_texte": 1,
            "victoires": 1,
            "defaites": 1,
            "sentiment_score": 1,
            "sentiment_label": 1,
            "creer_par_utilisateur": 1,
            "total": {"$add": ["$victoires", "$defaites"]}
        }},
        {"$sort": {"victoires": -1}}
    ]
    
    resultats = list(db.vote.aggregate(pipeline))
    
    if not resultats:
        st.info("Aucun vote enregistré pour cette question.")
        return
    
    # Préparer les données
    data = []
    for result in resultats:
        victoires = int(result.get("victoires", 0))
        defaites = int(result.get("defaites", 0))
        total = victoires + defaites
        score = round((victoires / total) * 100, 2) if total > 0 else 0.0
        
        type_idee = "Idée téléchargée" if result.get("creer_par_utilisateur") == "oui" else "Idée originale"
        
        data.append({
            "Idée": result["idee_texte"],
            "Score": float(score),
            "Type": type_idee,
            "Sentiment": result.get("sentiment_label", "Non analysé"),
            "Score Sentiment": float(result.get("sentiment_score", 0.0)),
            "Victoires": int(victoires),
            "Défaites": int(defaites),
            "Total": int(total)
        })
    
    df = pd.DataFrame(data).sort_values(by="Score", ascending=False)
    
    if not df.empty:
        # 🏆 Idée la plus soutenue
        meilleure = df.iloc[0]
        st.markdown(f"""
        <div style='background-color: #E8F5E9; padding: 1rem; border-radius: 10px; border-left: 5px solid #4CAF50;'>
            <h4 style='color: #2E7D32; margin: 0;'>🏆 Idée la plus soutenue</h4>
            <p style='margin: 0.5rem 0;'><strong>{meilleure['Idée']}</strong></p>
            <p style='margin: 0;'>Score: <strong>{meilleure['Score']:.1f}%</strong> | 
            Sentiment: <strong>{meilleure['Sentiment']}</strong> | 
            Votes: {meilleure['Total']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Graphique des scores
        st.markdown("### 📈 Classement des idées")
        
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X('Score:Q', title='Score (%)', scale=alt.Scale(domain=[0, 100])),
            y=alt.Y('Idée:N', sort='-x', title=''),
            color=alt.Color('Type:N', 
                          scale=alt.Scale(domain=["Idée originale", "Idée téléchargée"], 
                                        range=["#1f77b4", "#ff7f0e"]),
                          title="Type d'idée"),
            tooltip=['Idée:N', 'Score:Q', 'Victoires:Q', 'Défaites:Q', 'Type:N']
        ).properties(
            height=400,
            title="Score de préférence par idée"
        )
        
        st.altair_chart(chart, use_container_width=True)
        
        # Tableau détaillé
        st.markdown("### 📋 Détail des résultats")
        display_df = df[['Idée', 'Score', 'Victoires', 'Défaites', 'Total', 'Sentiment', 'Type']]
        st.dataframe(display_df, use_container_width=True)

# =============================================================
# === PAGE D'ACCUEIL ===
# =============================================================

def display_home_page():
    """Affiche la page d'accueil avec design moderne"""
    
    # CSS personnalisé
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 4rem 2rem;
            border-radius: 0 0 20px 20px;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
        }
        
        .main-title {
            font-size: 3.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        .main-subtitle {
            font-size: 1.3rem;
            opacity: 0.9;
            max-width: 800px;
            margin: 0 auto 2rem;
            line-height: 1.6;
        }
        
        .stats-container {
            display: flex;
            justify-content: center;
            gap: 2rem;
            flex-wrap: wrap;
            margin: 2rem 0;
        }
        
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            text-align: center;
            min-width: 150px;
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 0.5rem;
        }
        
        .stat-label {
            color: #666;
            font-size: 0.9rem;
        }
        
        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
            margin: 3rem 0;
        }
        
        .feature-card {
            background: white;
            border-radius: 15px;
            padding: 2rem;
            box-shadow: 0 8px 30px rgba(0,0,0,0.08);
            border: 1px solid rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        }
        
        .feature-card:hover {
            box-shadow: 0 12px 40px rgba(0,0,0,0.12);
            transform: translateY(-5px);
        }
        
        .feature-icon {
            font-size: 2.5rem;
            margin-bottom: 1rem;
            color: #667eea;
        }
        
        .feature-title {
            font-size: 1.3rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 1rem;
        }
        
        .feature-description {
            color: #666;
            line-height: 1.6;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header principal
    st.markdown("""
    <div class="main-header">
        <h1 class="main-title">🗳️ QUE VOULONS-NOUS POUR L'AFRIQUE ?</h1>
        <p class="main-subtitle">
            Plateforme citoyenne interactive pour explorer les priorités sociales, 
            politiques et économiques des Africains. Proposez, comparez et classez 
            des idées pour l'avenir du continent.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Statistiques en temps réel
    try:
        db = get_db_connection()
        
        total_questions = db.question.count_documents({})
        total_idees = db.idees.count_documents({})
        total_votes = db.vote.count_documents({})
        total_users = db.navigateur.count_documents({})
        
        st.markdown(f"""
        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-number">{total_questions}</div>
                <div class="stat-label">Questions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_idees}</div>
                <div class="stat-label">Idées</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_votes}</div>
                <div class="stat-label">Votes</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_users}</div>
                <div class="stat-label">Participants</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    except:
        pass
    
    # Section Fonctionnalités
    st.markdown("## ✨ Fonctionnalités principales")
    
    features = [
        {
            "icon": "🤔",
            "title": "Comparaison par paires",
            "description": "Méthode scientifique de Salganik pour mesurer les préférences collectives de manière précise et sans biais."
        },
        {
            "icon": "💡",
            "title": "Idées collaboratives",
            "description": "Proposez vos propres idées et voyez-les comparées avec toutes les autres idées existantes."
        },
        {
            "icon": "📊",
            "title": "Analyses avancées",
            "description": "Visualisez les résultats avec des graphiques interactifs et des analyses de sentiment automatiques."
        },
        {
            "icon": "🌍",
            "title": "Perspective africaine",
            "description": "Plateforme dédiée aux enjeux spécifiques du continent africain, par et pour les Africains."
        }
    ]
    
    cols = st.columns(2)
    for idx, feature in enumerate(features):
        with cols[idx % 2]:
            st.markdown(f"""
            <div class="feature-card">
                <div class="feature-icon">{feature['icon']}</div>
                <h3 class="feature-title">{feature['title']}</h3>
                <p class="feature-description">{feature['description']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # CTA Section
    st.markdown("## 🚀 Prêt à participer ?")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if st.button("✍️ Proposer une question", 
                    use_container_width=True, 
                    type="primary",
                    key="home_btn_create"):
            st.session_state.current_tab = "create"
            st.rerun()
    
    with col2:
        if st.button("🗳️ Commencer à voter", 
                    use_container_width=True,
                    key="home_btn_vote"):
            st.session_state.current_tab = "vote"
            st.rerun()
    
    with col3:
        if st.button("📊 Voir les résultats", 
                    use_container_width=True,
                    key="home_btn_stats"):
            st.session_state.current_tab = "stats"
            st.rerun()
    
    with col4:
        if st.button("📈 Visualisations", 
                    use_container_width=True,
                    key="home_btn_viz"):
            st.session_state.current_tab = "visualisations"
            st.rerun()

# =============================================================
# === FONCTION PRINCIPALE ===
# =============================================================

def main():
    """Fonction principale"""
    
    # Navigation
    tabs = ["🏠 Accueil", "➕ Créer", "🗳️ Voter", "📊 Statistiques", "📈 Visualisations"]
    tab_keys = ["home", "create", "vote", "stats", "visualisations"]
    
    selected_tab = st.session_state.current_tab
    
    # Afficher les onglets avec des clés uniques
    cols = st.columns([1, 1, 1, 1, 1, 2])
    
    for idx, (tab_name, tab_key) in enumerate(zip(tabs, tab_keys)):
        with cols[idx]:
            if st.button(tab_name, 
                        use_container_width=True,
                        type="primary" if selected_tab == tab_key else "secondary",
                        key=f"nav_{tab_key}"):
                st.session_state.current_tab = tab_key
                st.rerun()
    
    # Afficher le statut utilisateur
    with cols[5]:
        if st.session_state.get("email"):
            st.markdown(f"<div style='text-align: right; color: #666;'>👤 {st.session_state.email}</div>", 
                       unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align: right; color: #666;'>👤 Visiteur</div>", 
                       unsafe_allow_html=True)
    
    # Séparateur
    st.markdown("---")
    
    # Afficher le contenu selon l'onglet sélectionné
    if selected_tab == "home":
        display_home_page()
    
    elif selected_tab == "create":
        creer_question()
    
    elif selected_tab == "vote":
        participer()
    
    elif selected_tab == "stats":
        voir_resultats()
    
    elif selected_tab == "visualisations":
        afficher_visualisations()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem 0;">
        <p>🌍 <strong>Wiki Survey - Afrique Participative</strong></p>
        <p>Plateforme citoyenne pour le dialogue et la prise de décision collective</p>
        <p style="font-size: 0.8rem;">© 2024 - Tous droits réservés</p>
    </div>
    """, unsafe_allow_html=True)

# === Point d'entrée ===
if __name__ == "__main__":
    main()
