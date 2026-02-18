# data_loader.py
import pandas as pd

def load_df(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    # Date
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    else:
        raise ValueError("Missing required column: Date")

    # Metrics
    for col in ["Revenue", "Cost"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            raise ValueError(f"Missing required column: {col}")

    # Year
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    else:
        raise ValueError("Missing required column: Year")

    # Basic sanity
    if df["Date"].isna().all():
        raise ValueError("All Date values failed to parse.")

    return df

def data_coverage(df: pd.DataFrame) -> dict:
    return {
        "min_date": df["Date"].min(),
        "max_date": df["Date"].max(),
        "min_year": int(df["Year"].min()) if df["Year"].notna().any() else None,
        "max_year": int(df["Year"].max()) if df["Year"].notna().any() else None,
        "rows": int(len(df)),
        "cols": int(df.shape[1]),
    }

if __name__ == "__main__":
    df = load_df("marketing_data.csv")
    print(data_coverage(df))
    print(df.head(3))
