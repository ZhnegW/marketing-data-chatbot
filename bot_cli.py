# bot_cli.py
from data_loader import load_df, data_coverage
from schema import QuerySpec, TimeSpec, SortSpec, Filter, PatchSpec
from executor import execute_query
from state import apply_patch
import pandas as pd
from llm_parser import parse_user_to_spec

def pretty_print(obj):
    import pandas as pd
    if obj is None:
        print("No data.")
        return
    if isinstance(obj, pd.DataFrame):
        print(obj.head(20).to_string(index=False))
        if len(obj) > 20:
            print(f"... ({len(obj)} rows)")
    else:
        print(obj)

def main():
    pd.options.display.float_format = '{:,.2f}'.format

    df = load_df("marketing_data.csv")
    print("Loaded dataset:", {k: str(v) for k,v in data_coverage(df).items()})

    last_spec: QuerySpec | None = None

    print("\nAsk questions in natural language. Type 'exit' to quit.\n")

    while True:
        q = input("User> ").strip()
        if q.lower() in {"exit","quit"}:
            break

        kind, spec_or_patch, raw = parse_user_to_spec(df, q, last_spec, model="gpt-4o-mini")

        if kind == "query":
            last_spec = spec_or_patch
        else:
            if last_spec is None:
                print("I need a previous query to apply this follow-up. Please ask a full question first.")
                continue
            last_spec = apply_patch(last_spec, spec_or_patch)

        result, note, sql = execute_query(df, last_spec)
        print("\n[Policy]", note)
        print("[SQL]", sql.replace("\n"," ").strip())
        # print("[Result]")
        # print(result if result is not None else "No data for this period/filters.")
        # Check for Empty DataFrames, None values, or NaN scalars
        def check_if_empty(res):
            if res is None: return True
            if isinstance(res, pd.DataFrame): return res.empty
            # Use pd.isna and ensure it returns only a Boolean value (handling scalar NaN)
            try:
                if pd.isna(res): return True
            except: 
                pass # If `res` is an object that cannot be checked for `isna`, skip it
            return False

        if check_if_empty(result):
            print("\n[Notice] 📭 No data found matching your criteria.")
            print(f"Advice: The current filters are {note}.")
            print("You can try: 'Clear all filters' or choose a different time range.")
        else:
            print("[Result]")
            pretty_print(result)
        
        print("-" * 60)

if __name__ == "__main__":
    main()
