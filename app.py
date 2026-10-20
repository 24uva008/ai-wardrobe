import streamlit as st
import sqlite3
from datetime import datetime

st.set_page_config(page_title="AI Wardrobe", page_icon="🎀", layout="wide")

DB = "ai_wardrobe.db"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {font-family:Poppins,sans-serif;}
.stApp {background:#fff5fa;}
[data-testid="stSidebar"] {background:#ffe0ed;}
h1,h2,h3 {color:#ad3974;}
.stButton>button {
 background:#e65b9b;color:white;border:0;border-radius:12px;
 font-weight:600;width:100%;
}
.stButton>button:hover {background:#c83c80;color:white;}
.card {
 background:white;border:1px solid #f4c4da;border-radius:18px;
 padding:16px;margin-bottom:12px;
}
.hero {
 background:linear-gradient(120deg,#ffd4e7,#fff0f7);
 padding:25px;border-radius:22px;margin-bottom:20px;
}
</style>
""", unsafe_allow_html=True)


def connect():
    return sqlite3.connect(DB, check_same_thread=False)


with connect() as con:
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS clothes(
        id INTEGER PRIMARY KEY, uid INTEGER, name TEXT, category TEXT,
        color TEXT, style TEXT, occasions TEXT, photo BLOB)""")
    con.execute("""CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY, uid INTEGER, occasion TEXT,
        outfit TEXT, rating TEXT, date TEXT)""")


def get_clothes(uid):
    with connect() as con:
        return con.execute(
            "SELECT id,name,category,color,style,occasions,photo FROM clothes WHERE uid=?",
            (uid,)
        ).fetchall()


def get_feedback(uid):
    with connect() as con:
        return con.execute(
            "SELECT occasion,outfit,rating,date FROM feedback WHERE uid=? ORDER BY id DESC",
            (uid,)
        ).fetchall()


# LOGIN / REGISTER
if "uid" not in st.session_state:
    st.session_state.uid = None

if st.session_state.uid is None:
    st.markdown("""
    <div class="hero">
    <h1>🎀 AI Wardrobe</h1>
    <h3>Your personal virtual fashion assistant</h3>
    <p>Discover beautiful outfit combinations from your own wardrobe.</p>
    </div>
    """, unsafe_allow_html=True)

    mode = st.radio("Welcome!", ["Login", "Register"], horizontal=True)

    with st.form("account"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button(mode)

    if submit:
        if not username.strip() or not password:
            st.error("Enter your username and password.")
        elif mode == "Register":
            try:
                with connect() as con:
                    con.execute("INSERT INTO users(username,password) VALUES(?,?)",
                                (username.strip(), password))
                st.success("Account created! Select Login to continue.")
            except sqlite3.IntegrityError:
                st.error("Username already exists. Try another.")
        else:
            with connect() as con:
                row = con.execute(
                    "SELECT id FROM users WHERE username=? AND password=?",
                    (username.strip(), password)
                ).fetchone()
            if row:
                st.session_state.uid = row[0]
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    st.stop()


uid = st.session_state.uid
clothes = get_clothes(uid)

st.sidebar.markdown("# 🎀 AI Wardrobe")
st.sidebar.write(f"Welcome, {st.session_state.get('username', 'User')}!")
page = st.sidebar.radio("MENU", [
    "✨ Outfit Suggestions",
    "👗 My Wardrobe",
    "💗 My Feedback"
])

if st.sidebar.button("Log out"):
    st.session_state.uid = None
    st.rerun()


# PAGE 1: OUTFIT SUGGESTIONS
if page == "✨ Outfit Suggestions":
    st.markdown("""
    <div class="hero">
    <h1>✨ Find Your Outfit</h1>
    <p>Choose an occasion and discover combinations from your saved clothes.</p>
    </div>
    """, unsafe_allow_html=True)

    if not clothes:
        st.info("First, open My Wardrobe and add some clothes.")
    else:
        occasion = st.selectbox("1. Select occasion",
            ["College", "Casual", "Wedding", "Party", "Office", "Festive"])
        style = st.selectbox("2. Preferred style",
            ["Any style", "Simple", "Casual", "Formal", "Traditional", "Grand"])
        color = st.selectbox("3. Preferred colour",
            ["Any colour", "Pink", "Black", "White", "Blue", "Red",
             "Green", "Yellow", "Purple", "Beige", "Grey", "Denim"])

        if st.button("💗 Suggest My Outfit"):
            st.session_state.show_results = True
            st.session_state.occasion = occasion
            st.session_state.style = style
            st.session_state.color = color

        if st.session_state.get("show_results"):
            occasion = st.session_state.occasion
            style = st.session_state.style
            color = st.session_state.color

            tops = [x for x in clothes if x[2] in
                    ["Top", "Shirt", "Kurti", "T-shirt", "Blouse"]]
            bottoms = [x for x in clothes if x[2] in
                       ["Bottom", "Pants", "Jeans", "Skirt", "Leggings"]]
            dresses = [x for x in clothes if x[2] in
                       ["Dress", "One-piece", "Kurta set"]]

            feedback = get_feedback(uid)
            liked = [x[1] for x in feedback if x[2] == "Like"]
            disliked = [x[1] for x in feedback if x[2] == "Dislike"]

            results = []
            for top in tops:
                for bottom in bottoms:
                    title = top[1] + " + " + bottom[1]
                    score = 0
                    if top[4] == style or style == "Any style":
                        score += 2
                    if bottom[4] == style or style == "Any style":
                        score += 2
                    if top[3] == color or color == "Any colour":
                        score += 2
                    if bottom[3] in ["Black", "White", "Beige", "Denim", "Grey"]:
                        score += 1
                    if occasion in top[5] or occasion in bottom[5]:
                        score += 3
                    if title in liked:
                        score += 2
                    if title in disliked:
                        score -= 3
                    results.append((score, title, top, bottom))

            for dress in dresses:
                score = 3 if occasion in dress[5] else 0
                if dress[4] == style or style == "Any style":
                    score += 2
                if dress[3] == color or color == "Any colour":
                    score += 2
                results.append((score, dress[1], dress, None))

            results.sort(key=lambda x: x[0], reverse=True)

            st.markdown(f"## Your outfit ideas for {occasion} 💕")
            if not results:
                st.warning("Add a top and bottom, or a dress, to get recommendations.")
            else:
                for _, title, first, second in results[:6]:
                    with st.container(border=True):
                        st.subheader("🎀 " + title)
                        a, b = st.columns(2)
                        with a:
                            if first[6]:
                                st.image(first[6], use_container_width=True)
                            st.write(first[1])
                            st.caption(f"{first[3]} · {first[4]}")
                        if second:
                            with b:
                                if second[6]:
                                    st.image(second[6], use_container_width=True)
                                st.write(second[1])
                                st.caption(f"{second[3]} · {second[4]}")

                        f1, f2 = st.columns(2)
                        with f1:
                            if st.button("💗 Like", key="L"+title):
                                with connect() as con:
                                    con.execute(
                                        "INSERT INTO feedback(uid,occasion,outfit,rating,date) VALUES(?,?,?,?,?)",
                                        (uid, occasion, title, "Like",
                                         datetime.now().strftime("%d %b %Y %I:%M %p")))
                                st.success("Thanks! Your feedback is saved.")
                        with f2:
                            if st.button("👎 Dislike", key="D"+title):
                                with connect() as con:
                                    con.execute(
                                        "INSERT INTO feedback(uid,occasion,outfit,rating,date) VALUES(?,?,?,?,?)",
                                        (uid, occasion, title, "Dislike",
                                         datetime.now().strftime("%d %b %Y %I:%M %p")))
                                st.info("Feedback saved.")


# PAGE 2: MY WARDROBE
elif page == "👗 My Wardrobe":
    st.markdown("""
    <div class="hero">
    <h1>👗 My Wardrobe</h1>
    <p>Save your clothes here. Outfit suggestions will use these items.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("add_clothes", clear_on_submit=True):
        name = st.text_input("Clothing name", placeholder="e.g. Pink kurti")
        category = st.selectbox("Clothing type",
            ["Top", "Shirt", "Kurti", "T-shirt", "Blouse",
             "Bottom", "Pants", "Jeans", "Skirt", "Leggings",
             "Dress", "One-piece", "Kurta set"])
        color = st.selectbox("Colour",
            ["Black", "White", "Pink", "Blue", "Red", "Green",
             "Yellow", "Purple", "Beige", "Grey", "Denim", "Brown"])
        style = st.selectbox("Style",
            ["Simple", "Casual", "Formal", "Traditional", "Grand"])
        occasions = st.multiselect("Suitable occasions",
            ["College", "Casual", "Wedding", "Party", "Office", "Festive"],
            default=["Casual"])
        photo = st.file_uploader("Upload clothing photo (optional)",
                                 type=["jpg", "jpeg", "png", "webp"])
        save = st.form_submit_button("💗 Save Clothing")

    if save:
        if not name.strip():
            st.error("Enter a name for your clothing item.")
        elif not occasions:
            st.error("Select at least one occasion.")
        else:
            image = photo.getvalue() if photo else None
            with connect() as con:
                con.execute(
                    """INSERT INTO clothes(uid,name,category,color,style,occasions,photo)
                    VALUES(?,?,?,?,?,?,?)""",
                    (uid, name.strip(), category, color, style,
                     ",".join(occasions), image)
                )
            st.success("Clothing saved!")
            st.rerun()

    clothes = get_clothes(uid)
    st.markdown(f"## Your saved clothes ({len(clothes)})")

    if not clothes:
        st.info("Your wardrobe is empty. Add your first clothing item above.")
    else:
        cols = st.columns(3)
        for i, item in enumerate(clothes):
            with cols[i % 3]:
                with st.container(border=True):
                    if item[6]:
                        st.image(item[6], use_container_width=True)
                    else:
                        st.markdown("## 👚")
                    st.subheader(item[1])
                    st.write(f"{item[2]} · {item[3]}")
                    st.caption(f"Style: {item[4]}")
                    st.caption(f"Occasions: {item[5]}")
                    if st.button("🗑️ Delete", key=f"del{item[0]}"):
                        with connect() as con:
                            con.execute("DELETE FROM clothes WHERE id=? AND uid=?",
                                        (item[0], uid))
                        st.rerun()


# PAGE 3: FEEDBACK
elif page == "💗 My Feedback":
    st.markdown("""
    <div class="hero">
    <h1>💗 My Feedback</h1>
    <p>Review the likes and dislikes you gave to your outfit suggestions.</p>
    </div>
    """, unsafe_allow_html=True)

    feedback = get_feedback(uid)
    if not feedback:
        st.info("No feedback yet. Go to Outfit Suggestions and select Like or Dislike.")
    else:
        st.metric("Total feedback", len(feedback))
        for occasion, outfit, rating, date in feedback:
            with st.container(border=True):
                st.write("💗" if rating == "Like" else "👎", rating)
                st.subheader(outfit)
                st.caption(f"{occasion} · {date}")

st.divider()
st.caption("AI Wardrobe · Prototype uses rule-based outfit matching and saved feedback.")
