"""
Regression test: the invite-table server filter must actually filter.

Selecting a server in the Invitations view posted the server id, but the handler
rebuilt the query without applying any filter — so every server showed all
invitations. The handler now restricts the query to invitations linked to the
selected server through the association table.
"""

import pytest

from app.extensions import db
from app.models import AdminAccount, Invitation, MediaServer


@pytest.fixture
def admin_user(app):
    """Create an admin account for authenticated requests."""
    with app.app_context():
        created = False
        previous_hash = None
        admin = AdminAccount.query.filter_by(username="testadmin").first()
        if not admin:
            admin = AdminAccount(username="testadmin")
            admin.set_password("TestPass123")
            db.session.add(admin)
            db.session.commit()
            created = True
        else:
            previous_hash = admin.password_hash
            admin.set_password("TestPass123")
            db.session.commit()
        yield admin
        if created:
            db.session.delete(admin)
            db.session.commit()
        elif previous_hash is not None:
            admin = AdminAccount.query.filter_by(username="testadmin").first()
            if admin:
                admin.password_hash = previous_hash
                db.session.commit()


def test_invite_table_filters_by_server(client, app, admin_user):
    """Filtering by a server returns only that server's invitations."""
    with app.app_context():
        srv_a = MediaServer(
            name="Server A", server_type="plex", url="http://a", api_key="ka"
        )
        srv_b = MediaServer(
            name="Server B", server_type="jellyfin", url="http://b", api_key="kb"
        )
        db.session.add_all([srv_a, srv_b])
        db.session.commit()

        inv_a = Invitation(code="ONSERVERA", used=False, unlimited=False)
        inv_a.servers.append(srv_a)
        inv_b = Invitation(code="ONSERVERB", used=False, unlimited=False)
        inv_b.servers.append(srv_b)
        db.session.add_all([inv_a, inv_b])
        db.session.commit()
        a_id = srv_a.id

    client.post("/login", data={"username": "testadmin", "password": "TestPass123"})

    response = client.post("/invite/table", data={"server": str(a_id)})
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "ONSERVERA" in body
    assert "ONSERVERB" not in body
