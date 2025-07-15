import pandas as pd
from datetime import datetime

def transform_qb_to_df(report):
    report_data = report.get("Rows", {}).get("Row", [])
    data = []

    for row in report_data:
        if "Summary" in row:
            continue

        columns = row.get("ColData", [])
        if len(columns) >= 2:
            date = columns[0].get("value")
            amount = float(columns[1].get("value", 0))
            data.append({"ds": date, "y": amount})

    return pd.DataFrame(data)
