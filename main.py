# import streamlit as st
# # Import the page functions from photo_sku.py
# from photo_sku import photo_sku_generator_page
# # Import the new page function for fingerprint reports
# from fingerprint_report_page import fingerprint_report_page
# # Import the new login page function
# from login_page import login_page

# # --- Page Functions ---

# def home_page():
#     """
#     Displays the home page of the application.
#     """
#     st.markdown("<h1 style='text-align: center; color: #1E90FF;'>D&H Group Web App</h1>", unsafe_allow_html=True)
#     st.markdown("""
#         <div style="text-align: center; padding: 20px;">
#             <p style="font-size: 1.2em;">Welcome to the D&H Group Web App!</p>
#             <p>Use the sidebar navigation to explore different tools and generators.</p>
#         </div>
#         """, unsafe_allow_html=True)

# # Main Streamlit application entry point
# def main():
#     st.set_page_config(page_title="D&H Group Web App", page_icon="🌐", layout="wide")

#     # Initialize session state for page navigation and login status
#     if 'page' not in st.session_state:
#         st.session_state.page = 'home' # Default to home page
#     if 'logged_in' not in st.session_state:
#         st.session_state.logged_in = False # Default to not logged in

#     # Check if user is logged in
#     if not st.session_state.logged_in:
#         # If not logged in, display the login page
#         login_page()
#     else:
#         # If logged in, display the main app content with sidebar navigation
#         with st.sidebar:
#             st.header("Navigation")
#             if st.button("🏠 Home", use_container_width=True, key="nav_home"):
#                 st.session_state.page = 'home'
#             if st.button("📷 SKU Generator", use_container_width=True, key="nav_sku"):
#                 st.session_state.page = 'sku_generator'
#             if st.button("⏰ Fingerprint Reports", use_container_width=True, key="nav_fingerprint"):
#                 st.session_state.page = 'fingerprint_reports'
            
#             st.markdown("---") # Separator for logout button
#             if st.button("🚪 Logout", use_container_width=True, key="logout_button"):
#                 st.session_state.logged_in = False
#                 st.session_state.page = 'home' # Reset page to home after logout
#                 st.experimental_rerun() # Rerun to show login page

#         # --- Display Pages based on session state ---
#         if st.session_state.page == 'home':
#             home_page()
#         elif st.session_state.page == 'sku_generator':
#             photo_sku_generator_page()
#         elif st.session_state.page == 'fingerprint_reports':
#             fingerprint_report_page()
#         # Add conditions for other pages here

# if __name__ == "__main__":
#     main()


import streamlit as st
# Import the page functions from photo_sku.py
from photo_sku import photo_sku_generator_page
# Import the new page function for fingerprint reports
from fingerprint_report_page import fingerprint_report_page
# Import the new login page function
from login_page import login_page

# --- Page Functions ---

def home_page():
    """
    Displays the home page of the application.
    """
    st.markdown("<h1 style='text-align: center; color: #1E90FF;'>D&H Group Web App</h1>", unsafe_allow_html=True)
    st.markdown("""
        <div style="text-align: center; padding: 20px;">
            <p style="font-size: 1.2em;">Welcome to the D&H Group Web App!</p>
            <p>Use the sidebar navigation to explore different tools and generators.</p>
        </div>
        """, unsafe_allow_html=True)

# Main Streamlit application entry point
def main():
    st.set_page_config(page_title="D&H Group Web App", page_icon="🌐", layout="wide")

    # Initialize session state for page navigation and login status
    if 'page' not in st.session_state:
        st.session_state.page = 'home' # Default to home page
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False # Default to not logged in

    # Check if user is logged in
    if not st.session_state.logged_in:
        # If not logged in, display the login page
        login_page()
    else:
        # If logged in, display the main app content with sidebar navigation
        with st.sidebar:
            st.header("Navigation")
            if st.button("🏠 Home", use_container_width=True, key="nav_home"):
                st.session_state.page = 'home'
            if st.button("📷 SKU Generator", use_container_width=True, key="nav_sku"):
                st.session_state.page = 'sku_generator'
            if st.button("⏰ Fingerprint Reports", use_container_width=True, key="nav_fingerprint"):
                st.session_state.page = 'fingerprint_reports'
            
            st.markdown("---") # Separator for logout button
            if st.button("🚪 Logout", use_container_width=True, key="logout_button"):
                st.session_state.logged_in = False
                st.session_state.page = 'home' # Reset page to home after logout
                st.rerun() # Rerun to show login page (updated from experimental_rerun)

        # --- Display Pages based on session state ---
        if st.session_state.page == 'home':
            home_page()
        elif st.session_state.page == 'sku_generator':
            photo_sku_generator_page()
        elif st.session_state.page == 'fingerprint_reports':
            fingerprint_report_page()
        # Add conditions for other pages here

if __name__ == "__main__":
    main()

