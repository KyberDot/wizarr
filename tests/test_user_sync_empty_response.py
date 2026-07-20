"""An empty remote user list must not delete every local user.

list_users() runs automatically when the Users page loads (admin/users.html has a
hidden hx-get with hx-trigger="load"). It guards against the request raising, but
a successful response that yields no users was treated as "the admin unshared
everyone" and pruned every local row.
"""

from unittest.mock import Mock, PropertyMock, patch

from app.models import MediaServer, User
from app.services.media.plex import PlexClient


def _server(session):
    server = MediaServer(
        name="Plex", server_type="plex", url="http://plex.local", api_key="token"
    )
    session.add(server)
    session.commit()
    return server


def _users(session, server, emails):
    for email in emails:
        session.add(
            User(
                email=email,
                username=email.split("@")[0],
                token="None",
                code="None",
                server_id=server.id,
            )
        )
    session.commit()


def _client(server):
    """Build a PlexClient without touching the network."""
    client = PlexClient.__new__(PlexClient)
    client.server_id = server.id
    return client


def _emails(server):
    return {u.email for u in User.query.filter_by(server_id=server.id).all()}


def test_empty_remote_list_does_not_delete_local_users(session):
    """The reported failure: a successful response with zero users wiped the table."""
    server = _server(session)
    _users(session, server, ["a@example.com", "b@example.com"])
    client = _client(server)

    # spec'd deliberately: a bare Mock auto-creates any attribute, which hides
    # typos like self.server.name (PlexServer exposes friendlyName, not name)
    fake_server = Mock(spec=["machineIdentifier", "friendlyName"])
    fake_server.machineIdentifier = "mid"
    with (
        patch.object(PlexClient, "admin", new_callable=PropertyMock) as admin,
        patch.object(PlexClient, "server", new_callable=PropertyMock) as srv,
        patch.object(PlexClient, "_filter_users_for_server", return_value={}),
    ):
        admin.return_value.users.return_value = []
        srv.return_value = fake_server
        PlexClient.list_users.__wrapped__(client)

    assert _emails(server) == {"a@example.com", "b@example.com"}


def test_genuine_removal_still_prunes(session):
    """A non-empty remote set must still drop users that are no longer shared."""
    server = _server(session)
    _users(session, server, ["keep@example.com", "gone@example.com"])
    client = _client(server)

    # spec'd deliberately: a bare Mock auto-creates any attribute, which hides
    # typos like self.server.name (PlexServer exposes friendlyName, not name)
    fake_server = Mock(spec=["machineIdentifier", "friendlyName"])
    fake_server.machineIdentifier = "mid"
    keeper = Mock(title="keep")
    with (
        patch.object(PlexClient, "admin", new_callable=PropertyMock) as admin,
        patch.object(PlexClient, "server", new_callable=PropertyMock) as srv,
        patch.object(
            PlexClient,
            "_filter_users_for_server",
            return_value={"keep@example.com": keeper},
        ),
        patch.object(PlexClient, "_sync_user_permissions", return_value=None),
    ):
        admin.return_value.users.return_value = [keeper]
        srv.return_value = fake_server
        PlexClient.list_users.__wrapped__(client)

    assert _emails(server) == {"keep@example.com"}
