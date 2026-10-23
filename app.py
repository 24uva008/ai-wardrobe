
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "wardrobe.db")
IMG_DIR = os.path.join(BASE_DIR, "wardrobe_images")
os.makedirs(IMG_DIR, exist_ok=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: Poppins, sans-serif;
}
.stApp {
    background: #fff5fa;
}
[data-testid="stSidebar"] {
    background: #ffe0ed;
}
h1, h2, h3 {
    color: #ad3974;
}
.stButton > button, .stFormSubmitButton > button {
    background: #e65b9b;
    color: white;
    border: 0;
    border-radius: 12px;
    font-weight: 600;
    min-height: 45px;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    background: #c83c80;
    color: white;
}
.hero {
    background: linear-gradient(120deg, #ffd4e7, #fff0f7);
    padding: 24px;
    border-radius: 22px;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------

def add_missing_columns(con, table, wanted):
    existing = {
        row["name"]
        for row in con.execute(f"PRAGMA table_info({table})").fetchall()
    }

    for column, column_type in wanted.items():
        if column not in existing:
            con.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"
            )


def db_connect():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row

    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS clothes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            name TEXT,
            category TEXT,
            color TEXT,
            style TEXT,
            occasions TEXT,
            image_path TEXT,
            clip_vector TEXT
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            outfit_key TEXT,
            rating INTEGER
        )
    """)

    add_missing_columns(con, "users", {
        "username": "TEXT",
        "password": "TEXT"
    })

    add_missing_columns(con, "clothes", {
        "id": "INTEGER",
        "username": "TEXT",
        "name": "TEXT",
        "category": "TEXT",
        "color": "TEXT",
        "style": "TEXT",
        "occasions": "TEXT",
        "image_path": "TEXT",
        "clip_vector": "TEXT"
    })

    add_missing_columns(con, "feedback", {
        "id": "INTEGER",
        "username": "TEXT",
        "outfit_key": "TEXT",
        "rating": "INTEGER"
    })

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
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def show_image(path):
    try:
        st.image(path, width="stretch")
    except TypeError:
        st.image(path, use_container_width=True)


# ---------------- CLIP AI ----------------

@st.cache_resource(show_spinner="Loading CLIP AI model...")
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

    if not hasattr(features, "norm"):
        features = features.pooler_output

    features = features / features.norm(
        p=2, dim=-1, keepdim=True
    )

    return features[0].cpu().numpy().tolist()


def similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)

    if denominator == 0:
        return 0.0

    return float(np.dot(a, b) / denominator)


def classify_group(image, labels, prompt_type):
    """CLIP gives an approximate label for the uploaded image."""
    model, processor, torch = get_clip()

    prompts = [
        f"a photo of a {label.lower()} clothing item"
        if prompt_type == "item"
        else f"a photo of clothing that is {label.lower()}"
        if prompt_type == "color"
        else f"a photo of clothing in {label.lower()} style"
        if prompt_type == "style"
        else f"clothing suitable for {label.lower()}"
        for label in labels
    ]

    inputs = processor(
        text=prompts,
        images=image,
        return_tensors="pt",
        padding=True
    )

    with torch.no_grad():
        outputs = model(**inputs)
        scores = outputs.logits_per_image[0]
        best_index = int(scores.argmax().item())

    return labels[best_index]


def analyze_clothing(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    category = classify_group(
        image,
        ["Top", "Bottom", "Dress", "Footwear", "Accessory", "Other"],
        "item"
    )

    color = classify_group(
        image,
        ["Black", "White", "Pink", "Blue", "Red", "Green",
         "Yellow", "Purple", "Brown", "Beige", "Grey"],
        "color"
    )

    style = classify_group(
        image,
        ["Casual", "Formal", "Traditional", "Party"],
        "style"
    )

    # CLIP classification is approximate.
    # Keep all occasions available rather than guessing an occasion.
    occasions = "Any"

    vector = extract_clip(image_bytes)

    return category, color, style, occasions, vector


# ---------------- HEADER AND NAVIGATION ----------------

st.markdown("""
<div class="hero">
    <h1>🎀 AI Wardrobe</h1>
    <h3>Your personal virtual fashion assistant</h3>
    <p>Discover outfit combinations from your own wardrobe.</p>
</div>
""", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None

if "page" not in st.session_state:
    st.session_state.page = "Home"


def go_to(page):
    st.session_state.page = page


# ---------------- LOGIN AND REGISTRATION ----------------

if st.session_state.user is None:
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_register:
        st.subheader("Create your account 💗")

        with st.form("register_form"):
            new_user = st.text_input("Choose username")
            new_password = st.text_input(
                "Choose password", type="password"
            )
            confirm = st.text_input(
                "Confirm password", type="password"
            )
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
                    st.success(
                        "Account created! Now select the Login tab."
                    )
                except sqlite3.IntegrityError:
                    st.error("Username already exists. Choose another.")
                except sqlite3.Error as e:
                    st.error(f"Database error: {e}")

    with tab_login:
        st.subheader("Welcome back 💕")

        with st.form("login_form"):
            login_user = st.text_input("Username")
            login_password = st.text_input(
                "Password", type="password"
            )
            login = st.form_submit_button("Login")

        if login:
            try:
                result = con.execute(
                    "SELECT * FROM users WHERE username=? AND password=?",
                    (login_user.strip(), pw_hash(login_password))
                ).fetchone()

                if result:
                    st.session_state.user = login_user.strip()
                    st.session_state.page = "Home"
                    st.rerun()
                else:
                    st.error(
                        "Incorrect username or password. Register first if needed."
                    )
            except sqlite3.Error as e:
                st.error(f"Database error: {e}")

    st.stop()


user = st.session_state.user

with st.sidebar:
    st.title("🎀 AI Wardrobe")
    st.write(f"Hello, {user}")

    if st.button("Logout", use_container_width=True):
        st.session_state.user = None
        st.session_state.page = "Home"
        st.rerun()


# ---------------- HOME PAGE ----------------

page = st.session_state.page

if page == "Home":
    st.title("Welcome to Your Wardrobe 💗")
    st.write("Choose what you want to do.")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### ✨ Find Your Outfit")
        st.write("Discover combinations for your occasion.")
        if st.button("Find Your Outfit", key="home_find",
                     use_container_width=True):
            go_to("Find Your Outfit")
            st.rerun()

    with c2:
        st.markdown("### 👗 My Wardrobe")
        st.write("Upload and view your clothing images.")
        if st.button("My Wardrobe", key="home_wardrobe",
                     use_container_width=True):
            go_to("My Wardrobe")
            st.rerun()

    c3, c4 = st.columns(2)

    with c3:
        st.markdown("### 💌 Your Feedback")
        st.write("See the outfits you liked or disliked.")
        if st.button("Your Feedback", key="home_feedback",
                     use_container_width=True):
            go_to("Your Feedback")
            st.rerun()

    with c4:
        st.markdown("### 🏠 Back to Home Page")
        st.write("Return to the main page.")
        if st.button("Back to Home Page", key="home_back",
                     use_container_width=True):
            go_to("Home")
            st.rerun()


# ---------------- PAGE NAVIGATION ----------------

if page != "Home":
    if st.button("🏠 Back to Home Page", key="back_home"):
        go_to("Home")
        st.rerun()


# ---------------- MY WARDROBE ----------------

if page == "My Wardrobe":
    st.title("👗 My Wardrobe")
    st.write("Select multiple clothing images and upload them together.")

    image_files = st.file_uploader(
        "Choose all your clothing images",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="multiple_clothes"
    )

    if st.button("Save All Clothing", use_container_width=True):
        if not image_files:
            st.warning("Please select at least one image.")
        else:
            saved_count = 0

            progress = st.progress(0)

            for index, image_file in enumerate(image_files):
                try:
                    image_bytes = image_file.getvalue()

                    image = Image.open(
                        io.BytesIO(image_bytes)
                    ).convert("RGB")

                    with st.spinner(
                        f"Processing image {index + 1} of {len(image_files)}..."
                    ):
                        category, color, style, occasions, vector = (
                            analyze_clothing(image_bytes)
                        )

                    filename = (
                        f"{hashlib.sha256(user.encode()).hexdigest()[:12]}_"
                        f"{os.urandom(5).hex()}.jpg"
                    )

                    path = os.path.join(IMG_DIR, filename)
                    image.save(path, format="JPEG")

                    name = os.path.splitext(image_file.name)[0].strip()
                    if not name:
                        name = f"Clothing {index + 1}"

                    con.execute("""
                        INSERT INTO clothes
                        (username, name, category, color, style,
                         occasions, image_path, clip_vector)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user,
                        name,
                        category,
                        color,
                        style,
                        occasions,
                        os.path.join("wardrobe_images", filename),
                        json.dumps(vector)
                    ))

                    con.commit()
                    saved_count += 1

                except Exception as e:
                    st.warning(
                        f"Could not process {image_file.name}: {e}"
                    )

                progress.progress((index + 1) / len(image_files))

            st.success(f"Saved {saved_count} clothing image(s).")
            st.rerun()

    clothes = con.execute(
        "SELECT * FROM clothes WHERE username=? ORDER BY id DESC",
        (user,)
    ).fetchall()

    st.subheader(f"My saved clothes ({len(clothes)})")

    if not clothes:
        st.info("Upload some clothing images to get started.")
    else:
        cols = st.columns(3)

        for index, item in enumerate(clothes):
            with cols[index % 3]:
                path = full_path(item["image_path"])

                if path and os.path.exists(path):
                    show_image(path)

                st.markdown(f"**{item['name']}**")
                st.caption(
                    f"{item['category'] or 'Other'} · "
                    f"{item['color'] or 'Unknown'}"
                )
                st.caption(f"Style: {item['style'] or 'Any'}")

                if st.button(
                    "Delete",
                    key=f"delete_{item['id']}_{index}",
                    use_container_width=True
                ):
                    if path and os.path.exists(path):
                        os.remove(path)

                    con.execute(
                        "DELETE FROM clothes WHERE id=? AND username=?",
                        (item["id"], user)
                    )
                    con.commit()
                    st.rerun()


# ---------------- FIND YOUR OUTFIT ----------------

elif page == "Find Your Outfit":
    st.title("✨ Find Your Outfit")
    st.write(
        "Choose an occasion to find combinations from your saved clothes."
    )

    clothes = con.execute(
        "SELECT * FROM clothes WHERE username=?",
        (user,)
    ).fetchall()

    if len(clothes) < 2:
        st.info(
            "Open My Wardrobe and save at least two clothing items first."
        )
    else:
        c1, c2, c3 = st.columns(3)

        with c1:
            occasion = st.selectbox(
                "Occasion",
                ["College", "Office", "Wedding", "Party",
                 "Casual outing", "Festival", "Any"]
            )

        with c2:
            style_filter = st.selectbox(
                "Style",
                ["Any", "Casual", "Formal", "Traditional", "Party"]
            )

        with c3:
            color_filter = st.selectbox(
                "Preferred colour",
                ["Any", "Black", "White", "Pink", "Blue",
                 "Red", "Green", "Other"]
            )

        eligible = []

        for item in clothes:
            allowed = [
                value.strip().lower()
                for value in (item["occasions"] or "Any").split(",")
            ]

            if (
                occasion != "Any"
                and "any" not in allowed
                and occasion.lower() not in allowed
            ):
                continue

            if (
                style_filter != "Any"
                and item["style"] not in (style_filter, "Any")
            ):
                continue

            eligible.append(item)

        tops = [
            item for item in eligible
            if item["category"] in ("Top", "Dress")
        ]

        bottoms = [
            item for item in eligible
            if item["category"] in ("Bottom", "Footwear", "Accessory")
        ]

        pairs = [(a, b) for a in tops for b in bottoms]

        if not pairs:
            pairs = list(combinations(eligible, 2))

        if not pairs:
            st.warning(
                "No matching items. Try Occasion = Any or add more clothes."
            )
        else:
            feedback = con.execute(
                "SELECT outfit_key, rating FROM feedback WHERE username=?",
                (user,)
            ).fetchall()

            scores = {}

            for row in feedback:
                scores[row["outfit_key"]] = (
                    scores.get(row["outfit_key"], 0) + (row["rating"] or 0)
                )

            ranked = []

            for a, b in pairs:
                key = (
                    f"{min(a['id'], b['id'])}-"
                    f"{max(a['id'], b['id'])}"
                )

                bonus = sum(
                    1 for item in (a, b)
                    if color_filter != "Any"
                    and item["color"] == color_filter
                )

                sim = None

                try:
                    va = json.loads(a["clip_vector"]) if a["clip_vector"] else None
                    vb = json.loads(b["clip_vector"]) if b["clip_vector"] else None

                    if va and vb:
                        sim = similarity(va, vb)
                except Exception:
                    pass

                score = (
                    scores.get(key, 0) * 2
                    + bonus
                    + (0.3 * sim if sim is not None else 0)
                )

                ranked.append((score, key, a, b, sim))

            ranked.sort(key=lambda value: value[0], reverse=True)

            for number, (score, key, a, b, sim) in enumerate(
                ranked[:8], 1
            ):
                st.markdown("---")
                st.subheader(f"Outfit idea {number}")

                left, right = st.columns(2)

                with left:
                    path_a = full_path(a["image_path"])
                    if path_a and os.path.exists(path_a):
                        show_image(path_a)
                    st.write(f"**{a['name']}** · {a['color']}")

                with right:
                    path_b = full_path(b["image_path"])
                    if path_b and os.path.exists(path_b):
                        show_image(path_b)
                    st.write(f"**{b['name']}** · {b['color']}")

                if sim is not None:
                    st.caption(
                        f"CLIP image-vector similarity: {sim:.2f}"
                    )

                f1, f2 = st.columns(2)

                with f1:
                    if st.button(
                        "👍 Like", key=f"like_{key}_{number}",
                        use_container_width=True
                    ):
                        con.execute(
                            "DELETE FROM feedback WHERE username=? AND outfit_key=?",
                            (user, key)
                        )
                        con.execute(
                            "INSERT INTO feedback(username,outfit_key,rating) VALUES(?,?,?)",
                            (user, key, 1)
                        )
                        con.commit()
                        st.rerun()

                with f2:
                    if st.button(
                        "👎 Dislike", key=f"dislike_{key}_{number}",
                        use_container_width=True
                    ):
                        con.execute(
                            "DELETE FROM feedback WHERE username=? AND outfit_key=?",
                            (user, key)
                        )
                        con.execute(
                            "INSERT INTO feedback(username,outfit_key,rating) VALUES(?,?,?)",
                            (user, key, -1)
                        )
                        con.commit()
                        st.rerun()

    st.caption(
        "CLIP extracts image features. Occasion filtering uses saved metadata; "
        "visual classification and similarity are approximate."
    )


# ---------------- YOUR FEEDBACK ----------------

elif page == "Your Feedback":
    st.title("💌 Your Feedback")

    rows = con.execute(
        "SELECT outfit_key, rating FROM feedback WHERE username=? ORDER BY id DESC",
        (user,)
    ).fetchall()

    if not rows:
        st.info("No feedback yet. Like or dislike an outfit first.")
    else:
        names = {
            row["id"]: row["name"]
            for row in con.execute(
                "SELECT id, name FROM clothes WHERE username=?",
                (user,)
            ).fetchall()
        }

        st.metric("Feedback submitted", len(rows))

        for row in rows:
            label = (
                "👍 Liked"
                if (row["rating"] or 0) > 0
                else "👎 Disliked"
            )

            try:
                ida, idb = [
                    int(value) for value in row["outfit_key"].split("-")
                ]
                outfit_text = (
                    f"{names.get(ida, 'Deleted item')} + "
                    f"{names.get(idb, 'Deleted item')}"
                )
            except Exception:
                outfit_text = str(row["outfit_key"])

            st.write(f"{label} — {outfit_text}")


# ---------------- FOOTER ----------------

st.markdown("---")
st.caption(
    "AI Wardrobe · CLIP + cosine similarity + "
    "rule-based filtering + feedback"
)
