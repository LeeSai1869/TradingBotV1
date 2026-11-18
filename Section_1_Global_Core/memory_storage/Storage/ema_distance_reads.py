"""SQL adapters for ten EMA derivatives. This phase leaves storage unchanged."""
from Section_4_Features.execution.ema_distances import FIELDS,PERIODS


def expression(field,prefix='f',*,preserve_legacy=True):
    price=f'{prefix}.c'
    def percentage(distance,denominator):
        return f'((1.0*({distance}))/NULLIF({denominator},0))*100.0'
    formulas={f'ema{period}_distance_pct':percentage(f'abs({price}-{prefix}.ema{period})',price)
              for period in (50,200,300)}
    formulas['ema50_200_gap_pct']=(f'CASE WHEN {prefix}.ema200 IS NULL OR {prefix}.ema200=0 '
        f'THEN 0.0 ELSE {percentage(f"abs({prefix}.ema50-{prefix}.ema200)",f"{prefix}.ema200")} END')
    candidates=' UNION ALL '.join(
        f'SELECT {prefix}.ema{period} AS value,abs({prefix}.ema{period}-{price}) AS distance,{index} AS ordinal'
        for index,period in enumerate(PERIODS))
    for side,operator in (('buy','>'),('sell','<')):
        nearest=f'(SELECT value FROM ({candidates}) WHERE value{operator}{price} ORDER BY distance,ordinal LIMIT 1)'
        distance=f'abs(({nearest})-{price})'
        formulas[f'nearest_{side}_ema']=nearest
        formulas[f'nearest_{side}_ema_distance']=distance
        formulas[f'nearest_{side}_ema_distance_pct']=percentage(distance,price)
    value=formulas[field]
    # Match rt.clean for infinities/overflow as well as ordinary nulls.
    value=f'(CASE WHEN abs(({value}))<=1.7976931348623157e308 THEN ({value}) ELSE NULL END)'
    if preserve_legacy:
        value=f'(CASE WHEN {prefix}.formula_version=3 THEN {value} ELSE {prefix}."{field}" END)'
    return value+f' AS "{field}"'
