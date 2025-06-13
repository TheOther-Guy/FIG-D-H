import streamlit as st
# Import the page functions from photo_sku.py
from photo_sku import photo_sku_generator_page

# --- Page Functions ---

def home_page():
    """
    Displays the home page of the application.
    """
    st.markdown("<h1 style='text-align: center; color: #1E90FF;'>D&H Group Web App</h1>", unsafe_allow_html=True)

# Main Streamlit application entry point
def main():
    st.set_page_config(page_title="D&H Group Web App", page_icon="🌐", layout="wide")

    # Initialize session state for page navigation if not already set
    if 'page' not in st.session_state:
        st.session_state.page = 'home' # Default to home page

    # --- Sidebar for Navigation ---
    with st.sidebar:
        st.header("Navigation")
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = 'home'
        if st.button("📷 SKU Generator", use_container_width=True):
            st.session_state.page = 'sku_generator'
        # Add more buttons here for future pages (e.g., if you create a 'contact.py' file)
        # if st.button("📞 Contact Us", use_container_width=True):
        #     st.session_state.page = 'contact'

    # --- Display Pages based on session state ---
    if st.session_state.page == 'home':
        home_page()
    elif st.session_state.page == 'sku_generator':
        photo_sku_generator_page()
    # Add conditions for other pages here
    # elif st.session_state.page == 'contact':
    #     contact_page() # Assuming contact_page() is defined in contact.py or directly here

if __name__ == "__main__":
    main()
