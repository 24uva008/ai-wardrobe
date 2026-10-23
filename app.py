
import streamlit as st
import sqlite3
import hashlib
import os
import io
import json
import numpy as np
from PIL import Image

st.set_page_config(page_title="AI Wardrobe", page_icon="🎀", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "wardrobe.db")
IMG_DIR = os.path.join(BASE_DIR, "wardrobe_images")
os.makedirs(IMG_DIR, exist_ok=True)

# ---------------- DESIGN ----------------
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
    min-height: 42px;
}
.stButton > button:hover {
    background: #c83c80;
    color: white;
}
.hero {
    background: linear-gradient(120deg, #ffd4e7, #fff0f7);
    padding: 22px;
    border-radius: 20px;
    margin-bottom: 18px;
}
[data-testid="stImage"] img {
    object-fit: contain;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------
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

    con.commit()
    return con


try:
    con = db_connect()
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()


def pw_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


def full_path(path):
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def show_image(path, width=160):
    if path and os.path.exists(path):
        st.image(path, width=width)


# ---------------- CLOTHING OPTIONS ----------------
CATEGORIES = [
    "Top", "Shirt", "T-shirt", "Kurti",
    "Bottom", "Jeans", "Trousers",
    "Saree", "Dress", "One-piece",
    "Footwear", "Accessory", "Other"
]

STYLES = [
    "Casual", "Formal", "Traditional", "Grand", "Party"
]

COLORS = [
    "Black", "White", "Grey", "Red", "Pink", "Orange",
    "Yellow", "Green", "Blue", "Purple", "Brown", "Beige", "Cream"
]

OCCASIONS = [
    "College", "Office", "Wedding",
    "Party", "Casual outing", "Festival"
]

TOP_CATEGORIES = {"Top", "Shirt", "T-shirt", "Kurti"}
BOTTOM_CATEGORIES = {"Bottom", "Jeans", "Trousers"}
ONE_PIECE_CATEGORIES = {"Saree", "Dress", "One-piece"}
EXTRAS = {"Footwear", "Accessory"}


# ---------------- DEFAULT OCCASIONS ----------------
def recommended_occasions(category, style):
    if category == "Saree":
        return ["Wedding", "Festival"]

    if style == "Grand":
        return ["Wedding", "Party", "Festival"]

    if style == "Traditional":
        return ["Wedding", "Festival"]

    if style == "Formal":
        return ["Office", "College"]

    if style == "Party":
        return ["Party", "Wedding"]

    if category in ONE_PIECE_CATEGORIES:
        return ["College", "Casual outing", "Party"]

    if category in TOP_CATEGORIES | BOTTOM_CATEGORIES:
        return ["College", "Casual outing"]

    if category in EXTRAS:
        return OCCASIONS.copy()

    return ["Casual outing"]


# ---------------- OCCASION FILTERING ----------------
def is_suitable(item, occasion):
    category = (item["category"] or "Other").strip()
    style = (item["style"] or "").strip()
    name = (item["name"] or "").lower()

    saved_occasions = [
        x.strip().lower()
        for x in (item["occasions"] or "").split(",")
        if x.strip()
    ]

    # Help older records if the clothing name includes saree
    if "saree" in name or "sari" in name:
        category = "Saree"

    if occasion == "Any":
        return category != "Other"

    # Strict occasion/category/style rules
    if occasion == "College":
        category_ok = (
            category in TOP_CATEGORIES
            or category in BOTTOM_CATEGORIES
            or category in EXTRAS
        )
        style_ok = style in {"Casual", "Formal"}
        return category_ok and style_ok

    if occasion == "Office":
        category_ok = (
            category in {"Top", "Shirt", "T-shirt", "Bottom",
                         "Jeans", "Trousers", "Footwear", "Accessory"}
        )
        return category_ok and style == "Formal"

    if occasion == "Casual outing":
        category_ok = (
            category in TOP_CATEGORIES
            or category in BOTTOM_CATEGORIES
            or category in {"Dress", "One-piece", "Footwear", "Accessory"}
        )
        return category_ok and style == "Casual"

    if occasion == "Wedding":
        category_ok = (
            category in {"Saree", "Dress", "One-piece", "Kurti",
                         "Top", "Shirt", "Bottom", "Jeans",
                         "Trousers", "Footwear", "Accessory"}
        )
        style_ok = style in {"Traditional", "Grand", "Party"}
        return category_ok and style_ok

    if occasion == "Party":
        category_ok = (
            category in {"Top", "Shirt", "T-shirt", "Bottom",
                         "Jeans", "Trousers", "Dress", "One-piece",
                         "Footwear", "Accessory"}
        )
        return category_ok and style in {"Party", "Grand"}

    if occasion == "Festival":
        category_ok = (
            category in {"Saree", "Kurti", "Dress", "One-piece",
                         "Top", "Bottom", "Footwear", "Accessory"}
        )
        return category_ok and style in {"Traditional", "Grand", "Party"}

    return False


# ---------------- COLOUR COMPATIBILITY ----------------
def colour_harmony(color_a, color_b):
    if not color_a or not color_b:
        return 0.3

    if color_a == color_b:
        return 0.5

    neutrals = {
        "Black", "White", "Grey", "Beige", "Cream", "Brown"
    }

    if color_a in neutrals or color_b in neutrals:
        return 1.0

    good_pairs = {
        frozenset(("Blue", "White")),
        frozenset(("Blue", "Beige")),
        frozenset(("Blue", "Yellow")),
        frozenset(("Green", "Beige")),
        frozenset(("Green", "White")),
        frozenset(("Pink", "Grey")),
        frozenset(("Pink", "White")),
        frozenset(("Red", "Black")),
        frozenset(("Red", "White")),
        frozenset(("Purple", "Grey")),
        frozenset(("Purple", "White")),
        frozenset(("Brown", "Cream")),
        frozenset(("Orange", "Blue")),
        frozenset(("Yellow", "Purple"))
    }

    if frozenset((color_a, color_b)) in good_pairs:
        return 0.9

    return 0.45


# ---------------- CLIP IMAGE FEATURES ----------------
@st.cache_resource(show_spinner="Loading AI model...")
def get_clip():
    import torch
    from transformers import CLIPModel, CLIPProcessor

    model_name = "openai/clip-vit-base-patch32"
    model = CLIPModel.from_pretrained(model_name)
    processor = CLIPProcessor.from_pretrained(model_name)
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

        features = features / features.norm(
            p=2, dim=-1, keepdim=True
        )

    return features[0].cpu().numpy().tolist()


# ---------------- CLIP SUGGESTIONS ----------------
def clip_classify(image_bytes, labels, prompt_type):
    model, processor, torch = get_clip()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if prompt_type == "category":
        prompts = [
            f"a photo of a person wearing {label.lower()}"
            for label in labels
        ]
    elif prompt_type == "style":
        prompts = [
            f"clothing in {label.lower()} style"
            for label in labels
        ]
    else:
        prompts = [
            f"clothing that is {label.lower()} in colour"
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
        probabilities = scores.softmax(dim=0)

    index = int(probabilities.argmax().item())
    return labels[index]


# ---------------- HEADER ----------------
st.markdown("""
<div class="hero">
    <h1>🎀 AI Wardrobe</h1>
    <h3>Your Personal Virtual Fashion Assistant</h3>
    <p>Discover suitable outfits from your own wardrobe.</p>
</div>
""", unsafe_allow_html=True)


# ---------------- LOGIN / REGISTER ----------------
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    login_tab, register_tab = st.tabs(["Login", "Register"])

    with register_tab:
        st.subheader("Create your account 💗")

        with st.form("register_form"):
            new_user = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            confirm_password = st.text_input(
                "Confirm password", type="password"
            )
            register = st.form_submit_button("Register")

        if register:
            if len(new_user.strip()) < 3:
                st.warning("Username must contain at least 3 characters.")
            elif len(new_password) < 6:
                st.warning("Password must contain at least 6 characters.")
            elif new_password != confirm_password:
                st.warning("Passwords do not match.")
            else:
                try:
                    con.execute(
                        "INSERT INTO users(username,password) VALUES(?,?)",
                        (new_user.strip(), pw_hash(new_password))
                    )
                    con.commit()
                    st.success("Account created! Please log in.")
                except sqlite3.IntegrityError:
                    st.error("Username already exists.")

    with login_tab:
        st.subheader("Welcome back 💕")

        with st.form("login_form"):
            login_user = st.text_input("Username", key="login_user")
            login_password = st.text_input(
                "Password", type="password", key="login_password"
            )
            login = st.form_submit_button("Login")

        if login:
            result = con.execute(
                "SELECT username FROM users WHERE username=? AND password=?",
                (login_user.strip(), pw_hash(login_password))
            ).fetchone()

            if result:
                st.session_state.user = login_user.strip()
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    st.stop()


user = st.session_state.user

with st.sidebar:
    st.title("🎀 AI Wardrobe")
    st.write(f"Hello, {user}")

    page = st.radio(
        "Navigate",
        ["Find Your Outfit", "My Wardrobe", "My Feedback"]
    )

    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()


# ============================================================
# MY WARDROBE
# ============================================================
if page == "My Wardrobe":
    st.title("👗 My Wardrobe")
    st.write(
        "Upload multiple photos together. Confirm the category, colour, "
        "style and suitable occasions for better matching."
    )

    uploaded_files = st.file_uploader(
        "Choose clothing photos",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True
    )

    upload_details = []

    if uploaded_files:
        st.subheader("Confirm each clothing item")

        for index, uploaded in enumerate(uploaded_files):
            default_name = os.path.splitext(uploaded.name)[0].replace(
                "_", " "
            ).replace("-", " ").title()

            with st.container(border=True):
                image_col, details_col = st.columns([1, 3])

                with image_col:
                    try:
                        preview = Image.open(
                            io.BytesIO(uploaded.getvalue())
                        ).convert("RGB")
                        st.image(preview, width=120)
                    except Exception:
                        st.warning("Image preview unavailable.")

                with details_col:
                    st.markdown(f"**Photo {index + 1}: {uploaded.name}**")

                    item_name = st.text_input(
                        "Clothing name",
                        value=default_name,
                        key=f"name_{index}"
                    )

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        category = st.selectbox(
                            "Category / Type",
                            ["Select category"] + CATEGORIES,
                            key=f"category_{index}"
                        )

                    with col2:
                        color = st.selectbox(
                            "Colour",
                            ["Select colour"] + COLORS,
                            key=f"color_{index}"
                        )

                    with col3:
                        style = st.selectbox(
                            "Style",
                            ["Select style"] + STYLES,
                            key=f"style_{index}"
                        )

                    occasions = st.multiselect(
                        "Suitable occasions",
                        OCCASIONS,
                        key=f"occasion_{index}"
                    )

                    upload_details.append(
                        (item_name, category, color, style, occasions)
                    )

        if st.button(
            "💾 Save all clothing",
            type="primary",
            use_container_width=True
        ):
            missing = []

            for i, details in enumerate(upload_details):
                if (
                    details[1] == "Select category"
                    or details[2] == "Select colour"
                    or details[3] == "Select style"
                ):
                    missing.append(str(i + 1))

            if missing:
                st.error(
                    "Select category, colour and style for photo(s): "
                    + ", ".join(missing)
                )
            else:
                progress = st.progress(0)
                saved_count = 0

                for index, uploaded in enumerate(uploaded_files):
                    try:
                        image_bytes = uploaded.getvalue()
                        image = Image.open(
                            io.BytesIO(image_bytes)
                        ).convert("RGB")

                        filename = (
                            hashlib.sha256(
                                (
                                    user + uploaded.name
                                    + str(index) + os.urandom(4).hex()
                                ).encode()
                            ).hexdigest()[:20] + ".jpg"
                        )

                        image_path = os.path.join(IMG_DIR, filename)
                        image.save(
                            image_path,
                            format="JPEG",
                            quality=90,
                            optimize=True
                        )

                        (
                            item_name, category, color,
                            style, selected_occasions
                        ) = upload_details[index]

                        if not selected_occasions:
                            selected_occasions = recommended_occasions(
                                category, style
                            )

                        vector_text = ""

                        try:
                            vector_text = json.dumps(
                                get_image_vector(image_bytes)
                            )
                        except Exception:
                            pass

                        con.execute("""
                            INSERT INTO clothes
                            (username,name,category,color,style,
                             occasions,image_path,clip_vector)
                            VALUES(?,?,?,?,?,?,?,?)
                        """, (
                            user,
                            item_name.strip() or uploaded.name,
                            category,
                            color,
                            style,
                            ", ".join(selected_occasions),
                            os.path.join("wardrobe_images", filename),
                            vector_text
                        ))

                        con.commit()
                        saved_count += 1

                    except Exception as e:
                        st.warning(
                            f"Could not save {uploaded.name}: {e}"
                        )

                    progress.progress(
                        (index + 1) / len(uploaded_files)
                    )

                st.success(f"Saved {saved_count} clothing photo(s).")
                st.rerun()

    clothes = con.execute(
        "SELECT * FROM clothes WHERE username=? ORDER BY id DESC",
        (user,)
    ).fetchall()

    st.subheader(f"My saved clothes ({len(clothes)})")

    if not clothes:
        st.info("Upload clothing photos to start your digital wardrobe.")

    for item in clothes:
        with st.container(border=True):
            image_col, details_col = st.columns([1, 3])

            with image_col:
                path = full_path(item["image_path"])
                if path and os.path.exists(path):
                    show_image(path, width=130)

            with details_col:
                st.markdown(f"**{item['name']}**")
                st.write(
                    f"Type: {item['category']} · "
                    f"Colour: {item['color']} · Style: {item['style']}"
                )
                st.caption(
                    "Suitable for: " + (item["occasions"] or "Not set")
                )

                with st.expander("✏️ Edit clothing details"):
                    with st.form(f"edit_{item['id']}"):
                        edit_name = st.text_input(
                            "Name", value=item["name"] or ""
                        )

                        edit_category = st.selectbox(
                            "Category",
                            CATEGORIES,
                            index=(
                                CATEGORIES.index(item["category"])
                                if item["category"] in CATEGORIES
                                else CATEGORIES.index("Other")
                            )
                        )

                        edit_color = st.selectbox(
                            "Colour",
                            COLORS,
                            index=(
                                COLORS.index(item["color"])
                                if item["color"] in COLORS else 0
                            )
                        )

                        edit_style = st.selectbox(
                            "Style",
                            STYLES,
                            index=(
                                STYLES.index(item["style"])
                                if item["style"] in STYLES else 0
                            )
                        )

                        saved_occasions = [
                            x.strip()
                            for x in (item["occasions"] or "").split(",")
                            if x.strip() in OCCASIONS
                        ]

                        edit_occasions = st.multiselect(
                            "Suitable occasions",
                            OCCASIONS,
                            default=saved_occasions
                        )

                        save_edit = st.form_submit_button("Save changes")

                    if save_edit:
                        if not edit_occasions:
                            edit_occasions = recommended_occasions(
                                edit_category, edit_style
                            )

                        con.execute("""
                            UPDATE clothes
                            SET name=?, category=?, color=?, style=?, occasions=?
                            WHERE id=? AND username=?
                        """, (
                            edit_name.strip() or item["name"],
                            edit_category,
                            edit_color,
                            edit_style,
                            ", ".join(edit_occasions),
                            item["id"],
                            user
                        ))

                        con.commit()
                        st.success("Clothing details updated.")
                        st.rerun()

                if st.button(
                    "🗑️ Delete item",
                    key=f"delete_{item['id']}"
                ):
                    path = full_path(item["image_path"])

                    if path and os.path.exists(path):
                        os.remove(path)

                    con.execute(
                        "DELETE FROM clothes WHERE id=? AND username=?",
                        (item["id"], user)
                    )
                    con.commit()
                    st.rerun()


# ============================================================
# FIND YOUR OUTFIT
# ============================================================
elif page == "Find Your Outfit":
    st.title("✨ Find Your Outfit")
    st.write(
        "Choose your occasion and preferences. The system filters "
        "unsuitable clothes before generating combinations."
    )

    clothes = con.execute(
        "SELECT * FROM clothes WHERE username=?",
        (user,)
    ).fetchall()

    if not clothes:
        st.info("Upload clothing photos in My Wardrobe first.")

    else:
        col1, col2 = st.columns(2)

        with col1:
            occasion = st.selectbox(
                "1. Occasion",
                ["College", "Office", "Wedding", "Party",
                 "Casual outing", "Festival", "Any"]
            )

            style_filter = st.selectbox(
                "2. Preferred style",
                ["Any"] + STYLES
            )

        with col2:
            color_filter = st.selectbox(
                "3. Preferred colour",
                ["Any"] + COLORS
            )

            outfit_type = st.selectbox(
                "4. Outfit type",
                [
                    "Complete outfit (Top + Bottom)",
                    "One-piece (Saree / Dress)",
                    "Any complete outfit"
                ]
            )

        eligible = [
            item for item in clothes
            if is_suitable(item, occasion)
        ]

        if style_filter != "Any":
            eligible = [
                item for item in eligible
                if item["style"] == style_filter
            ]

        tops = [
            item for item in eligible
            if item["category"] in TOP_CATEGORIES
        ]

        bottoms = [
            item for item in eligible
            if item["category"] in BOTTOM_CATEGORIES
        ]

        one_pieces = [
            item for item in eligible
            if item["category"] in ONE_PIECE_CATEGORIES
        ]

        footwear = [
            item for item in eligible
            if item["category"] == "Footwear"
        ]

        outfit_pairs = []

        # Full outfit: only top + bottom
        if outfit_type in {
            "Complete outfit (Top + Bottom)",
            "Any complete outfit"
        }:
            for top in tops:
                for bottom in bottoms:
                    if top["id"] != bottom["id"]:
                        outfit_pairs.append((top, bottom))

        # One-piece outfits: saree/dress + footwear when available
        if outfit_type in {
            "One-piece (Saree / Dress)",
            "Any complete outfit"
        }:
            for piece in one_pieces:
                if footwear:
                    for shoes in footwear:
                        if piece["id"] != shoes["id"]:
                            outfit_pairs.append((piece, shoes))
                else:
                    outfit_pairs.append((piece, piece))

        # Remove duplicate pairs
        unique_pairs = {}

        for a, b in outfit_pairs:
            key = (
                f"{min(a['id'], b['id'])}-"
                f"{max(a['id'], b['id'])}"
            )
            unique_pairs[key] = (a, b)

        if not unique_pairs:
            st.warning(
                "No complete matching outfit found. Check the category, "
                "style and occasion labels in My Wardrobe, or upload "
                "more suitable clothes."
            )

        else:
            feedback_rows = con.execute(
                "SELECT outfit_key, rating FROM feedback WHERE username=?",
                (user,)
            ).fetchall()

            feedback_scores = {}

            for row in feedback_rows:
                feedback_scores[row["outfit_key"]] = (
                    feedback_scores.get(row["outfit_key"], 0)
                    + (row["rating"] or 0)
                )

            ranked = []

            for key, (a, b) in unique_pairs.items():
                if a["id"] == b["id"]:
                    colour_score = 0.5
                else:
                    colour_score = colour_harmony(
                        a["color"], b["color"]
                    )

                preferred_bonus = sum(
                    0.45
                    for item in (a, b)
                    if color_filter != "Any"
                    and item["color"] == color_filter
                )

                score = (
                    feedback_scores.get(key, 0) * 2
                    + colour_score
                    + preferred_bonus
                )

                ranked.append(
                    (score, key, a, b, colour_score)
                )

            ranked.sort(key=lambda x: x[0], reverse=True)

            st.success(
                f"Found {len(ranked)} outfit combination(s)."
            )

            for number, (
                score, key, a, b, colour_score
            ) in enumerate(ranked[:8], 1):

                st.markdown("---")
                st.subheader(f"Outfit idea {number}")

                if a["id"] == b["id"]:
                    path = full_path(a["image_path"])

                    if path and os.path.exists(path):
                        show_image(path, width=180)

                    st.write(f"**{a['name']}**")
                    st.caption(
                        f"{a['category']} · {a['color']} · {a['style']}"
                    )
                    st.caption("Complete one-piece outfit")

                else:
                    left, right = st.columns(2)

                    with left:
                        path_a = full_path(a["image_path"])

                        if path_a and os.path.exists(path_a):
                            show_image(path_a, width=180)

                        st.write(f"**{a['name']}**")
                        st.caption(
                            f"{a['category']} · {a['color']} · {a['style']}"
                        )

                    with right:
                        path_b = full_path(b["image_path"])

                        if path_b and os.path.exists(path_b):
                            show_image(path_b, width=180)

                        st.write(f"**{b['name']}**")
                        st.caption(
                            f"{b['category']} · {b['color']} · {b['style']}"
                        )

                    st.caption(
                        f"Colour compatibility estimate: {colour_score:.2f}"
                    )

                col_like, col_dislike = st.columns(2)

                with col_like:
                    if st.button(
                        "👍 Like",
                        key=f"like_{key}_{number}",
                        use_container_width=True
                    ):
                        con.execute(
                            "DELETE FROM feedback "
                            "WHERE username=? AND outfit_key=?",
                            (user, key)
                        )

                        con.execute("""
                            INSERT INTO feedback(username,outfit_key,rating)
                            VALUES(?,?,?)
                        """, (user, key, 1))

                        con.commit()
                        st.rerun()

                with col_dislike:
                    if st.button(
                        "👎 Dislike",
                        key=f"dislike_{key}_{number}",
                        use_container_width=True
                    ):
                        con.execute(
                            "DELETE FROM feedback "
                            "WHERE username=? AND outfit_key=?",
                            (user, key)
                        )

                        con.execute("""
                            INSERT INTO feedback(username,outfit_key,rating)
                            VALUES(?,?,?)
                        """, (user, key, -1))

                        con.commit()
                        st.rerun()

    st.caption(
        "For better results, select the correct category, colour, "
        "style and suitable occasions when uploading clothes."
    )


# ============================================================
# MY FEEDBACK
# ============================================================
else:
    st.title("💌 My Feedback")

    rows = con.execute(
        "SELECT outfit_key, rating FROM feedback "
        "WHERE username=? ORDER BY id DESC",
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
                id_a, id_b = [
                    int(value)
                    for value in row["outfit_key"].split("-")
                ]

                outfit_text = (
                    f"{names.get(id_a, 'Deleted item')} + "
                    f"{names.get(id_b, 'Deleted item')}"
                )

            except Exception:
                outfit_text = row["outfit_key"]

            st.write(f"{label} — {outfit_text}")


# ---------------- FOOTER ----------------
st.markdown("---")
st.caption(
    "AI Wardrobe · Occasion filtering · Colour compatibility · "
    "Outfit matching · User feedback"
)
