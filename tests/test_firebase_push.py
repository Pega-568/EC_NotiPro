import pytest
from unittest.mock import patch, MagicMock

from firebase_admin import messaging
from app.services.notifications import _send_push
from app.models import DeviceToken
from app.extensions import db


def test_send_push_disabled(app):
    with app.app_context():
        app.config["FCM_ENABLED"] = False
        result = _send_push("fake-token", "meeting_created", {"meeting_id": 1})
        assert result["result"] == "fallido"
        assert result["detail"] == "fcm_disabled"


def test_send_push_no_credentials(app):
    with app.app_context():
        app.config["FCM_ENABLED"] = True
        app.config["FCM_SERVICE_ACCOUNT_PATH"] = ""
        result = _send_push("fake-token", "meeting_created", {"meeting_id": 1})
        assert result["result"] == "fallido"
        assert result["detail"] == "fcm_http_v1_not_configured"


@patch("app.services.notifications.firebase_admin")
@patch("app.services.notifications.credentials.Certificate")
@patch("app.services.notifications.messaging.send")
def test_send_push_success(mock_send, mock_certificate, mock_firebase_admin, app):
    with app.app_context():
        app.config["FCM_ENABLED"] = True
        app.config["FCM_SERVICE_ACCOUNT_PATH"] = "fake-path.json"
        mock_firebase_admin._apps = {"[DEFAULT]": True}
        
        result = _send_push("fake-token", "meeting_created", {"meeting_id": 1})
        
        assert result["result"] == "enviado"
        assert result["detail"] == "fcm_sent"
        mock_send.assert_called_once()
        
        message_arg = mock_send.call_args[0][0]
        assert message_arg.notification.title == "EC_NotiPro"
        assert message_arg.notification.body == "Nueva actualización de reunión. Abra la app para revisar los detalles."
        assert message_arg.data["type"] == "meeting_created"
        assert message_arg.data["meeting_id"] == "1"
        assert message_arg.data["title"] == "EC_NotiPro"
        assert message_arg.data["body"] == "Nueva actualización de reunión. Abra la app para revisar los detalles."
        assert message_arg.data["channel_id"] == "reuniones"


@patch("app.services.notifications.firebase_admin")
@patch("app.services.notifications.credentials.Certificate")
@patch("app.services.notifications.messaging.send")
def test_send_push_invalid_token(mock_send, mock_certificate, mock_firebase_admin, app):
    with app.app_context():
        app.config["FCM_ENABLED"] = True
        app.config["FCM_SERVICE_ACCOUNT_PATH"] = "fake-path.json"
        mock_firebase_admin._apps = {"[DEFAULT]": True}
        
        # Simular que send lanza UnregisteredError
        mock_send.side_effect = messaging.UnregisteredError("Token not registered")
        
        # Crear un token ficticio en BD
        dt = DeviceToken(usuario_id=1, token="invalid-token", plataforma="android", estado="Activo")
        db.session.add(dt)
        db.session.commit()
        
        result = _send_push("invalid-token", "meeting_created", {"meeting_id": 1})
        
        assert result["result"] == "token_invalido"
        assert result["detail"] == "firebase_unregistered"
        
        # Verificar que se actualizó el token
        updated_dt = db.session.get(DeviceToken, dt.id)
        assert updated_dt.estado == "Inactivo"


@patch("app.services.notifications.firebase_admin")
@patch("app.services.notifications.credentials.Certificate")
@patch("app.services.notifications.messaging.send")
def test_send_push_firebase_error(mock_send, mock_certificate, mock_firebase_admin, app):
    with app.app_context():
        app.config["FCM_ENABLED"] = True
        app.config["FCM_SERVICE_ACCOUNT_PATH"] = "fake-path.json"
        mock_firebase_admin._apps = {"[DEFAULT]": True}
        
        # Simular otro error
        mock_send.side_effect = Exception("Unknown Firebase Error")
        
        result = _send_push("fake-token", "meeting_created", {"meeting_id": 1})
        
        assert result["result"] == "fallido"
        assert result["detail"] == "firebase_error"
