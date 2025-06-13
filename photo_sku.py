import streamlit as st
import pandas as pd
import re
import io
from collections import defaultdict

# Function to extract SKU from filename
def extract_sku_from_filename(filename):
    """
    Extracts the SKU from a filename following the pattern P_SKUnameD#.jpg.
    Args:
        filename (str): The name of the photo file.
    Returns:
        str: The extracted SKU, or None if no match is found.
    """
    match = re.search(r'P_(.+?)D\d+\.jpg', filename)
    if match:
        return match.group(1)
    return None

# Function to process uploaded photo files
def process_photos_from_uploads(uploaded_files):
    """
    Processes a list of uploaded photo files to extract SKUs and organize photo names.
    Args:
        uploaded_files (list): A list of Streamlit UploadedFile objects.
    Returns:
        tuple: A pandas DataFrame with SKUs and photo names, and an error message (if any).
    """
    sku_photos = defaultdict(list)
    
    if not uploaded_files:
        return None, "No files uploaded."

    for uploaded_file in uploaded_files:
        # Use the name attribute of the uploaded file directly
        filename = uploaded_file.name
        sku = extract_sku_from_filename(filename)
        if sku:
            sku_photos[sku].append(filename)
    
    if not sku_photos:
        return None, "No valid JPG files with correct naming found (e.g., P_SKUnameD1.jpg)"
    
    data = []
    for sku, photos in sku_photos.items():
        row = {'sku': sku}
        try:
            # Sort photos based on the digit after 'D' (e.g., D1, D2, D10)
            photos.sort(key=lambda x: int(re.search(r'D(\d+)\.jpg', x).group(1)))
        except AttributeError:
            # Fallback to alphabetical sort if digit not found or conversion fails
            photos.sort()
        except Exception:
            # Catch any other unexpected errors during sorting
            photos.sort()

        # Populate up to 8 photo columns
        for i in range(8):
            row[f'photo_{i+1}'] = photos[i] if i < len(photos) else ''
        data.append(row)
    
    # Define columns explicitly to ensure order
    columns = ['sku'] + [f'photo_{i+1}' for i in range(8)]
    df = pd.DataFrame(data, columns=columns)
    return df, None

# Streamlit page function for the Photo SKU Generator
def photo_sku_generator_page():
    """
    Displays the photo SKU CSV generator functionality.
    """
    st.title("📷 Photo SKU CSV Generator")
    st.info("⬆️ Select multiple JPG files named like `P_SKUnameD1.jpg`, etc., from your local system.")

    # File uploader now accepts multiple JPG/JPEG files
    uploaded_files = st.file_uploader(
        "Select photos",
        type=["jpg", "jpeg"],
        accept_multiple_files=True
    )
    
    if uploaded_files: # Check if any files were selected
        if st.button("🔍 Process Photos"):
            with st.spinner("Processing..."):
                df, error = process_photos_from_uploads(uploaded_files)
                
                if error:
                    st.error(f"❌ Error: {error}")
                else:
                    st.success(f"✅ Successfully processed {len(df)} SKUs!")

                    # Display metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total SKUs", len(df))
                    with col2:
                        # Calculate total photos by counting non-empty photo columns for each row
                        total_photos = df.iloc[:, 1:].apply(lambda row: row.astype(bool).sum(), axis=1).sum()
                        st.metric("Total Photos", total_photos)
                    with col3:
                        avg_photos = total_photos / len(df) if len(df) > 0 else 0
                        st.metric("Avg Photos per SKU", f"{avg_photos:.1f}")

                    # Preview and download
                    st.subheader("📋 CSV Preview")
                    st.dataframe(df, use_container_width=True)

                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, index=False)
                    st.download_button(
                        label="📥 Download CSV File",
                        data=csv_buffer.getvalue(),
                        file_name="photo_sku_mapping.csv",
                        mime="text/csv",
                        type="primary"
                    )

                    # Show sample results
                    st.subheader("📝 Sample Results")
                    for _, row in df.head(3).iterrows():
                        sku = row['sku']
                        # Filter out empty photo names for display
                        photos = [row[f'photo_{i+1}'] for i in range(8) if row[f'photo_{i+1}']]
                        st.markdown(f"**SKU: {sku}** → {', '.join(photos)}")
    elif uploaded_files is None: # No files selected yet
        st.info("Please select photo files to begin processing.")

