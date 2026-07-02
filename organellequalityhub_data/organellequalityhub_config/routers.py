SUPABASE_APPS = {'plastid_interaction', 'search_function', 'genome_map', 'organism_metadata'}


class SupabaseRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label in SUPABASE_APPS:
            return 'supabase'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label in SUPABASE_APPS:
            return 'supabase'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        if (obj1._meta.app_label in SUPABASE_APPS) == (obj2._meta.app_label in SUPABASE_APPS):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in SUPABASE_APPS:
            return db == 'supabase'
        return db == 'default'
