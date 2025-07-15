import pandas as pd
from datetime import datetime

def transform_qb_to_df(report):
    rows = report.Rows.Row
    data = []
    for row in rows:
        if hasattr(row, "ColData"):
            values = [float(cell.value or 0) for cell in row.ColData if cell.value.replace(".", "", 1).isdigit()]
            if values:
                total = sum(values)
                data.append(total)

    df = pd.DataFrame({"y": data})
    df["ds"] = pd.date_range(end=datetime.today(), periods=len(df), freq="ME")
    return df
