
import streamlit as st

st.set_page_config(
    page_title="AI Wardrobe",
    page_icon="👗",
    layout="wide"
)

st.title("👗 AI Wardrobe")
st.write("Your Personal AI Fashion Assistant")
st.divider()

st.header("1. Choose Your Occasion")

occasion = st.selectbox(
    "Where are you going?",
    ["College", "Wedding", "Party", "Casual", "Office"]
)

preference = st.selectbox(
    "Choose your clothing preference",
    ["Traditional", "Western", "Casual", "Any Style"]
)

st.header("2. Add Your Wardrobe")

with st.form("wardrobe_form"):
    clothing_name = st.text_input(
        "Clothing name",
        placeholder="e.g. Black kurti"
    )

    category = st.selectbox(
        "Clothing category",
        ["Top", "Kurti", "Shirt", "Jeans",
         "Trousers", "Skirt", "Dress"]
    )

    colour = st.selectbox(
        "Clothing colour",
        ["Black", "White", "Blue", "Red",
         "Green", "Pink", "Yellow", "Beige",
         "Brown", "Other"]
    )

    submitted = st.form_submit_button("Add Clothing")

if "wardrobe" not in st.session_state:
    st.session_state.wardrobe = []

if submitted:
    if clothing_name.strip():
        st.session_state.wardrobe.append({
            "name": clothing_name.strip(),
            "category": category,
            "colour": colour
        })
        st.success("Clothing added!")
    else:
        st.warning("Please enter a clothing name.")

st.header("3. My Digital Wardrobe")

if st.session_state.wardrobe:
    st.dataframe(st.session_state.wardrobe)
else:
    st.info("Add your clothes to build your wardrobe.")

st.header("4. Outfit Recommendation")

if st.button("Recommend My Outfit"):
    clothes = st.session_state.wardrobe

    if not clothes:
        st.warning("Add clothes to your wardrobe first.")
    else:
        st.subheader(f"Occasion: {occasion}")
        st.write(f"Style preference: {preference}")

        tops = [
            item for item in clothes
            if item["category"] in
            ["Top", "Kurti", "Shirt", "Dress"]
        ]

        bottoms = [
            item for item in clothes
            if item["category"] in
            ["Jeans", "Trousers", "Skirt"]
        ]

        if tops:
            st.write("**Suggested top:**", tops[0]["name"])
        if bottoms:
            st.write("**Suggested bottom:**", bottoms[0]["name"])

        if not tops and not bottoms:
            st.info("Add a top or bottom to get suggestions.")

        st.caption(
            "Basic recommendation demo. Advanced AI matching "
            "will be added in later steps."
        )

st.header("5. Feedback")

feedback = st.radio(
    "Do you like the recommendation?",
    ["Like", "Dislike"],
    horizontal=True
)

if st.button("Submit Feedback"):
    st.success(f"Feedback received: {feedback}")
    st.write(
        "This starter version demonstrates feedback input. "
        "Persistent feedback learning will be added next."
    )
