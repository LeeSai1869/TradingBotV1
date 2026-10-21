"""Small scalar/array semantics shared by the translated Python features.

No Pine parser or eval runs in the application. Missing values propagate and
array bounds fail explicitly, rather than fabricating a usable market value.
"""
import math
import operator

NA=float('nan')
def is_na(x):return x is None or isinstance(x,float) and math.isnan(x)
def truth(x):return False if is_na(x) else bool(x)
def neg(x):return NA if is_na(x) else -x
_OPERATORS={'+':operator.add,'-':operator.sub,'*':operator.mul,'/':operator.truediv,'%':operator.mod,
            '==':operator.eq,'!=':operator.ne,'>':operator.gt,'<':operator.lt,'>=':operator.ge,'<=':operator.le}
def binary(op,a,b):
    if is_na(a) or is_na(b):return False if op in ('==','!=','>','<','>=','<=') else NA
    if op in ('/','%') and b==0:return NA
    return _OPERATORS[op](a,b)
def to_int(x):return NA if is_na(x) else int(x)
def to_float(x):return NA if is_na(x) else float(x)
def inclusive(a,b):
    if is_na(a) or is_na(b):return ()
    a,b=int(a),int(b)
    if abs(a-b)>100000:raise ValueError('Pine loop exceeds 100000 iterations')
    return range(a,b+(1 if b>=a else -1),1 if b>=a else -1)
def math_abs(x):return NA if is_na(x) else abs(x)
def math_max(*x):return NA if any(is_na(v) for v in x) else max(x)
def math_min(*x):return NA if any(is_na(v) for v in x) else min(x)
def math_sqrt(x):return NA if is_na(x) or x<0 else math.sqrt(x)
def math_floor(x):return NA if is_na(x) else math.floor(x)
def arr_new_float(size=0,value=NA):return [value]*int(size)
def arr_new_int(size=0,value=NA):return [value]*int(size)
def arr_new_bool(size=0,value=False):return [value]*int(size)
def arr_new_string(size=0,value=''):return [value]*int(size)
def arr_from_values(*values):return list(values)
def arr_size(a):return len(a)
def _index(a,i):
    if is_na(i) or int(i)!=i or not 0<=i<len(a):raise IndexError(f'Pine array index {i}; size {len(a)}')
    return int(i)
def arr_get(a,i):return a[_index(a,i)]
def arr_set(a,i,value):a[_index(a,i)]=value
def arr_push(a,value):a.append(value)
def arr_remove(a,i):return a.pop(_index(a,i))
def arr_clear(a):a.clear()
def arr_indexof(a,value):
    for i,v in enumerate(a):
        if binary('==',v,value):return i
    return -1
def arr_max(a):return max((v for v in a if not is_na(v)),default=NA)
def arr_min(a):return min((v for v in a if not is_na(v)),default=NA)
def str_length(value):return NA if is_na(value) else len(value)
def str_pos(value,sub):return NA if is_na(value) or is_na(sub) or sub not in value else value.index(sub)
def str_contains(value,sub):return False if is_na(value) or is_na(sub) else sub in value
def str_substring(value,start,end=None):return NA if is_na(value) or is_na(start) or end is not None and is_na(end) else value[int(start):None if end is None else int(end)]
def str_tonumber(value):
    try:return float(value)
    except (ValueError,TypeError):return NA
def str_tostring(value,pattern=None):
    if is_na(value):return 'NaN'
    if isinstance(value,bool):return 'true' if value else 'false'
    if pattern and set(pattern)=={'0'}:return str(int(value)).zfill(len(pattern))
    return str(value) if isinstance(value,str) else format(value,'.8f').rstrip('0').rstrip('.') if isinstance(value,float) else str(value)
def normalize(value,minimum,maximum,power=1.,higher=True):
    from Section_1_Global_Core.Data_Contracts_Legacy.market_definitions import normalize_relative
    result=normalize_relative(*(None if is_na(v) else v for v in (value,minimum,maximum)),power,higher)
    return NA if result is None else result

def clean(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    return value


def rma(state,key,value,length):
    """Shared Wilder seed/recurrence primitive; indicator kernels own their inputs."""
    part=state.setdefault(key,{'seed':[],'value':None})
    if not is_na(value):
        if part['value'] is None:
            part['seed'].append(value)
            if len(part['seed'])==length:part['value']=math.fsum(part['seed'])/length;part['seed']=[]
        else:
            alpha=1/length;part['value']=alpha*value+(1-alpha)*part['value']
    return NA if part['value'] is None else part['value']
