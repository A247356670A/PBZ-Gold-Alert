"""Typed native fields used by attribute effects; no changes to historical parsers."""
from fx_parser_v202 import FX202
class FX205(FX202):
    def value(self,t):
        if t==('Struct','GameplayTagContainer'):
            start=self.p;count=self.take('I');assert count<1000
            v=dict(GameplayTags=[self.value(('Name',))for _ in range(count)])
            self.records.append(dict(kind='value',type=t,start=start,end=self.p,parent=self.stack[-1]if self.stack else None,value=v))
            return v
        if t==('FieldPath',):
            start=self.p;count=self.take('I');assert count<20
            v=dict(path=[self.value(('Name',))for _ in range(count)],owner=self.take('i'))
            self.records.append(dict(kind='value',type=t,start=start,end=self.p,parent=self.stack[-1]if self.stack else None,value=v))
            return v
        return super().value(t)
