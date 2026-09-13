"""Shared builders for hermetic tests."""

from __future__ import annotations


def make_vpn_service(client, ip_service):
    from hotspotshield_gui.services.connection_verifier import ConnectionVerifier
    from hotspotshield_gui.services.vpn_service import VpnService

    return VpnService(
        client,
        ip_service=ip_service,
        verifier=ConnectionVerifier(client, ip_service),
        verify_egress=True,
    )
