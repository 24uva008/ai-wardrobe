
import streamlit as st
import sqlite3
import hashlib
import os
import io
import json
import numpy as np
from PIL import Image
from itertools import combinations

st.set_page_config(
    page_title="AI Wardrobe",
    page_icon="🎀",
    layout="wide"
)

DB = "wardrobe.db"
IMAGE_DIR = "wardrobe_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {font-family:Poppins,sans-serif;}
.stApp {background:#fff5fa;}
[data-testid="stSidebar"] {background:#ffe0ed;}
h1,h2,h3 {color:#ad3974;}
.stButton>button, .stFormSubmitButton>button {
background:#e65b9b;color:white;border:0;
border-radius:12px;font-weight:600;width:100%;
}
.stButton>button:hover {background:#c83c80;color:white;}
.hero {background:linear-gradient(120deg,#ffd4e7,#fff0f7);
padding:25px;border-radius:22px;margin-bottom:20px;}
.card {background:white;border:1px solid #f4c4da;
border-radius:18px;padding:16px;margin-bottom:12px;}
</style>
""", unsafe_allow_html=True)


def connect_db():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row

    con.execute("""
    CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )""")

    con.execute("""
    CREATE TABLE IF NOT EXISTS clothes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        name TEXT,
        category TEXT,
        color TEXT,
        style TEXT,
        occasions TEXT,
        image_path TEXT,
        clip_vector TEXT
    )""")

    con.execute("""
    CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        outfit_key TEXT,
        rating INTEGER
    )""")

    con.commit()
    return con


con = connect_db()


def password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


@st.cache_resource(show_spinner="Loading CLIP AI model...")
def load_clip():
    import torch
    from transformers import CLIPModel, CLIPProcessor

    model_name = "openai/clip-vit-base-patch32"
    model = CLIPModel.from_pretrained(model_name)
    processor = CLIPProcessor.from_pretrained(model_name)
    model.eval()
    return model, processor, torch


def extract_features(image_bytes):
    try:
        model, processor, torch = load_clip()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")

        with torch.no_grad():
            features = model.get_image_features(**inputs)
            features = features / features.norm(
                p=2, dim=-1, keepdim=True
            )

        return features[0].cpu().numpy().tolist()

    except Exception as error:
        st.error(f"CLIP could not load: {error}")
        return None


def cosine_similarity(vector1, vector2):
    a = np.array(vector1, dtype=float)
    b = np.array(vector2, dtype=float)

    denominator = np.linalg.norm(a) * np.linalg.norm(b)

    if denominator == 0:
        return 0.0

    return float(np.dot(a, b) / denominator)


st.markdown("""
<div class="hero">
<h1>🎀 AI Wardrobe</h1>
<h3>Your personal virtual fashion assistant</h3>
<p>Discover outfit combinations from your own wardrobe.</p>
</div>
""", unsafe_allow_html=True)


if "user" not in st.session_state:
    st.session_state.user = None


if not st.session_state.user:
    login, register = st.tabs(["Login", "Register"])

    with register:
        st.subheader("Create your account 💗")

        new_user = st.text_input("Choose username", key="new_user")
        new_password = st.text_input(
            "Choose password", type="password", key="new_password"
        )
        confirm_password = st.text_input(
            "Confirm password", type="password", key="confirm_password"
        )

        if st.button("Register"):
            if len(new_user.strip()) < 3:
                st.warning("Username must contain at least 3 characters.")

            elif len(new_password) < 6:
                st.warning("Password must contain at least 6 characters.")

            elif new_password != confirm_password:
                st.warning("Passwords do not match.")

            else:
                
                try:
                    con.execute(
                        "INSERT INTO users (username, password) VALUES (?, ?)",
                        (
                            new_user.strip(),
                            password_hash(new_password)
                        )
                    )
                    con.commit()
                    st.success("Account created! Now click the Login tab.")
                except sqlite3.IntegrityError:
                    st.error("Username already exists. Please choose another.")
                except sqlite3.OperationalError as error:
                    st.error(f"Database error: {error}")
    with login:
        st.subheader("Welcome back 💗")

        username = st.text_input("Username", key="login_username")
        password = st.text_input(
            "Password", type="password", key="login_password"
        )

        if st.button("Login"):
            result = con.execute(
                "SELECT * FROM users WHERE username = ? AND password = ?",
                (username.strip(), password_hash(password))
            ).fetchone()

            if result:
                st.session_state.user = username.strip()
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    st.stop()
