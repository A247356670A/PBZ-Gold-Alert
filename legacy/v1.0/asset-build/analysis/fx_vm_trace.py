"""Symbolic output traces for the alert scripts, with register lifetimes retained."""
def output_expressions(code):
 regs={};outputs={}
 for ins in code:
  args=[('c',ix) if typ=='c' else regs.get(ix,('undefined',ix)) for typ,ix in ins['inputs']]
  if ins['op'].startswith('outputdata_'):
   outputs[(ins['op'],ins['dataset'],ins['attribute'])]=args[0]
  else:
   for index,dest in enumerate(ins['outputs']):
    if ins['op'].startswith('inputdata_'):expr=('input',ins['dataset'],ins['attribute'])
    elif ins['op']=='external_func_call':expr=('external',ins['function'],index,tuple(args))
    else:expr=(ins['op'],*args)
    regs[dest]=expr
 return outputs

def constants(expr):
 if expr[0]=='c':return {expr[1]}
 out=set()
 for v in expr[1:]:
  if isinstance(v,tuple):
   if v and isinstance(v[0],tuple):
    for e in v:out.update(constants(e))
   else:out.update(constants(v))
 return out
