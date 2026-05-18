# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
from miranda_admin_ops import admin_create_user_group, admin_assign_user_to_group

# Add org_team_group_id column to organization table if it doesn't exist
if not utilities.has_column(utilities.admin_sc, "organization", "org_team_group_id"):
    utilities.add_column(
        utilities.admin_sc, "organization", "org_team_group_id", "INTEGER"
    )

# Add is_org_managed column to user_groups table if it doesn't exist
if not utilities.has_column(utilities.admin_sc, "user_groups", "is_org_managed"):
    utilities.add_column(
        utilities.admin_sc,
        "user_groups",
        "is_org_managed",
        "BOOLEAN NOT NULL DEFAULT FALSE",
    )

# Create teams for each organization that doesn't have one, and assign users
with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
        # Get all organizations that don't have a team group yet
        cur.execute("""
            SELECT id, name, creator_user_id 
            FROM organization 
            WHERE org_team_group_id IS NULL
        """)
        organizations = cur.fetchall()

        for org_id, org_name, creator_user_id in organizations:
            print(f"Creating team for organization '{org_name}' (id: {org_id})")

            # Create a user group for this organization
            team_group_id = admin_create_user_group(
                name=f"{org_name}",
                group_owner_id=creator_user_id,
                is_public=False,
                members_can_invite_others=True,
                is_org_managed=True,
            )
            print(f"  Created team group {team_group_id}")

            # Update the organization to reference this team group
            cur.execute(
                """
                UPDATE organization 
                SET org_team_group_id = %s 
                WHERE id = %s
            """,
                (team_group_id, org_id),
            )
            con.commit()
            print(f"  Updated organization {org_id} with team group {team_group_id}")

            # Get all users in this organization
            cur.execute(
                """
                SELECT id 
                FROM users 
                WHERE organization_id = %s
            """,
                (org_id,),
            )
            user_ids = cur.fetchall()

            # Assign each user to the team group
            for (user_id,) in user_ids:
                admin_assign_user_to_group(None, user_id, team_group_id)
                print(f"  Assigned user {user_id} to team group {team_group_id}")

# Add foreign key constraint to reference user_groups table
if utilities.table_exists(
    utilities.admin_sc, "organization"
) and utilities.table_exists(utilities.admin_sc, "user_groups"):
    with utilities.admin_sc.connect() as con:
        with con.cursor() as cur:
            # Check if the foreign key constraint already exists
            cur.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                WHERE TABLE_NAME = 'organization' 
                AND COLUMN_NAME = 'org_team_group_id' 
                AND REFERENCED_TABLE_NAME = 'user_groups'
                AND TABLE_SCHEMA = 'miranda'
            """)
            fk_exists = cur.fetchone()[0] > 0

            if not fk_exists:
                cur.execute("""
                    ALTER TABLE organization 
                    ADD CONSTRAINT fk_organization_team_group 
                    FOREIGN KEY (org_team_group_id) REFERENCES user_groups(id)
                """)
                print(
                    "Added foreign key constraint from organization.org_team_group_id to user_groups.id"
                )
