from sqlalchemy import text
from sqlmodel import Session

from app.db.models import NotificationChannel, NotificationTarget, Printer, SystemConfig


def test_credentials_are_encrypted_in_database(db_session: Session) -> None:
    printer = Printer(name="Encrypted printer", api_key="moonraker-secret")
    config = SystemConfig(
        id=1,
        s3_access_key="storage-user",
        s3_secret_key="storage-secret",
        makerworld_token="makerworld-secret",
    )
    channel = NotificationChannel(
        name="Encrypted webhook",
        target=NotificationTarget.WEBHOOK,
        config_json='{"url":"https://hooks.example/secret-token"}',
    )
    db_session.add(printer)
    db_session.add(config)
    db_session.add(channel)
    db_session.commit()

    raw_printer = db_session.exec(
        text("SELECT api_key FROM printers WHERE id = :id").bindparams(id=printer.id)
    ).one()[0]
    raw_config = db_session.exec(
        text("SELECT s3_secret_key, makerworld_token FROM system_config WHERE id = 1")
    ).one()
    raw_channel = db_session.exec(
        text("SELECT config_json FROM notification_channels WHERE id = :id").bindparams(
            id=channel.id
        )
    ).one()[0]

    assert raw_printer.startswith("enc:v1:")
    assert "moonraker-secret" not in raw_printer
    assert all(value.startswith("enc:v1:") for value in raw_config)
    assert "secret-token" not in raw_channel

    db_session.expire_all()
    assert db_session.get(Printer, printer.id).api_key == "moonraker-secret"
    assert db_session.get(SystemConfig, 1).s3_secret_key == "storage-secret"
    assert "secret-token" in db_session.get(NotificationChannel, channel.id).config_json


def test_legacy_plaintext_credentials_remain_readable(db_session: Session) -> None:
    db_session.exec(
        text(
            "INSERT INTO printers (name, provider, moonraker_url, status, api_key, "
            "created_at, updated_at) VALUES "
            "('Legacy', 'MOONRAKER', '', 'UNKNOWN', 'legacy-secret', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
    )
    db_session.commit()
    printer = db_session.exec(text("SELECT id FROM printers WHERE name = 'Legacy'")).one()

    assert db_session.get(Printer, printer[0]).api_key == "legacy-secret"
