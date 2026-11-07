"""Additional native structs needed for the gauntlet renderer and soft paths."""
from parse_fx import FXParser

class FX202(FXParser):
    def value(self,t):
        start=self.p
        if t==('Struct','IntVector2'):v=self.take('ii')
        elif t==('Struct','Transform'):v=self.take('dddddddddd')
        elif t==('SoftObject',):v=dict(package=self.value(('Name',)),asset=self.value(('Name',)),subpath=self.string())
        else:return super().value(t)
        self.records.append(dict(kind='value',type=t,start=start,end=self.p,parent=self.stack[-1]if self.stack else None,value=v))
        return v
