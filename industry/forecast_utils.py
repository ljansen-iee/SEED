# forecast_utils.py
import numpy as np  # Import numpy for numerical operations
from sklearn.linear_model import LinearRegression  # Import LinearRegression for linear trend prediction
import pandas as pd  # Import pandas for data manipulation

def predict_linear_trend(df, year_column, value_column, future_years):
    """
    Fits linear regression to data and predicts for future years.

    Parameters:
        df: DataFrame with year and value
        year_column: column name with years (e.g., "Year")
        value_column: column name with production values
        future_years: list of future years to predict

    Returns:
        forecast_df: DataFrame with columns ["Year", "Forecast", "Unit"]
    """
    # Prepare inputs
    df_sorted = df.sort_values(by=year_column)  # Sort the DataFrame by year
    X = df_sorted[year_column].values.reshape(-1, 1)  # Extract year values and reshape for sklearn
    y = df_sorted[value_column].values  # Extract production values

    # Train model
    model = LinearRegression()  # Create a LinearRegression model
    model.fit(X, y)  # Fit the model to the data

    # Predict future
    X_future = np.array(future_years).reshape(-1, 1)  # Prepare future years for prediction
    y_future = model.predict(X_future)  # Predict values for future years

    # Return as DataFrame
    return pd.DataFrame({
        "Year": future_years,  # Future years
        "Forecast": y_future   # Predicted values for those years
         })