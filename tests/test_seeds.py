from app.extensions import db
from app.models import Role, Usuario, ZonaReunion, Configuracion, Area
from app.services.seeds import seed_defaults


def test_seed_defaults_in_production_creates_base_catalogs_without_demo_users(app):
    app.config["APP_ENV"] = "production"
    app.config["ALLOW_DEMO_SEED"] = False

    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_defaults()

        assert Role.query.count() >= 4
        assert Area.query.count() >= 4
        assert Configuracion.query.count() >= 1
        assert ZonaReunion.query.count() >= 3
        assert Usuario.query.filter_by(correo="admin@empresa.local").first() is None
        assert Usuario.query.filter_by(correo="secretaria.general@empresa.local").first() is None
        assert Usuario.query.filter_by(correo="usuario1.contabilidad@empresa.local").first() is None
