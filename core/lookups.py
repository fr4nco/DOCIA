from django.db.models import Lookup, CharField

class UnaccentIContains(Lookup):
    lookup_name = "unaccent_icontains"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"unaccent({lhs}) ILIKE unaccent('%%' || {rhs} || '%%')", lhs_params + rhs_params

CharField.register_lookup(UnaccentIContains)
