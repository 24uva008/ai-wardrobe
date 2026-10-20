
import streamlit as st
import sqlite3
import os
from datetime import datetime

st.set_page_config(
    page_title="AI Wardrobe",
    page_icon="👗",
    layout="wide"
)

DB_NAME = "wardrobe.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    return sqlite3.connect(DB_NAME)


def setup_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clothes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            colour TEXT NOT NULL,
            style TEXT NOT NULL,
            occasions TEXT NOT NULL,
            image_path TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            outfit TEXT NOT NULL,
            rating TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


setup_db()


def query_db(sql, params=(), fetch=False):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    result = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return result


# Demo wardrobe items
def add_demo_clothes(username):
    existing = query_db(
        "SELECT id FROM clothes WHERE username=?",
        (username,), True
    )
    if existing:
        return

    demo = [
        ("Black Shirt", "Top", "Black", "Casual",
         "College, Casual"),
        ("White Shirt", "Top", "White", "Formal",
         "College, Office, Interview"),
        ("Blue Jeans", "Bottom", "Blue", "Casual",
         "College, Casual"),
        ("Black Trousers", "Bottom", "Black", "Formal",
         "Office, Interview, Party"),
        ("Floral Kurti", "Top", "Pink", "Traditional",
         "College, Festival, Casual"),
        ("Traditional Dress", "One-piece", "Maroon",
         "Grand", "Wedding, Festival, Party")
    ]

    for name, category, colour, style, occasions in demo:
        query_db("""
            INSERT INTO clothes
            (username, name, category, colour, style, occasions)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, name, category, colour, style, occasions))


def login_screen():
    st.title("👗 AI Wardrobe")
    st.write("Your personal virtual fashion assistant")
    st.caption("Discover outfit combinations from your wardrobe.")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input(
            "Password", type="password", key="login_pass"
        )

        if st.button("Login", use_container_width=True):
            users = query_db(
                "SELECT username FROM users WHERE username=? AND password=?",
                (username.strip(), password), True
            )
            if users:
                st.session_state.username = username.strip()
                add_demo_clothes(username.strip())
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab2:
        new_user = st.text_input("Choose username", key="reg_user")
        new_pass = st.text_input(
            "Choose password", type="password", key="reg_pass"
        )

        if st.button("Create Account", use_container_width=True):
            if not new_user.strip() or not new_pass:
                st.warning("Enter a username and password.")
            elif query_db(
                "SELECT username FROM users WHERE username=?",
                (new_user.strip(),), True
            ):
                st.error("Username already exists.")
            else:
                query_db(
                    "INSERT INTO users VALUES (?, ?)",
                    (new_user.strip(), new_pass)
                )
                add_demo_clothes(new_user.strip())
                st.success("Account created! Please log in.")

    st.info(
        "Demo version: use a unique test password. "
        "Production deployment needs secure password hashing and "
        "persistent database storage."
    )


def get_clothes(username):
    return query_db("""
        SELECT id, name, category, colour, style, occasions, image_path
        FROM clothes WHERE username=?
        ORDER BY id DESC
    """, (username,), True)


def wardrobe_page(username):
    st.header("👚 My Wardrobe")
    st.write("View sample clothes or add your own clothing items.")

    with st.expander("➕ Add a clothing item"):
        with st.form("add_clothing", clear_on_submit=True):
            name = st.text_input("Clothing name")
            category = st.selectbox(
                "Category", ["Top", "Bottom", "One-piece", "Footwear",
                             "Accessory", "Outerwear"]
            )
            colour = st.selectbox(
                "Colour", ["Black", "White", "Blue", "Red", "Pink",
                           "Green", "Yellow", "Brown", "Maroon",
                           "Grey", "Beige", "Other"]
            )
            style = st.selectbox(
                "Style", ["Casual", "Formal", "Traditional", "Grand",
                          "Sporty", "Party"]
            )
            occasions = st.multiselect(
                "Suitable occasions",
                ["College", "Office", "Wedding", "Festival",
                 "Party", "Casual", "Interview", "Travel"]
            )
            image = st.file_uploader(
                "Clothing photo (optional)",
                type=["jpg", "jpeg", "png"]
            )
            submitted = st.form_submit_button("Save Clothing")

            if submitted:
                if not name.strip() or not occasions:
                    st.error("Enter the name and select an occasion.")
                else:
                    image_path = None
                    if image:
                        safe_name = (
                            f"{username}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                            f"_{image.name.replace(' ', '_')}"
                        )
                        image_path = os.path.join(UPLOAD_DIR, safe_name)
                        with open(image_path, "wb") as file:
                            file.write(image.getbuffer())

                    query_db("""
                        INSERT INTO clothes
                        (username, name, category, colour, style,
                         occasions, image_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        username, name.strip(), category, colour,
                        style, ", ".join(occasions), image_path
                    ))
                    st.success("Clothing saved!")
                    st.rerun()

    clothes = get_clothes(username)
    if not clothes:
        st.info("Your wardrobe is empty.")
        return

    cols = st.columns(3)
    for i, item in enumerate(clothes):
        item_id, name, category, colour, style, occasions, image_path = item
        with cols[i % 3]:
            with st.container(border=True):
                if image_path and os.path.exists(image_path):
                    st.image(image_path, use_container_width=True)
                st.subheader(name)
                st.write(f"**Category:** {category}")
                st.write(f"**Colour:** {colour}")
                st.write(f"**Style:** {style}")
                st.caption(f"Occasions: {occasions}")
                if st.button("Delete", key=f"delete_{item_id}"):
                    query_db(
                        "DELETE FROM clothes WHERE id=? AND username=?",
                        (item_id, username)
                    )
                    st.rerun()


def recommendation_page(username):
    st.header("✨ Outfit Recommendation")
    st.write("Choose an occasion and preferences to find matching clothes.")

    with st.form("recommendation_form"):
        occasion = st.selectbox(
            "Select occasion",
            ["College", "Office", "Wedding", "Festival",
             "Party", "Casual", "Interview", "Travel"]
        )
        preferred_style = st.selectbox(
            "Preferred style",
            ["Any", "Casual", "Formal", "Traditional", "Grand",
             "Sporty", "Party"]
        )
        preferred_colour = st.selectbox(
            "Preferred colour",
            ["Any", "Black", "White", "Blue", "Red", "Pink",
             "Green", "Yellow", "Brown", "Maroon", "Grey", "Beige"]
        )
        submitted = st.form_submit_button("Recommend Outfits")

    if not submitted:
        st.info("Select your preferences and click Recommend Outfits.")
        return

    clothes = get_clothes(username)
    suitable = [
        item for item in clothes
        if occasion.lower() in item[5].lower()
    ]

    if preferred_style != "Any":
        styled = [
            item for item in suitable
            if item[4].lower() == preferred_style.lower()
        ]
        if styled:
            suitable = styled

    if preferred_colour != "Any":
        coloured = [
            item for item in suitable
            if item[3].lower() == preferred_colour.lower()
        ]
        if coloured:
            suitable = coloured

    # Basic matching: pair a top with a bottom.
    tops = [x for x in suitable if x[2] in ("Top", "One-piece")]
    bottoms = [x for x in suitable if x[2] == "Bottom"]

    # Rank pairs by simple colour/style rules and saved feedback.
    pairs = []
    feedback_rows = query_db(
        "SELECT outfit, rating FROM feedback WHERE username=?",
        (username,), True
    )
    liked = {x[0] for x in feedback_rows if x[1] == "Like"}
    disliked = {x[0] for x in feedback_rows if x[1] == "Dislike"}

    for top in tops:
        if top[2] == "One-piece":
            label = top[1]
            score = 2
            if label in liked:
                score += 3
            if label in disliked:
                score -= 5
            pairs.append((score, label, [top]))
            continue

        for bottom in bottoms:
            if top[3] == bottom[3]:
                score = 0
            else:
                score = 2

            if top[4] == bottom[4]:
                score += 1

            label = f"{top[1]} + {bottom[1]}"
            if label in liked:
                score += 3
            if label in disliked:
                score -= 5
            pairs.append((score, label, [top, bottom]))

    pairs.sort(key=lambda x: x[0], reverse=True)

    if not pairs:
        st.warning(
            "No complete outfit found for this selection. "
            "Try another occasion or add suitable clothes."
        )
        st.write("Suitable individual items:")
        for item in suitable:
            st.write(f"- {item[1]} ({item[3]}, {item[4]})")
        return

    st.subheader("Recommended outfits")
    for index, (_, label, items) in enumerate(pairs[:5], start=1):
        with st.container(border=True):
            st.markdown(f"### {index}. {label}")
            for item in items:
                if item[6] and os.path.exists(item[6]):
                    st.image(item[6], width=180)
                st.write(
                    f"{item[1]} — {item[3]} colour, {item[4]} style"
                )

            left, right = st.columns(2)
            with left:
                if st.button("👍 Like", key=f"like_{index}_{label}"):
                    query_db("""
                        INSERT INTO feedback
                        (username, outfit, rating, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        username, label, "Like",
                        datetime.now().isoformat(timespec="seconds")
                    ))
                    st.success("Feedback saved!")
                    st.rerun()

            with right:
                if st.button("👎 Dislike", key=f"dislike_{index}_{label}"):
                    query_db("""
                        INSERT INTO feedback
                        (username, outfit, rating, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        username, label, "Dislike",
                        datetime.now().isoformat(timespec="seconds")
                    ))
                    st.success("Feedback saved!")
                    st.rerun()

    st.caption(
        "This version uses rule-based filtering and simple colour/style "
        "rules. It does not yet use CLIP or a trained machine-learning model."
    )


def feedback_page(username):
    st.header("💬 My Feedback")
    rows = query_db("""
        SELECT outfit, rating, created_at
        FROM feedback WHERE username=?
        ORDER BY id DESC
    """, (username,), True)

    if not rows:
        st.info("No feedback yet. Like or dislike a recommendation first.")
        return

    for outfit, rating, created_at in rows:
        st.write(f"**{rating}** — {outfit}")
        st.caption(created_at)


def main():
    st.sidebar.title("👗 AI Wardrobe")
    st.sidebar.caption("Virtual Fashion Assistant")

    username = st.session_state.get("username")

    if not username:
        login_screen()
        return

    st.sidebar.success(f"Logged in as {username}")
    page = st.sidebar.radio(
        "Navigate",
        ["Home", "My Wardrobe", "Recommendations", "My Feedback"]
    )

    if st.sidebar.button("Logout"):
        del st.session_state["username"]
        st.rerun()

    if page == "Home":
        st.title("Welcome to AI Wardrobe ✨")
        st.write(
            "Plan outfits using clothes already in your digital wardrobe."
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 👚 Digital Wardrobe")
            st.write("Add clothing details and optional photos.")
        with c2:
            st.markdown("### 🎨 Outfit Matching")
            st.write("Filter by occasion, colour and style.")
        st.markdown("### 🧠 Feedback")
        st.write("Like or dislike recommendations to adjust future ranking.")
        st.info(
            "Demo notice: this is a rule-based prototype. "
            "CLIP image recognition and secure production login "
            "are not implemented yet."
        )

    elif page == "My Wardrobe":
        wardrobe_page(username)
    elif page == "Recommendations":
        recommendation_page(username)
    elif page == "My Feedback":
        feedback_page(username)


main()
