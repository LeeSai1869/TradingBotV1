"""Section 4.2.1: current and previous raw price fields."""
from types import SimpleNamespace

NAME = 'price'
INPUTS = ('df',)
OUTPUT_FIELDS = ('c','o','h','l','c1','o1','h1','l1','current_price','prev_close')


def compute(df):
    values = {key: None for key in OUTPUT_FIELDS}
    if df is not None and not df.empty:
        for key,column in [('c','close'),('o','open'),('h','high'),('l','low')]:
            values[key] = float(df[column].iloc[-1])
            values[key+'1'] = float(df[column].iloc[-2]) if len(df)>1 else None
        values['current_price'] = values['c']
        values['prev_close'] = values['c1']
    return SimpleNamespace(**values)
