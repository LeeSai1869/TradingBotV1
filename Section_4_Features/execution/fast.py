"""Verified execution-only kernels; the reviewed feature AST stays authoritative.

Only exact known loop ASTs are replaced; OB truth wrappers are removed only
when their argument is proven boolean. A loop source edit automatically falls back
to the original loop. Outputs, scratch values, NA semantics and checkpoints stay
identical, so optimization never changes formula fingerprints or replay cursors.
"""
import ast
import hashlib
import inspect
import textwrap
from functools import lru_cache
from . import runtime as rt


def liquidity_clusters(e):
    highs=list(reversed(e.histories.get('h',())))[:50]
    lows=list(reversed(e.histories.get('l',())))[:50]
    high=e['externalHighLiquidity'];low=e['externalLowLiquidity'];close=e['c'];tolerance=e['liquidityClusterTolerance']
    hc=e['highClusterCount'];lc=e['lowClusterCount']
    if not rt.is_na(close) and close!=0 and not rt.is_na(tolerance):
        if not rt.is_na(high):
            for value in highs:
                if not rt.is_na(value) and abs(value-high)/close<=tolerance:hc=rt.binary('+',hc,1)
        if not rt.is_na(low):
            for value in lows:
                if not rt.is_na(value) and abs(value-low)/close<=tolerance:lc=rt.binary('+',lc,1)
    e['highClusterCount']=hc;e['lowClusterCount']=lc;e['i']=50


def liquidity_ages(e):
    limit=e['externalLiquidityLookback']
    # Retain the strict inclusive-bound validation (including descending loops).
    indices=rt.inclusive(1,limit)
    highs=list(reversed(e.histories.get('h',())));lows=list(reversed(e.histories.get('l',())))
    high=e['externalHighLiquidity'];low=e['externalLowLiquidity'];close=e['c']
    ha=e['highLiquidityAge'];la=e['lowLiquidityAge']
    if not rt.is_na(close) and close!=0:
        for i in indices:
            # The reviewed loop uses positive indices; unusual descending bounds
            # retain the original previous() semantics rather than Python [-1].
            h=highs[i-1] if 0<i<=len(highs) else e.previous('h',i)
            l=lows[i-1] if 0<i<=len(lows) else e.previous('l',i)
            if rt.is_na(ha) and not rt.is_na(high) and not rt.is_na(h) and abs(h-high)/close<.0005:ha=i
            if rt.is_na(la) and not rt.is_na(low) and not rt.is_na(l) and abs(l-low)/close<.0005:la=i
            if not rt.is_na(ha) and not rt.is_na(la):break
    e['highLiquidityAge']=ha;e['lowLiquidityAge']=la
    if indices:e['i']=indices[-1]


LOOPS={
    '229101549af3e3816527fc15ecf9f1b33dd1d097f7059117de31ce9cdfac67dc':'_fast_clusters',
    '218fafbd80e897f2852792a98655a44dbd86755aa4a013757dad68da5b2d698b':'_fast_ages',
}
HELPERS={'_fast_clusters':liquidity_clusters,'_fast_ages':liquidity_ages}


def semantics():
    from .context import Context
    return tuple(getattr(rt,name) for name in ('binary','truth','is_na','math_abs','math_min','math_max','inclusive'))+(Context.previous,)


@lru_cache(maxsize=8)
def compatible(functions):
    from .components import stable_dump
    try:
        code=''.join(stable_dump(ast.parse(textwrap.dedent(inspect.getsource(fn)))) for fn in functions)
    except (OSError,TypeError):return False
    return hashlib.sha256(code.encode()).hexdigest()=='ac3913d429d5d484772777f578352c938fdb6bc2619c0a08c884804b642a4a03'


def optimize(body,module_name):
    if module_name not in ('Section_4_Features.features.liquidity','Section_4_Features.features.volume_profile','Section_4_Features.features.order_blocks'):return body
    if not compatible(semantics()):return body
    from .components import stable_dump
    if module_name=='Section_4_Features.features.order_blocks':
        import copy
        return [BooleanTruth().visit(copy.deepcopy(node)) for node in body]
    class Replace(ast.NodeTransformer):
        def visit_For(self,node):return self.loop(node)
        def visit_While(self,node):return self.loop(node)
        def loop(self,node):
            helper=LOOPS.get(hashlib.sha256(stable_dump(node).encode()).hexdigest())
            if helper:
                return ast.copy_location(ast.Expr(value=ast.Call(func=ast.Name(id=helper,ctx=ast.Load()),args=[ast.Name(id='e',ctx=ast.Load())],keywords=[])),node)
            return self.generic_visit(node)
    # Do not mutate the original calculation AST retained in the dependency graph.
    import copy
    return [Replace().visit(copy.deepcopy(node)) for node in body]


@lru_cache(maxsize=32)
def _compiled(fn,semantics_key):
    tree=ast.parse(textwrap.dedent(inspect.getsource(fn)))
    tree.body[0].body=optimize(tree.body[0].body,fn.__module__)
    namespace={**fn.__globals__,**HELPERS}
    exec(compile(ast.fix_missing_locations(tree),fn.__code__.co_filename,'exec'),namespace)
    from types import FunctionType
    fn.__globals__.update(HELPERS)
    return FunctionType(namespace[fn.__name__].__code__,fn.__globals__,fn.__name__,fn.__defaults__,fn.__closure__)


def resolve(module,name):
    fn=getattr(module,name)
    if module.__name__ not in ('Section_4_Features.features.liquidity','Section_4_Features.features.volume_profile','Section_4_Features.features.order_blocks') or not inspect.isfunction(fn) or fn.__module__!=module.__name__ or fn.__closure__:return fn
    return _compiled(fn,semantics())


def vp_poc(e):
    bins=e['vpVolumeBins'];maximum=e['maxVolume'];index=e['pocIndex']
    for i in rt.inclusive(0,rt.binary('-',e['vpBins'],1)):
        value=rt.arr_get(bins,i)
        if not rt.is_na(value) and not rt.is_na(maximum) and value>maximum:maximum=value;index=i
        e['i']=i;e['binVol']=value
    e['maxVolume']=maximum;e['pocIndex']=index


def vp_total(e):
    bins=e['vpVolumeBins'];total=e['totalVPVolume']
    for i in rt.inclusive(0,rt.binary('-',e['vpBins'],1)):
        total=rt.binary('+',total,rt.arr_get(bins,i));e['i']=i
    e['totalVPVolume']=total


def vp_area(e):
    bins=e['vpVolumeBins'];last=e['vpBins']-1
    lo=e['vaLowIndex'];hi=e['vaHighIndex'];volume=e['accumulatedVolume'];target=e['valueTarget'];base=e['vpLow'];size=e['vpBinSize']
    while not rt.is_na(volume) and not rt.is_na(target) and volume<target and (lo>0 or hi<last):
        left=rt.arr_get(bins,lo-1) if lo>0 else 0
        right=rt.arr_get(bins,hi+1) if hi<last else 0
        if lo>0 and (hi==last or (not rt.is_na(left) and not rt.is_na(right) and left>=right)):
            lo-=1;volume=rt.binary('+',volume,left)
        else:hi+=1;volume=rt.binary('+',volume,right)
        e['leftVol']=left;e['rightVol']=right
        e['vaLowIndex']=lo;e['vaHighIndex']=hi;e['accumulatedVolume']=volume
        e['vpVALow']=base+lo*size;e['vpVAHigh']=base+(hi+1)*size


def vp_nodes(e):
    bins=e['vpVolumeBins'];base=e['vpLow'];size=e['vpBinSize'];hvn=e['hvnThreshold'];lvn=e['lvnThreshold']
    hl=e['vpHVNLow'];hh=e['vpHVNHigh'];ll=e['vpLVNLow'];lh=e['vpLVNHigh']
    for i in rt.inclusive(0,rt.binary('-',e['vpBins'],1)):
        volume=rt.arr_get(bins,i);low=base+i*size;high=base+(i+1)*size
        if not rt.is_na(volume):
            if not rt.is_na(hvn) and volume>=hvn:
                hl=low if rt.is_na(hl) else rt.math_min(hl,low);hh=high if rt.is_na(hh) else rt.math_max(hh,high)
            if not rt.is_na(lvn) and volume<=lvn:
                ll=low if rt.is_na(ll) else rt.math_min(ll,low);lh=high if rt.is_na(lh) else rt.math_max(lh,high)
        e['i']=i;e['binVol']=volume;e['binLow']=low;e['binHigh']=high
    e['vpHVNLow']=hl;e['vpHVNHigh']=hh;e['vpLVNLow']=ll;e['vpLVNHigh']=lh


LOOPS.update({
 '120c0b4fe24f0b5ded90eb0bcbede2d4e7fb68c718a31a5c8211b10db6809ac5':'_fast_poc',
 '3525cad9f92bb342dcb5d9b9e9e192f8cd2e03b73daa079071df97bc52a87820':'_fast_total',
 '5fa3b9c31de26f51c7a7c80669fb78f0f34118f95802083259642f4ce3f9326e':'_fast_area',
 'fbfca450100d5808d9bd69cf98e1c621cfbf00fdb25bcaf12ddd4fc24ce42bf2':'_fast_nodes',
})
HELPERS.update(_fast_poc=vp_poc,_fast_total=vp_total,_fast_area=vp_area,_fast_nodes=vp_nodes)


class BooleanTruth(ast.NodeTransformer):
    """Remove truth() only around expressions proven to return Python bool.

    Never infer types of context fields, replace NA comparisons, or reorder
    operands. Runtime compatibility is checked by optimize() before this runs.
    """
    @staticmethod
    def boolean(node):
        if isinstance(node,ast.Constant):return type(node.value) is bool
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):return True
        if isinstance(node,ast.BoolOp):return all(BooleanTruth.boolean(v) for v in node.values)
        return (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                and isinstance(node.func.value,ast.Name) and node.func.value.id=='rt'
                and node.func.attr in ('truth','is_na'))
    def visit_Call(self,node):
        node=self.generic_visit(node)
        if (isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name)
                and node.func.value.id=='rt' and node.func.attr=='truth'
                and len(node.args)==1 and not node.keywords and self.boolean(node.args[0])):
            return ast.copy_location(node.args[0],node)
        return node
