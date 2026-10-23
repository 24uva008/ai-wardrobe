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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "wardrobe.db")
IMG_DIR = os.path.join(BASE_DIR, "wardrobe_images")
os.makedirs(IMG_DIR, exist_ok=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {font-family:Poppins,sans-serif;}
.stApp {background:#fff5fa;}
[data-testid="stSidebar"] {background:#ffe0ed;}
h1,h2,h3 {color:#ad3974;}
.stButton>button, .stFormSubmitButton>button {
background:#e65b9b;color:white;border:0;border-radius:12px;font-weight:600;width:100%;
}
.stButton>button:hover {background:#c83c80;color:white;}
.hero {background:linear-gradient(120deg,#ffd4e7,#fff0f7);padding:24px;border-radius:22px;margin-bottom:20px;}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------
def add_missing_columns(con, table, wanted):
    existing = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
    for col, col_type in wanted.items():
        if col not in existing:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")


def db_connect():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY, password TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS clothes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, name TEXT,
        category TEXT, color TEXT, style TEXT, occasions TEXT,
        image_path TEXT, clip_vector TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT,
        outfit_key TEXT, rating INTEGER)""")
    add_missing_columns(con, "users", {"password": "TEXT"})
    add_missing_columns(con, "clothes", {
        "username": "TEXT", "name": "TEXT", "category": "TEXT", "color": "TEXT",
        "style": "TEXT", "occasions": "TEXT", "image_path": "TEXT", "clip_vector": "TEXT"})
    add_missing_columns(con, "feedback", {
        "username": "TEXT", "outfit_key": "TEXT", "rating": "INTEGER"})
    con.commit()
    return con


try:
    con = db_connect()
except Exception as e:
    st.error("Database could not be opened.")
    st.code(f"{type(e).__name__}: {e}")
    st.stop()


def pw_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


def full_path(path):
    if not path:
        return ""
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


def show_image(path):
    try:
        st.image(path, width="stretch")
    except TypeError:
        st.image(path, use_container_width=True)


# ---------------- CLIP MODEL ----------------
@st.cache_resource(show_spinner="Loading CLIP AI model. The first load may take time...")
def get_clip():
    import torch
    from transformers import CLIPModel, CLIPProcessor
    model_id = "openai/clip-vit-base-patch32"
    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(model_id)
    model.eval()
    return model, processor, torch


def get_image_vector(image_bytes):
    model, processor, torch = get_clip()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        features = model.get_image_features(**inputs)
        if not isinstance(features, torch.Tensor):
            features = features.pooler_output
        features = features / features.norm(p=2, dim=-1, keepdim=True)
    return features[0].cpu().numpy().tolist()


def clip_classify(image_bytes, labels):
    """Predict a broad label from CLIP text/image similarity; prediction can be wrong."""
    model, processor, torch = get_clip()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    prompts = [f"a photo of a clothing item, {label}" for label in labels]
    inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)[0]
    idx = int(probs.argmax().item())
    return labels[idx], float(probs[idx].item())


def dominant_color(image_bytes):
    """Rough colour estimate from the whole image; clothing/background can affect it."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image.thumbnail((80, 80))
    arr = np.asarray(image, dtype=np.float32).reshape(-1, 3)
    rgb = np.median(arr, axis=0)
    palette = {
        "Black": (25, 25, 25), "White": (238, 238, 238), "Grey": (128, 128, 128),
        "Red": (190, 35, 45), "Pink": (225, 125, 165), "Orange": (220, 120, 35),
        "Yellow": (225, 195, 45), "Green": (45, 125, 70), "Blue": (45, 85, 170),
        "Purple": (115, 65, 145), "Brown": (115, 75, 45), "Beige": (205, 185, 145),
        "Cream": (235, 225, 195)
    }
    # Compare brightness and RGB distance; this is only a rough estimate.
    if max(rgb) < 55:
        return "Black"
    if min(rgb) > 218:
        return "White"
    return min(palette, key=lambda name: np.linalg.norm(rgb - np.array(palette[name])))


CATEGORIES = ["Top", "Shirt", "T-shirt", "Kurti", "Bottom", "Jeans", "Trousers", "Saree", "Dress", "One-piece", "Footwear", "Accessory", "Other"]
STYLES = ["Casual", "Formal", "Traditional", "Grand", "Party"]
COLORS = ["Black", "White", "Grey", "Red", "Pink", "Orange", "Yellow", "Green", "Blue", "Purple", "Brown", "Beige", "Cream"]

TOP_CATEGORIES = {"Top", "Shirt", "T-shirt", "Kurti"}
BOTTOM_CATEGORIES = {"Bottom", "Jeans", "Trousers"}
ONE_PIECE_CATEGORIES = {"Saree", "Dress", "One-piece"}
EXTRAS = {"Footwear", "Accessory"}


def recommended_occasions(category, style):
    """Rule-based default occasions; users can correct category/style in My Wardrobe."""
    category = (category or "Other").strip()
    style = (style or "Casual").strip()
    if category == "Saree" or style in {"Traditional", "Grand"}:
        return ["Wedding", "Festival"] if style != "Grand" else ["Wedding", "Party", "Festival"]
    if category in {"Dress", "One-piece"}:
        if style in {"Party", "Grand"}:
            return ["Party", "Wedding", "Festival"]
        return ["College", "Casual outing", "Party"]
    if style == "Formal":
        return ["Office", "College"]
    if style == "Party":
        return ["Party", "Wedding"]
    if category in TOP_CATEGORIES | BOTTOM_CATEGORIES:
        return ["College", "Casual outing"]
    if category in EXTRAS:
        return ["College", "Office", "Casual outing", "Wedding", "Party", "Festival"]
    return ["Casual outing"]


def is_suitable(item, occasion):
    """Hard rules stop clearly unsuitable clothing being recommended for an occasion."""
    category = (item["category"] or "Other").strip()
    style = (item["style"] or "Casual").strip()
    name = (item["name"] or "").lower()
    # Help older records whose category is only 'Dress' but whose name says saree.
    if "saree" in name or "sari" in name:
        category = "Saree"
    if occasion == "Any":
        return category != "Other"
    if occasion == "College":
        return category in TOP_CATEGORIES | BOTTOM_CATEGORIES | EXTRAS and style in {"Casual", "Formal", "Traditional"}
    if occasion == "Office":
        return category in {"Top", "Shirt", "Bottom", "Trousers", "Footwear", "Accessory"} and style == "Formal"
    if occasion == "Casual outing":
        return category in TOP_CATEGORIES | BOTTOM_CATEGORIES | {"Dress", "One-piece", "Footwear", "Accessory"} and style in {"Casual", "Party", "Traditional"}
    if occasion == "Wedding":
        return category in {"Saree", "Dress", "One-piece", "Kurti", "Top", "Bottom", "Footwear", "Accessory"} and style in {"Traditional", "Grand", "Party", "Formal"}
    if occasion == "Party":
        return category in {"Top", "Shirt", "T-shirt", "Bottom", "Jeans", "Trousers", "Dress", "One-piece", "Footwear", "Accessory"} and style in {"Casual", "Party", "Grand", "Formal"}
    if occasion == "Festival":
        return category in {"Saree", "Kurti", "Dress", "One-piece", "Top", "Bottom", "Footwear", "Accessory"} and style in {"Traditional", "Grand", "Casual", "Party"}
    return True


def colour_harmony(a, b):
    """Simple explainable colour compatibility score, not a guarantee of fashion taste."""
    ca, cb = (a or "").strip(), (b or "").strip()
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 0.35
    neutrals = {"Black", "White", "Grey", "Beige", "Cream", "Brown"}
    if ca in neutrals or cb in neutrals:
        return 1.0
    pairs = {
        frozenset(("Blue", "White")), frozenset(("Blue", "Beige")),
        frozenset(("Blue", "Yellow")), frozenset(("Green", "Beige")),
        frozenset(("Green", "White")), frozenset(("Pink", "Grey")),
        frozenset(("Pink", "White")), frozenset(("Red", "Black")),
        frozenset(("Red", "White")), frozenset(("Purple", "Grey")),
        frozenset(("Purple", "White")), frozenset(("Brown", "Cream")),
        frozenset(("Orange", "Blue")), frozenset(("Yellow", "Purple")),
    }
    return 0.9 if frozenset((ca, cb)) in pairs else 0.45


def similarity(a, b):
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


# ---------------- HEADER ----------------
st.markdown("""
<div class="hero">
<h1>🎀 AI Wardrobe</h1>
<h3>Your personal virtual fashion assistant</h3>
<p>Discover outfit combinations from clothes in your own wardrobe.</p>
</div>
""", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- LOGIN / REGISTER ----------------
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
                    con.execute("INSERT INTO users(username,password) VALUES(?,?)",
                                (new_user.strip(), pw_hash(new_password)))
                    con.commit()
                    st.success("Account created! Now select the Login tab.")
                except sqlite3.IntegrityError:
                    st.error("Username already exists. Choose another.")
                except sqlite3.Error as e:
                    st.error(f"Database error: {type(e).__name__}: {e}")

    with tab_login:
        st.subheader("Welcome back 💕")
        with st.form("login_form"):
            login_user = st.text_input("Username")
            login_password = st.text_input("Password", type="password")
            login = st.form_submit_button("Login")
        if login:
            try:
                result = con.execute(
                    "SELECT username FROM users WHERE username=? AND password=?",
                    (login_user.strip(), pw_hash(login_password))
                ).fetchone()
                if result:
                    st.session_state.user = login_user.strip()
                    st.rerun()
                else:
                    st.error("Incorrect username or password. Register first if needed.")
            except sqlite3.Error as e:
                st.error(f"Database error: {type(e).__name__}: {e}")
    st.stop()


user = st.session_state.user
with st.sidebar:
    st.title("🎀 AI Wardrobe")
    st.write("Hello,", user)
    page = st.radio("Choose a page", ["Find Your Outfit", "My Wardrobe", "My Feedback"])
    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()


# ---------------- MY WARDROBE ----------------
if page == "My Wardrobe":
    st.title("👗 My Wardrobe")
    st.write("Select multiple clothing photos together. Type, colour and style are estimated automatically.")
    uploaded_files = st.file_uploader(
        "Choose multiple clothing photos",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True
    )

    if uploaded_files and st.button("Analyse and save all photos", type="primary"):
        progress = st.progress(0)
        saved_count = 0
        for index, uploaded in enumerate(uploaded_files):
            image_bytes = uploaded.getvalue()
            base_name = os.path.splitext(uploaded.name)[0].replace("_", " ").replace("-", " ").strip()
            item_name = base_name.title() if base_name else f"Clothing {index + 1}"
            try:
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                filename = f"{hashlib.sha256((user + uploaded.name + str(index)).encode()).hexdigest()[:16]}.jpg"
                path = os.path.join(IMG_DIR, filename)
                image.save(path, format="JPEG", quality=92)

                # Defaults allow saving even if the model is not available.
                category, style, vector_text = "Other", "Casual", ""
                try:
                    detected_category, _ = clip_classify(image_bytes, [
                        "a casual top", "a shirt or blouse", "a t-shirt",
                        "a kurti or salwar kameez", "jeans", "trousers or pants",
                        "a saree", "a dress", "a one-piece outfit",
                        "footwear", "a handbag or fashion accessory", "other clothing"
                    ])
                    category_map = {
                        "a casual top": "Top", "a shirt or blouse": "Shirt",
                        "a t-shirt": "T-shirt", "a kurti or salwar kameez": "Kurti",
                        "jeans": "Jeans", "trousers or pants": "Trousers",
                        "a saree": "Saree", "a dress": "Dress",
                        "a one-piece outfit": "One-piece", "footwear": "Footwear",
                        "a handbag or fashion accessory": "Accessory", "other clothing": "Other"
                    }
                    category = category_map.get(detected_category, "Other")
                    detected_style, _ = clip_classify(image_bytes, [
                        "casual everyday clothing", "formal office clothing",
                        "traditional Indian clothing", "grand wedding clothing",
                        "party wear clothing"
                    ])
                    style_map = {
                        "casual everyday clothing": "Casual",
                        "formal office clothing": "Formal",
                        "traditional Indian clothing": "Traditional",
                        "grand wedding clothing": "Grand",
                        "party wear clothing": "Party"
                    }
                    style = style_map.get(detected_style, "Casual")
                    vector_text = json.dumps(get_image_vector(image_bytes))
                except Exception:
                    # Still save the photo if CLIP is unavailable.
                    pass

                color = dominant_color(image_bytes)
                occasions = recommended_occasions(category, style)
                con.execute("""
                    INSERT INTO clothes
                    (username,name,category,color,style,occasions,image_path,clip_vector)
                    VALUES(?,?,?,?,?,?,?,?)
                """, (user, item_name, category, color, style, ", ".join(occasions),
                      os.path.join("wardrobe_images", filename), vector_text))
                con.commit()
                saved_count += 1
            except Exception as e:
                st.warning(f"Could not save {uploaded.name}: {e}")
            progress.progress((index + 1) / len(uploaded_files))
        st.success(f"Saved {saved_count} of {len(uploaded_files)} photo(s).")
        st.info("AI labels are estimates. Check the details below and use Edit details if a label is wrong.")
        st.rerun()

    clothes = con.execute(
        "SELECT * FROM clothes WHERE username=? ORDER BY id DESC", (user,)
    ).fetchall()
    st.subheader(f"My saved clothes ({len(clothes)})")
    if not clothes:
        st.info("Upload some clothing photos to start your digital wardrobe.")
    else:
        for item in clothes:
            with st.container(border=True):
                col1, col2 = st.columns([1, 2])
                with col1:
                    p = full_path(item["image_path"])
                    if p and os.path.exists(p):
                        show_image(p)
                with col2:
                    st.markdown(f"**{item['name']}**")
                    st.write(f"Type: {item['category']} · Colour: {item['color']} · Style: {item['style']}")
                    st.caption("Suggested occasions: " + (item["occasions"] or "Casual outing"))
                    with st.expander("Edit details if AI guessed incorrectly"):
                        with st.form(f"edit_{item['id']}"):
                            edit_name = st.text_input("Clothing name", value=item["name"] or "")
                            edit_category = st.selectbox(
                                "Type", CATEGORIES,
                                index=CATEGORIES.index(item["category"] if item["category"] in CATEGORIES else "Other"))
                            colors = COLORS
                            edit_color = st.selectbox("Colour", colors,
                                index=colors.index(item["color"]) if item["color"] in colors else 0)
                            styles = STYLES
                            edit_style = st.selectbox("Style", styles,
                                index=styles.index(item["style"]) if item["style"] in styles else 0)
                            edit_save = st.form_submit_button("Save corrections")
                        if edit_save:
                            new_occasions = recommended_occasions(edit_category, edit_style)
                            con.execute("""UPDATE clothes SET name=?,category=?,color=?,style=?,occasions=?
                                           WHERE id=? AND username=?""",
                                        (edit_name.strip() or item["name"], edit_category, edit_color,
                                         edit_style, ", ".join(new_occasions), item["id"], user))
                            con.commit()
                            st.success("Details updated.")
                            st.rerun()
                    if st.button("Delete", key=f"delete_{item['id']}"):
                        p = full_path(item["image_path"])
                        if p and os.path.exists(p):
                            os.remove(p)
                        con.execute("DELETE FROM clothes WHERE id=? AND username=?", (item["id"], user))
                        con.commit()
                        st.rerun()


# ---------------- FIND YOUR OUTFIT ----------------
elif page == "Find Your Outfit":
    st.title("✨ Find Your Outfit")
    st.write("Occasion rules filter clothes first; colour compatibility and your feedback rank the combinations next.")
    clothes = con.execute("SELECT * FROM clothes WHERE username=?", (user,)).fetchall()

    if len(clothes) < 2:
        st.info("Open My Wardrobe and save at least two clothing items first.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            occasion = st.selectbox("Occasion", ["College", "Office", "Wedding", "Party", "Casual outing", "Festival", "Any"])
        with c2:
            color_filter = st.selectbox("Preferred colour (boosts matching; does not exclude other colours)", ["Any"] + COLORS)

        eligible = [item for item in clothes if is_suitable(item, occasion)]
        if not eligible:
            st.warning("No clothes currently match this occasion. Open My Wardrobe → Edit details and correct the clothing type/style, or choose another occasion.")
        else:
            tops = [x for x in eligible if x["category"] in TOP_CATEGORIES]
            bottoms = [x for x in eligible if x["category"] in BOTTOM_CATEGORIES]
            one_pieces = [x for x in eligible if x["category"] in ONE_PIECE_CATEGORIES]
            extras = [x for x in eligible if x["category"] in EXTRAS]

            # Proper combinations: top + bottom; one-piece outfit + accessory/footwear.
            outfit_pairs = [(a, b) for a in tops for b in bottoms if a["id"] != b["id"]]
            for item in one_pieces:
                if extras:
                    outfit_pairs.extend((item, extra) for extra in extras)
                else:
                    outfit_pairs.append((item, item))  # single-piece outfit; shown once below
            # Do not create random saree + jeans or top + footwear combinations.
            if not outfit_pairs and occasion == "Any":
                outfit_pairs = [(a, b) for a, b in combinations(eligible, 2)
                                if not (a["category"] in ONE_PIECE_CATEGORIES and b["category"] in BOTTOM_CATEGORIES)
                                and not (b["category"] in ONE_PIECE_CATEGORIES and a["category"] in BOTTOM_CATEGORIES)]

            # Remove duplicate pairs while preserving their order.
            unique_pairs = {}
            for a, b in outfit_pairs:
                key = f"{min(a['id'], b['id'])}-{max(a['id'], b['id'])}"
                unique_pairs[key] = (a, b)

            if not unique_pairs:
                st.warning("No suitable outfit combination found. Add a top and bottom, or add footwear/accessory for a dress or saree.")
            else:
                feedback_rows = con.execute("SELECT outfit_key,rating FROM feedback WHERE username=?", (user,)).fetchall()
                feedback_scores = {}
                for row in feedback_rows:
                    feedback_scores[row["outfit_key"]] = feedback_scores.get(row["outfit_key"], 0) + (row["rating"] or 0)

                ranked = []
                for key, (a, b) in unique_pairs.items():
                    colour_score = colour_harmony(a["color"], b["color"]) if a["id"] != b["id"] else 0.5
                    preferred_bonus = sum(0.35 for item in (a, b)
                                          if color_filter != "Any" and item["color"] == color_filter)
                    vector_similarity = None
                    try:
                        va = json.loads(a["clip_vector"]) if a["clip_vector"] else None
                        vb = json.loads(b["clip_vector"]) if b["clip_vector"] else None
                        if va and vb and a["id"] != b["id"]:
                            vector_similarity = similarity(va, vb)
                    except Exception:
                        pass
                    score = (feedback_scores.get(key, 0) * 2.0 + colour_score
                             + preferred_bonus + (0.05 * vector_similarity if vector_similarity is not None else 0))
                    ranked.append((score, key, a, b, colour_score, vector_similarity))
                ranked.sort(key=lambda x: x[0], reverse=True)

                for n, (score, key, a, b, colour_score, vector_similarity) in enumerate(ranked[:8], 1):
                    st.markdown("---")
                    st.subheader(f"Outfit idea {n}")
                    if a["id"] == b["id"]:
                        p = full_path(a["image_path"])
                        if p and os.path.exists(p):
                            show_image(p)
                        st.write(f"**{a['name']}** · {a['category']} · {a['color']} · {a['style']}")
                    else:
                        left, right = st.columns(2)
                        with left:
                            p = full_path(a["image_path"])
                            if p and os.path.exists(p):
                                show_image(p)
                            st.write(f"**{a['name']}** · {a['category']} · {a['color']} · {a['style']}")
                        with right:
                            p = full_path(b["image_path"])
                            if p and os.path.exists(p):
                                show_image(p)
                            st.write(f"**{b['name']}** · {b['category']} · {b['color']} · {b['style']}")
                        st.caption(f"Colour compatibility estimate: {colour_score:.2f}")
                    if vector_similarity is not None:
                        st.caption(f"Visual similarity signal (not a fashion score): {vector_similarity:.2f}")
                    f1, f2 = st.columns(2)
                    with f1:
                        if st.button("👍 Like", key=f"like_{key}_{n}", use_container_width=True):
                            con.execute("DELETE FROM feedback WHERE username=? AND outfit_key=?", (user, key))
                            con.execute("INSERT INTO feedback(username,outfit_key,rating) VALUES(?,?,?)", (user, key, 1))
                            con.commit()
                            st.rerun()
                    with f2:
                        if st.button("👎 Dislike", key=f"dislike_{key}_{n}", use_container_width=True):
                            con.execute("DELETE FROM feedback WHERE username=? AND outfit_key=?", (user, key))
                            con.execute("INSERT INTO feedback(username,outfit_key,rating) VALUES(?,?,?)", (user, key, -1))
                            con.commit()
                            st.rerun()

    st.caption("Note: automatic image labels can be wrong. Correct the Type and Style in My Wardrobe for better recommendations.")


# ---------------- FEEDBACK HISTORY ----------------
else:
    st.title("💌 My Feedback")
    rows = con.execute(
        "SELECT outfit_key,rating FROM feedback WHERE username=? ORDER BY id DESC", (user,)
    ).fetchall()
    if not rows:
        st.info("No feedback yet. Like or dislike an outfit first.")
    else:
        names = {r["id"]: r["name"] for r in con.execute(
            "SELECT id,name FROM clothes WHERE username=?", (user,)).fetchall()}
        st.metric("Feedback submitted", len(rows))
        for row in rows:
            label = "👍 Liked" if (row["rating"] or 0) > 0 else "👎 Disliked"
            try:
                ida, idb = [int(x) for x in row["outfit_key"].split("-")]
                outfit_text = f"{names.get(ida, 'Deleted item')} + {names.get(idb, 'Deleted item')}"
            except Exception:
                outfit_text = str(row["outfit_key"])
            st.write(f"{label} — {outfit_text}")

st.markdown("---")
st.caption("AI Wardrobe · CLIP-based estimates + occasion rules + colour estimate + feedback ranking")
