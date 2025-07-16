import pandas as pd

def read_operation_data_excel(file_path):
    # Create an empty dictionary to store DataFrames
    d_op = {}

    # Read the Excel file with multiple sheets
    xl = pd.ExcelFile(file_path)

    # Loop through each sheet in the Excel file
    for sheet_name in xl.sheet_names:
        # Read each sheet as a DataFrame
        df = xl.parse(sheet_name)
        
        # Store the DataFrame in the dictionary with sheet name as key
        d_op[sheet_name] = df

    return d_op