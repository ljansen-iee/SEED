import os
import pandas as pd
import tabula

def open_pdf(file_path, pages="1", multiple_tables=False, encoding="latin1", **kwargs):
    """
    Reads tables from a PDF file using tabula-py.
    
    Args:
        file_path (str): The path to the PDF file.
        pages (str or int): The pages to read (e.g., "140", "1-3", "all").
        multiple_tables (bool): Whether to extract multiple tables.
        encoding (str): The character encoding for the PDF.
        **kwargs: Any other keyword arguments for tabula.read_pdf.
        
    Returns:
        list of DataFrames (if multiple_tables=True) or DataFrame
    """
    return tabula.read_pdf(
        file_path, 
        pages=pages, 
        multiple_tables=multiple_tables, 
        encoding=encoding,
        **kwargs
    )

def read_file(file_path,pdf_options=None):
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path, encoding="utf8")
        elif file_path.endswith('.xlsx'):
            return pd.read_excel(file_path, engine='openpyxl')
        elif file_path.endswith('.pdf'):
            # PDFs are not loaded here; handle them manually with open_pdf()
            return None
        else:
            raise ValueError(f"Unsupported file extension: {file_path}")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None
        
def load_files_from_folder(folder_path):
    return {file_doc: read_file(os.path.join(folder_path, file_doc)) 
            for file_doc in os.listdir(folder_path)}       

    
def load_all_files(energy_sector="residential", base_dir=None):
    if base_dir is None:
        if '__file__' in globals():
            base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            base_dir = os.getcwd()
    # Prevent double folder names if energy_sector is empty or already in base_dir
    if energy_sector and os.path.basename(os.path.normpath(base_dir)).lower() != energy_sector.lower():
        path = os.path.join(base_dir, energy_sector, "input_data")
    else:
        path = os.path.join(base_dir, "input_data")

    dfs_country_spe = {}  # Dict to hold df
    dfs_global = {}  # Dict to hold df

    if not os.path.exists(path):
        raise FileNotFoundError(f"The path {path} does not exist.")
    
    for folder_name in ['country_specific', 'global']:
        folder_path = os.path.join(path, folder_name)
        if os.path.exists(folder_path):
            if folder_name == "country_specific":
                dfs_country_spe = load_files_from_folder(folder_path)
            elif folder_name == 'global':
                dfs_global = load_files_from_folder(folder_path)
    return dfs_country_spe, dfs_global