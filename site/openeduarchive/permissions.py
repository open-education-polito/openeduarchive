# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 Politecnico di Torino
#
# This file is a derivative of invenio-config-kth, originally developed by
# KTH Royal Institute of Technology Sweden, and modifications are made by
# Politecnico di Torino. This file is under the copyright of Politecnico di Torino and is also
# licensed under the terms of the relevant LICENSE (see repo's root).
#
# Original work: https://github.com/Samk13/rdm-restricted-permissions/tree/master
# Original license at <https://opensource.org/licenses/MIT>.

from flask import abort, current_app
from flask_principal import RoleNeed
from invenio_administration.generators import Administration
from invenio_communities.permissions import CommunityPermissionPolicy
from invenio_i18n import lazy_gettext as _
from invenio_rdm_records.services import RDMRecordPermissionPolicy
from invenio_rdm_records.services.errors import RecordCommunityMissing
from invenio_records_permissions.generators import (
    ConditionalGenerator,
    Disable,
    Generator,
    SystemProcess,
)


class CommunityManager(Generator):
    """Allows users with the community manager role to perform an action."""

    def needs(self, record=None, **kwargs):
        """Enabling Needs."""
        role_name = current_app.config.get(
            "CONFIG_OEA_COMMUNITY_MANAGER_ROLE", "community-manager"
        )
        return [RoleNeed(role_name)]


class IfInCommunity(ConditionalGenerator):
    """Conditional generator to check if the record is in a community."""

    def _condition(self, record, **kwargs):
        """Check if the record is part of a community."""
        if not record or not record.parent.communities.ids:
            abort(403, description=_("Please select a community before publishing."))
        return True


class IfOneCommunity(ConditionalGenerator):
    """Conditional generator to check if the record has at least one community."""

    def _condition(self, record, **kwargs):
        """Check if the record is part of a community."""
        if not record or len(record.parent.communities.ids) == 1:
            raise RecordCommunityMissing("", "One community per record is required")
        return True


class OEACommunitiesPermissionPolicy(CommunityPermissionPolicy):
    """Communities permission policy of Open Education Archive.

    This will enable community managers and admins only to create communities.
    """

    can_create = [CommunityManager(), Administration(), SystemProcess()]

    can_include_directly = [Disable()]


class OEARecordPermissionPolicy(RDMRecordPermissionPolicy):
    """Record permission policy of Open Education Archive.

    This will enable curators to publish records.
    """

    can_publish = [
        IfInCommunity(
            then_=RDMRecordPermissionPolicy.can_publish,
            else_=[SystemProcess()]
        )
    ]

    # Remove community from an already created record just if it has more than one community
    can_remove_community = [
        IfOneCommunity(
            then_=RDMRecordPermissionPolicy.can_remove_community,
            else_=[SystemProcess()],
        )
    ]
