from __future__ import annotations

import pytest

from python_template.core.config import Settings
from python_template.core.manifests import PluginActionManifest
from python_template.core.models import RiskTier
from python_template.core.policy import PolicyEngine


def _action(
    capability_id: str,
    risk_tier: RiskTier = RiskTier.transactional,
) -> PluginActionManifest:
    return PluginActionManifest(
        name="test_action",
        capability_id=capability_id,
        resource_type="test_resource",
        risk_tier=risk_tier,
        route_pattern="/:test_action/{phase}",
        supports_propose=True,
        requires_idempotency=False,
        emits_attributes=["origin", "resource_type"],
        resource=None,
        mutating=True,
    )


def test_risk_tier_defaults_drive_approval_behavior():
    policy = PolicyEngine(settings=Settings())

    assert (
        policy.requires_approval(
            _action("apple_music.playback.play", risk_tier=RiskTier.routine),
            "execute",
        )
        is False
    )
    assert (
        policy.requires_approval(
            _action("gmail.message.reply", risk_tier=RiskTier.transactional),
            "execute",
        )
        is True
    )
    assert (
        policy.requires_approval(
            _action("apple_music.playlist.delete", risk_tier=RiskTier.dangerous),
            "execute",
        )
        is True
    )
    assert (
        policy.requires_approval(
            _action("apple_music.playback.play", risk_tier=RiskTier.routine),
            "propose",
        )
        is False
    )


def test_global_override_allow_can_suppress_default_approval():
    policy = PolicyEngine(
        settings=Settings(
            action_approval_overrides_json='{"global":{"allow":["gmail.message.reply"]}}'
        )
    )

    assert (
        policy.requires_approval(
            _action("gmail.message.reply", risk_tier=RiskTier.transactional),
            "execute",
        )
        is False
    )


def test_global_override_require_can_force_approval():
    policy = PolicyEngine(
        settings=Settings(
            action_approval_overrides_json='{"global":{"require":["apple_music.playback.*"]}}'
        )
    )

    assert (
        policy.requires_approval(
            _action("apple_music.playback.pause", risk_tier=RiskTier.routine),
            "execute",
        )
        is True
    )


def test_plugin_specific_override_beats_global_override():
    policy = PolicyEngine(
        settings=Settings(
            action_approval_overrides_json=(
                '{"global":{"require":["apple_music.*"]},'
                '"plugins":{"apple_music":{"allow":["playback.play"]}}}'
            )
        )
    )

    assert (
        policy.requires_approval(
            _action("apple_music.playback.play", risk_tier=RiskTier.transactional),
            "execute",
        )
        is False
    )


def test_plugin_specific_require_can_force_protection():
    policy = PolicyEngine(
        settings=Settings(
            action_approval_overrides_json=(
                '{"plugins":{"apple_music":{"require":["playlist.delete"]}}}'
            )
        )
    )

    assert (
        policy.requires_approval(
            _action("apple_music.playlist.delete", risk_tier=RiskTier.routine),
            "execute",
        )
        is True
    )


def test_risk_defaults_can_be_overridden_by_config():
    policy = PolicyEngine(
        settings=Settings(
            action_approval_defaults_json='{"transactional": false, "routine": true}'
        )
    )

    assert (
        policy.requires_approval(
            _action("gmail.message.reply", risk_tier=RiskTier.transactional),
            "execute",
        )
        is False
    )
    assert (
        policy.requires_approval(
            _action("apple_music.playback.play", risk_tier=RiskTier.routine),
            "execute",
        )
        is True
    )


def test_invalid_override_config_raises_value_error():
    with pytest.raises(
        ValueError,
        match="ACTION_APPROVAL_OVERRIDES_JSON.global.allow pattern 'bad\\*pattern'",
    ):
        PolicyEngine(
            settings=Settings(
                action_approval_overrides_json=('{"global":{"allow":["bad*pattern"]}}')
            )
        )


def test_invalid_default_config_raises_value_error():
    with pytest.raises(ValueError, match="unknown risk tier 'unknown'"):
        PolicyEngine(
            settings=Settings(action_approval_defaults_json='{"unknown": true}')
        )


def test_non_apple_music_transactional_actions_keep_existing_approval_behavior():
    policy = PolicyEngine(settings=Settings())

    assert (
        policy.requires_approval(
            _action("gmail.message.archive", risk_tier=RiskTier.transactional),
            "execute",
        )
        is True
    )
