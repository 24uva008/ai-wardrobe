
import streamlit as st
import sqlite3
import hashlib
import os
import io
import json
import numpy as np
from PIL import Image
from itertools import combinations

st.set_page_config(page_title="AI Wardrobe", page_icon="🎀", layout="wide")

DB = "wardrobe.db"
os.makedirs("wardrobe_images", exist_ok=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {font-family:Poppins,sans-serif;}
.stApp {background:#fff5fa;}
[data-testid="stSidebar"] {background:#ffe0ed;}
h1,h2,h3 {color:#ad3974;}
.stButton>button, .stFormSubmitButton>button {
background:#e65b9b;color:white;border:0;border-radius:12px;
font-weight:600;width:100%;
}
.stButton>button:hover {background:#c83c80;color:white;}
.hero {background:linear-gradient(120deg,#ffd4e7,#fff0f7);
padding:24px;border-radius:22px;margin-bottom:20px;}
</style>
""", unsafe_allow_html=True)


def db_connect():
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
        username TEXT, name TEXT, category TEXT, color TEXT,
        style TEXT, occasions TEXT, image_path TEXT,
        clip_vector TEXT
    )""")
    con.execute("""
    CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT, outfit_key TEXT, rating INTEGER
    )""")
    con.commit()
    return con


con = db_connect()


def pw_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


@st.cache_resource(show_spinner="Loading CLIP AI model. First load may take time...")
def get_clip():
    from transformers import CLIPModel, CLIPProcessor
    import torch
    model_id = "openai/clip-vit-base-patch32"
    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(model_id)
    model.eval()
    return model, processor, torch


def extract_clip(image_bytes):
    model, processor, torch = get_clip()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        features = model.get_image_features(**inputs)
        features = features / features.norm(p=2, dim=-1, keepdim=True)
    return features[0].cpu().numpy().tolist()


def similarity(a, b):
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


st.markdown("""
<div class="hero">
<h1>🎀 AI Wardrobe</h1>
<h3>Your personal virtual fashion assistant</h3>
<p>Discover outfit combinations from your own wardrobe.</p>
</div>
""", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None

# LOGIN AND REGISTRATION
if st.session_state.user is None:
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_register:
        st.subheader("Create your account 💗")
        with st.form("register_form"):
            new_user = st.text_input("Choose username")
            new_password = st.text_input("Choose password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            register = st.form_submit_button("Register")

        if register:
            if len(new_user.strip()) < 3:
                st.warning("Username needs at least 3 characters.")
            elif len(new_password) < 6:
                st.warning("Password needs at least 6 characters.")
            elif new_password != confirm:
                st.warning("Passwords do not match.")
            else:
                try:
                    con.execute(
                        "INSERT INTO users(username,password) VALUES(?,?)",
                        (new_user.strip(), pw_hash(new_password))
                    )
                    con.commit()
                    st.success("Account created! Now select the Login tab.")
                except sqlite3.IntegrityError:
                    st.error("Username already exists. Choose another.")

    with tab_login:
        st.subheader("Welcome back 💕")
        with st.form("login_form"):
            login_user = st.text_input("Username")
            login_password = st.text_input("Password", type="password")
            login = st.form_submit_button("Login")

        if login:
            result = con.execute(
                "SELECT * FROM users WHERE username=? AND password=?",
                (login_user.strip(), pw_hash(login_password))
            ).fetchone()

            if result:
                st.session_state.user = login_user.strip()
                st.rerun()
            else:
                st.error("Incorrect username or password. Register first if needed.")

    st.stop()


user = st.session_state.user

with st.sidebar:
    st.title("🎀 AI Wardrobe")
    st.write("Hello,", user)
    page = st.radio(
        "Choose a page",
        ["Find Your Outfit", "My Wardrobe", "My Feedback"]
    )
    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()


# MY WARDROBE
if page == "My Wardrobe":
    st.title("👗 My Wardrobe")
    st.write("Upload and save clothing images here.")

    with st.form("add_clothing", clear_on_submit=True):
        image_file = st.file_uploader(
            "Choose clothing image", type=["jpg", "jpeg", "png", "webp"]
        )
        name = st.text_input("Clothing name", placeholder="Black kurti")
        category = st.selectbox(
            "Category", ["Top", "Bottom", "Dress", "Footwear", "Accessory", "Other"]
        )
        color = st.selectbox(
            "Colour", ["Black", "White", "Pink", "Blue", "Red", "Green",
                       "Yellow", "Purple", "Brown", "Beige", "Grey", "Other"]
        )
        style = st.selectbox(
            "Style", ["Casual", "Formal", "Traditional", "Party", "Any"]
        )
        occasions = st.multiselect(
            "Suitable occasions",
            ["College", "Office", "Wedding", "Party", "Casual outing",
             "Festival", "Any"]
        )
        save = st.form_submit_button("Save Clothing")

    if save:
        if image_file is None or not name.strip():
            st.warning("Enter a clothing name and upload an image.")
        else:
            image_bytes = image_file.getvalue()
            filename = f"{user}_{os.urandom(5).hex()}.jpg"
            path = os.path.join("wardrobe_images", filename)
            Image.open(io.BytesIO(image_bytes)).convert("RGB").save(path)

            vector_text = ""
            try:
                with st.spinner("CLIP is extracting image features..."):
                    vector_text = json.dumps(extract_clip(image_bytes))
                st.success("CLIP image features extracted!")
            except Exception as e:
                st.warning("Image saved, but CLIP could not load. Check requirements.txt.")
                st.caption(str(e))

            con.execute("""
                INSERT INTO clothes
                (username,name,category,color,style,occasions,image_path,clip_vector)
                VALUES(?,?,?,?,?,?,?,?)
            """, (
                user, name.strip(), category, color, style,
                ", ".join(occasions) if occasions else "Any",
                path, vector_text
            ))
            con.commit()
            st.success("Clothing saved to your wardrobe!")

    clothes = con.execute(
        "SELECT * FROM clothes WHERE username=? ORDER BY id DESC", (user,)
    ).fetchall()

    st.subheader(f"My saved clothes ({len(clothes)})")
    if not clothes:
        st.info("Add at least two clothing items to get outfit suggestions.")
    else:
        cols = st.columns(3)
        for i, item in enumerate(clothes):
            with cols[i % 3]:
                if os.path.exists(item["image_path"]):
                    st.image(item["image_path"], use_container_width=True)
                st.markdown(f"**{item['name']}**")
                st.caption(
                    f"{item['category']} · {item['color']} · {item['style']}"
                )
                st.caption("Occasions: " + item["occasions"])
                if st.button("Delete", key=f"delete_{item['id']}"):
                    if os.path.exists(item["image_path"]):
                        os.remove(item["image_path"])
                    con.execute(
                        "DELETE FROM clothes WHERE id=? AND username=?",
                        (item["id"], user)
                    )
                    con.commit()
                    st.rerun()


# OUTFIT SUGGESTIONS
elif page == "Find Your Outfit":
    st.title("✨ Find Your Outfit")
    st.write("Choose an occasion to find combinations from your saved clothes.")

    clothes = con.execute(
        "SELECT * FROM clothes WHERE username=?", (user,)
    ).fetchall()

    if len(clothes) < 2:
        st.info("Open My Wardrobe and save at least two clothing items first.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            occasion = st.selectbox(
                "Occasion", ["College", "Office", "Wedding", "Party",
                             "Casual outing", "Festival", "Any"]
            )
        with c2:
            style_filter = st.selectbox(
                "Style", ["Any", "Casual", "Formal", "Traditional", "Party"]
            )
        with c3:
            color_filter = st.selectbox(
                "Preferred colour", ["Any", "Black", "White", "Pink",
                                     "Blue", "Red", "Green", "Other"]
            )

        eligible = []
        for item in clothes:
            allowed = [x.strip().lower() for x in item["occasions"].split(",")]
            if occasion != "Any" and "any" not in allowed and occasion.lower() not in allowed:
                continue
            if style_filter != "Any" and item["style"] not in (style_filter, "Any"):
                continue
            eligible.append(item)

        tops = [x for x in eligible if x["category"] in ("Top", "Dress")]
        bottoms = [x for x in eligible if x["category"] in ("Bottom", "Footwear", "Accessory")]

        pairs = [(a, b) for a in tops for b in bottoms]
        if not pairs:
            pairs = list(combinations(eligible, 2))

        if not pairs:
            st.warning("No matching items. Try Occasion = Any or add more clothes.")
        else:
            feedback = con.execute(
                "SELECT outfit_key,rating FROM feedback WHERE username=?", (user,)
            ).fetchall()
            scores = {}
            for row in feedback:
                scores[row["outfit_key"]] = scores.get(row["outfit_key"], 0) + row["rating"]

            ranked = []
            for a, b in pairs:
                key = f"{min(a['id'],b['id'])}-{max(a['id'],b['id'])}"
                bonus = sum(
                    1 for x in (a, b)
                    if color_filter != "Any" and x["color"] == color_filter
                )
                sim = None
                try:
                    va = json.loads(a["clip_vector"]) if a["clip_vector"] else None
                    vb = json.loads(b["clip_vector"]) if b["clip_vector"] else None
                    if va and vb:
                        sim = similarity(va, vb)
                except Exception:
                    pass
                score = scores.get(key, 0) + bonus
                ranked.append((score, key, a, b, sim))

            ranked.sort(key=lambda x: x[0], reverse=True)

            for n, (score, key, a, b, sim) in enumerate(ranked[:8], 1):
                st.markdown("---")
                st.subheader(f"Outfit idea {n}")
                left, right = st.columns(2)
                with left:
                    if os.path.exists(a["image_path"]):
                        st.image(a["image_path"], use_container_width=True)
                    st.write(f"**{a['name']}** · {a['color']}")
                with right:
                    if os.path.exists(b["image_path"]):
                        st.image(b["image_path"], use_container_width=True)
                    st.write(f"**{b['name']}** · {b['color']}")

                if sim is not None:
                    st.caption(f"CLIP image-vector similarity: {sim:.2f}")

                f1, f2 = st.columns(2)
                with f1:
                    if st.button("👍 Like", key=f"like_{key}_{n}"):
                        con.execute(
                            "INSERT INTO feedback(username,outfit_key,rating) VALUES(?,?,?)",
                            (user, key, 1)
                        )
                        con.commit()
                        st.success("Feedback saved!")
                        st.rerun()
                with f2:
                    if st.button("👎 Dislike", key=f"dislike_{key}_{n}"):
                        con.execute(
                            "INSERT INTO feedback(username,outfit_key,rating) VALUES(?,?,?)",
                            (user, key, -1)
                        )
                        con.commit()
                        st.success("Feedback saved!")
                        st.rerun()

    st.caption(
    "Prototype: occasion filtering uses rules. CLIP extracts visual image features; "
    "cosine similarity compares vectors. It does not guarantee fashion compatibility."
    )


# FEEDBACK HISTORY
else:
    st.title("💌 My Feedback")
    rows = con.execute(
        "SELECT outfit_key,rating FROM feedback WHERE username=? ORDER BY id DESC",
        (user,)
    ).fetchall()

    if not rows:
        st.info("No feedback yet. Like or dislike an outfit first.")
    else:
        st.metric("Feedback submitted", len(rows))
        for row in rows:
            label = "👍 Liked" if row["rating"] > 0 else "👎 Disliked"
            st.write(f"{label} — Outfit IDs: {row['outfit_key']}")

st.markdown("---")
st.caption("AI Wardrobe · CLIP + cosine similarity + rule-based filtering + feedback")
