import streamlit as st

def login_page():
    """
    Displays a login form with username and password fields.
    Authenticates against hardcoded credentials.
    Sets st.session_state.logged_in to True on successful login.
    """
    st.title("🔐 Login to D&H Group Web App")

    # Input fields for username and password
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    # Login button
    if st.button("Login", type="primary", key="login_button"):
        # Simple hardcoded authentication for demonstration purposes
        # In a real application, you would replace this with a secure backend authentication.
        if username == "admin" and password == "adminpass": # Example credentials
            st.session_state.logged_in = True
            st.success("Login successful! Redirecting...")
            st.rerun() # Rerun the app to switch to the main content (updated from experimental_rerun)
        else:
            st.error("Invalid username or password. Please try again.")

    st.markdown("---")
    st.info("Hint: Use username 'admin' and password 'adminpass' to log in.")

