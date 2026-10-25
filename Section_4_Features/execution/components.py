"""Trusted Python calculation units, dependencies and selective replay plans.

Parse local feature functions once at startup, never stored code or market data.
Top-level statements retain the original source order and feature file layout.
"""
import ast
from collections import defaultdict
import hashlib
import importlib
import inspect
import textwrap
from functools import lru_cache
import json
from pathlib import Path
from types import SimpleNamespace
from .context import Context,MANIFEST,HISTORY
from .contract import ALIASES,snake,canonical
from . import runtime as rt

BASELINE=Path(__file__).with_name('component_baseline.json')
ROOT=Path(__file__).resolve().parents[2]


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def stable_dump(node,*,include_attributes=False):
    """Freeze Python 3.12's AST representation across supported interpreters.

    Python 3.13+ omits empty optional lists in ast.dump by default. Those
    formatting changes are not calculation changes. Never hash that default.
    """
    if isinstance(node,ast.AST):
        fields=[]
        for name,value in ast.iter_fields(node):
            if value is not None or getattr(type(node),name,...) is not None:fields.append(name+'='+stable_dump(value))
        return type(node).__name__+'('+', '.join(fields)+')'
    if isinstance(node,list):return '['+', '.join(stable_dump(item) for item in node)+']'
    return repr(node)


def legacy_dump(node,*,include_attributes=False):
    """Reproduce the accidental Python 3.13/3.14 fingerprint for migration only."""
    if isinstance(node,ast.AST):
        fields=[]
        for name,value in ast.iter_fields(node):
            if value==[]:continue
            if value is not None or getattr(type(node),name,...) is not None:fields.append(name+'='+legacy_dump(value))
        return type(node).__name__+'('+', '.join(fields)+')'
    if isinstance(node,list):return '['+', '.join(legacy_dump(item) for item in node)+']'
    return repr(node)


def literal(value):
    if value is None or isinstance(value,(str,int,float,bool)):return value
    if isinstance(value,(list,tuple)):return [literal(v) for v in value]
    if isinstance(value,(set,frozenset)):return sorted((literal(v) for v in value),key=str)
    if isinstance(value,dict):return {str(k):literal(v) for k,v in value.items()}
    if inspect.isfunction(value) or inspect.isbuiltin(value):return ['callable',value.__module__,value.__qualname__]
    raise TypeError('not a literal dependency')


def globals_used(tree,namespace):
    result={}
    for n in ast.walk(tree):
        value=None;name=None
        if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id in namespace:
            value=namespace[n.id];name=n.id
        elif isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id in namespace:
            obj=namespace[n.value.id];value=getattr(obj,n.attr,None);name=n.value.id+'.'+n.attr
        if name is not None:
            try:result[name]=literal(value)
            except TypeError:pass
    return result


def function_hash(fn,seen=None,dumper=stable_dump):
    seen=set() if seen is None else seen
    if not inspect.isfunction(fn) or fn in seen:return ''
    seen.add(fn)
    tree=ast.parse(textwrap.dedent(inspect.getsource(fn)))
    imports={}
    for n in ast.walk(tree):
        if isinstance(n,ast.ImportFrom):
            try:
                mod=importlib.import_module('.'*n.level+(n.module or ''),fn.__module__.rpartition('.')[0])
                for alias in n.names:imports[alias.asname or alias.name]=getattr(mod,alias.name)
            except (ImportError,AttributeError):pass
    dependencies=[]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call):continue
        target=None
        if isinstance(n.func,ast.Name):target=imports.get(n.func.id,fn.__globals__.get(n.func.id))
        elif isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name):
            obj=imports.get(n.func.value.id,fn.__globals__.get(n.func.value.id))
            target=getattr(obj,n.func.attr,None)
        if inspect.isfunction(target):dependencies.append(function_hash(target,seen,dumper))
    return digest([dumper(tree,include_attributes=False),dependencies,globals_used(tree,fn.__globals__)])


@lru_cache(maxsize=None)
def source_hash(fn,dumper=stable_dump):return function_hash(fn,dumper=dumper)

def key(node):
    if isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant) and isinstance(node.slice.value,str):
        if isinstance(node.value,ast.Name) and node.value.id=='e':return node.slice.value
        if isinstance(node.value,ast.Attribute) and isinstance(node.value.value,ast.Name) and node.value.value.id=='e' and node.value.attr in ('values','persistent'):return node.slice.value
    return None


class Access(ast.NodeVisitor):
    def __init__(self,module):self.module=module;self.reads=set();self.writes=set();self.history=set();self.sites=set();self.helpers=set();self.visited=set();self.dispatch=False;self.assigned=set();self.external=set()
    def visit_Subscript(self,node):
        name=key(node)
        if name:
            if isinstance(node.ctx,ast.Store):self.writes.add(name);self.assigned.add(name)
            else:
                self.reads.add(name)
                if name not in self.assigned:self.external.add(name)
        self.generic_visit(node)
    def visit_Assign(self,node):
        self.visit(node.value)
        for target in node.targets:self.visit(target)
    def visit_For(self,node):
        self.visit(node.iter);before=set(self.assigned);self.visit(node.target)
        for statement in node.body:self.visit(statement)
        self.assigned=before
        for statement in node.orelse:self.visit(statement)
    def visit_While(self,node):
        self.visit(node.test);before=set(self.assigned)
        for statement in node.body:self.visit(statement)
        self.assigned=before
        for statement in node.orelse:self.visit(statement)
    def visit_If(self,node):
        self.visit(node.test);before=set(self.assigned)
        for statement in node.body:self.visit(statement)
        left=set(self.assigned);self.assigned=before
        for statement in node.orelse:self.visit(statement)
        self.assigned&=left
    def visit_Call(self,node):
        fn=node.func
        if isinstance(fn,ast.Attribute) and isinstance(fn.value,ast.Name) and fn.value.id=='e':
            if fn.attr=='input' and node.args and isinstance(node.args[0],ast.Constant):self.reads.add(node.args[0].value)
            if fn.attr in ('previous','initialize') and node.args and isinstance(node.args[0],ast.Constant):
                name=node.args[0].value
                if fn.attr=='previous':self.history.add(name);self.reads.add(name)
                else:self.writes.add(name);self.assigned.add(name)
            if fn.attr=='ta' and len(node.args)>1 and isinstance(node.args[0],ast.Constant):
                from ..features import trend,momentum,volatility,ema_structure
                ta=node.args[0].value;self.sites.add(node.args[1].value)
                helper={'ema':trend.calculate_ema,'rsi':momentum.calculate_rsi,'dmi':momentum.calculate_dmi,'atr':volatility.calculate,'wma':ema_structure.calculate_wma}.get(ta)
                if helper:self.helpers.add(helper)
                self.dispatch=True
        if isinstance(fn,ast.Attribute) and isinstance(fn.value,ast.Attribute) and isinstance(fn.value.value,ast.Name) and fn.value.value.id=='e':
            if fn.value.attr in ('values','persistent') and fn.attr=='update':self.writes.update(k.arg for k in node.keywords if k.arg)
            if fn.value.attr=='histories' and fn.attr=='get' and node.args and isinstance(node.args[0],ast.Constant):self.history.add(node.args[0].value)
        if isinstance(fn,ast.Attribute) and fn.attr in ('arr_set','arr_push','arr_remove','arr_clear') and node.args:
            name=key(node.args[0])
            if name:self.writes.add(name)
        target=None
        if isinstance(fn,ast.Name):target=getattr(self.module,fn.id,None)
        elif isinstance(fn,ast.Attribute) and isinstance(fn.value,ast.Name):target=getattr(getattr(self.module,fn.value.id,None),fn.attr,None)
        if inspect.isfunction(target):
            self.helpers.add(target)
            if target.__module__==self.module.__name__ and target not in self.visited:
                self.visited.add(target);self.visit(ast.parse(textwrap.dedent(inspect.getsource(target))))
        self.generic_visit(node)


class Catalog:
    def __init__(self,dumper=stable_dump):
        infrastructure=digest([dumper(ast.parse(textwrap.dedent(inspect.getsource(fn))),include_attributes=False) for fn in (Context.begin,Context.finish,Context.previous,Context.__getitem__,Context.__setitem__,Context.initialize,Context.daily,canonical)])
        self.units=[];self.modules={};self.producers=defaultdict(list)
        contract_types=dict(MANIFEST['contract'])
        export_aliases={'vwapValue':'vwap','nearestSupportPrice':'nearestSupport','nearestResistancePrice':'nearestResistance','prevDayHigh':'previousDayHigh','prevDayLow':'previousDayLow'}
        from .engine import EXTRA_STEP,EXTRA_FIELDS
        for step in [{'module':'Section_4_Features.execution.memory','function':'update'},*MANIFEST['steps'],EXTRA_STEP]:
            name=step['module'] if '.' in step['module'] else 'Section_4_Features.features.'+step['module']
            module=importlib.import_module(name);self.modules[name]=module
            tree=ast.parse(inspect.getsource(getattr(module,step['function'])))
            counts=defaultdict(int)
            for statement in tree.body[0].body:
                access=Access(module);access.visit(statement)
                label=','.join(sorted(access.writes)) or dumper(statement,include_attributes=False)[:70]
                counts[label]+=1;uid=f'{name}:{label}:{counts[label]}'
                source=digest([infrastructure,globals_used(statement,module.__dict__),[(w,contract_types.get(export_aliases.get(w,w)),w in HISTORY) for w in sorted(access.writes)],
                               sorted((a,v) for a,v in ALIASES.items() if v in {snake(w) for w in access.writes}),dumper(statement,include_attributes=False),sorted(source_hash(f,dumper) for f in access.helpers),dumper(ast.parse(textwrap.dedent(inspect.getsource(Context.ta))),include_attributes=False) if access.dispatch else None])
                unit=SimpleNamespace(id=uid,module=name,statement=statement,source=source,**{k:getattr(access,k) for k in ('reads','writes','history','sites','external')})
                unit.guaranteed=set(access.assigned)
                self.units.append(unit)
                for output in unit.writes:self.producers[output].append(uid)
        # MTF helpers run before the numbered feature functions.
        from ..features.vwap import session_value
        from ..features.volume import moving_average
        for uid,output,fn,params in [('context:vwap','mtfData.vwapValue',session_value,set()),('context:volume','mtfData.volumeMA',moving_average,{'volumeLookback'})]:
            unit=SimpleNamespace(id=uid,module='context',statement=None,source=function_hash(fn,dumper=dumper),reads=params,writes={output},history=set(),sites=set(),external=params,guaranteed={output})
            self.units.insert(0,unit);self.producers[output].append(uid)
        self.by_id={u.id:u for u in self.units};self.edges=defaultdict(set);self.requires=defaultdict(lambda:defaultdict(set));self.fallback=defaultdict(set)
        shared=set(HISTORY)|set(MANIFEST['persistent'])|{n for n,_ in MANIFEST['contract']}
        latest={};local={}
        for u in self.units:
            for field in u.external:
                source=local.get((u.module,field),latest.get(field))
                if source and source!=u.id:
                    self.edges[source].add(u.id);self.requires[u.id][field].add(source)
            for field in u.history:
                for source in self.producers.get(field,[]):
                    if source!=u.id:
                        self.edges[source].add(u.id);self.requires[u.id][field].add(source)
            for field in u.writes:
                previous=local.get((u.module,field),latest.get(field))
                if previous and previous!=u.id and field not in u.guaranteed:self.fallback[u.id].add(previous)
                if field in shared and field in latest and latest[field]!=u.id and field not in u.guaranteed:self.edges[latest[field]].add(u.id)
                local[u.module,field]=u.id
                latest[field]=u.id
        # A persistent write can change consumers earlier in the next candle.
        # Forward-only dependencies miss state-machine feedback (e.g. a BOS
        # cleanup changing the next candle's protected levels/foundations).
        persistent=set(MANIFEST['persistent'])|{'lastStructureResetBar'}
        for unit in self.units:
            for field in unit.reads & persistent:
                for producer in self.producers.get(field,()):
                    if producer!=unit.id:
                        self.edges[producer].add(unit.id)
                        self.requires[unit.id][field].add(producer)
        self.final=dict(latest)
        # Context.begin carries the prior regime into Section 5.
        for source in self.producers.get('regimeState',[]):
            for u in self.units:
                if 'lastRegime' in u.reads:self.edges[source].add(u.id)
        self.source={u.id:u.source for u in self.units}
        self.source_revision=digest(self.source)
        self.export={name:snake(name) for name,_ in MANIFEST['contract']}
        self.export.update(vwapValue='vwap',nearestSupportPrice='nearest_support',nearestResistancePrice='nearest_resistance',prevDayHigh='previous_day_high',prevDayLow='previous_day_low',prevCandleRange='prev_candle_range')
        for field in ('controlState','energyState','regimeState','fatigueState','trendState','transitionState'):self.export[field]=snake(field)
        self.export.update({field:snake(field) for field in EXTRA_FIELDS})
        self.export_inverse={column:field for field,column in self.export.items()}

    def changed(self,sources,old_parameters,new_parameters):
        changed={u.id for u in self.units if sources.get(u.id)!=u.source or any(old_parameters.get(k)!=new_parameters.get(k) for k in u.reads if k in old_parameters or k in new_parameters)}
        # Removed producers can invalidate consumers/outputs through their old
        # feature module. Never silently retain data from a deleted formula.
        for removed in sources.keys()-self.source.keys():
            module=removed.split(':',1)[0]
            changed.update(u.id for u in self.units if u.module==module)
        while True:
            expanded=changed|{v for u in changed for v in self.edges[u]}
            if expanded==changed:return changed
            changed=expanded

    def plan(self,changed):
        return self._plan(frozenset(changed))

    @lru_cache(maxsize=32)
    def _plan(self,changed):
        changed=set(changed)
        while True:
            expanded=changed|{v for u in changed for v in self.edges[u]}
            if expanded==changed:break
            changed=expanded
        execute=set(changed)
        # Internal arrays/intermediates absent from stored rows require their
        # producing calculations; exported prerequisites are hydrated instead.
        while True:
            required=set(execute)
            for uid in execute:
                u=self.by_id[uid]
                required.update(self.fallback[uid])
                for field in u.reads|u.history:
                    if field in self.export or field.startswith(('mtfData.','barstate.','timeframe.','syminfo.')):continue
                    required.update(self.requires[uid].get(field,()))
            if required==execute:break
            execute=required
        writes=set().union(*(self.by_id[u].writes for u in changed)) if changed else set()
        columns={self.export[w] for w in writes if w in self.export and self.final.get(w) in changed}
        for alias,source in ALIASES.items():
            if source in columns:columns.add(alias)
        for field in ('atr','ema7','ema25','ema50','ema100','ema200','ema300'):
            if field in writes and self.final.get(field) in changed:columns.add('prev_'+field)
        if any(self.by_id[u].module.endswith('.daily_levels') for u in changed):columns.add('daily_source_ready')
        for side,prefix in [('support','support'),('resistance','resistance'),('inst_support','instSupport'),('inst_resistance','instResistance')]:
            identifier='nearest'+prefix[0].upper()+prefix[1:]+'ZoneID'
            if writes&{prefix+'LowArray',prefix+'HighArray',prefix+'ZoneIDArray',identifier}:columns.update(f'{side}_zone_{edge}' for edge in ('low','high'))
        executed_writes=set().union(*(self.by_id[u].writes for u in execute))
        shadowed={field for field in executed_writes if field in self.export and self.final.get(field) not in execute}
        functions=[]
        for name,module in self.modules.items():
            body=[]
            for u in self.units:
                if u.module!=name:continue
                if u.id in execute:body.append(u.statement)
                else:
                    for field in u.writes&shadowed:
                        if self.final.get(field)==u.id:
                            body.append(ast.Expr(value=ast.Call(func=ast.Name(id='_hydrate',ctx=ast.Load()),args=[ast.Name(id='e',ctx=ast.Load()),ast.Constant(field),ast.Constant(self.export[field])],keywords=[])))
            if not body:continue
            function=ast.FunctionDef(name='_selective_update',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='e')],kwonlyargs=[],kw_defaults=[],defaults=[]),body=body,decorator_list=[])
            from . import fast
            function.body=fast.optimize(function.body,name)
            tree=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]));namespace={**module.__dict__,**fast.HELPERS};namespace['_hydrate']=hydrate
            exec(compile(tree,module.__file__,'exec'),namespace)
            functions.append(namespace['_selective_update'])
        return SimpleNamespace(changed=changed,execute=execute,shadowed=shadowed,writes=writes,columns=columns,functions=functions,
                               state_writes=set().union(*(self.by_id[u].writes for u in execute)),
                               reads=set().union(*(self.by_id[u].reads for u in execute)),
                               history_keys=(set().union(*(self.by_id[u].history|self.by_id[u].writes for u in execute))&HISTORY),sites=set().union(*(self.by_id[u].sites for u in execute)))

_CATALOG=None

def catalog():
    global _CATALOG
    if _CATALOG is None:_CATALOG=Catalog()
    return _CATALOG


@lru_cache(maxsize=1)
def baseline_sources():
    data=json.loads(BASELINE.read_text())
    return data['sources'],data['source_sha256']


def desired_parameters():return Context('_revision_','1m').parameters

def current_signature():return digest([catalog().source_revision,desired_parameters()])


def hydrate(e,field,column):
    value=e._stored.get(column)
    e.values[field]=rt.NA if value is None else value


@lru_cache(maxsize=1)
def legacy_runtime_sources():
    return Catalog(dumper=legacy_dump).source
