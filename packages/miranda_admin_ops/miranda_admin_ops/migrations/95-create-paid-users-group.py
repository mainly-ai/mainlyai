# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
from miranda_admin_ops import admin_create_user_group, admin_assign_user_to_group

# Define the name of the group
GROUP_NAME = "PAID"

with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
        # Check if the group already exists
        cur.execute(
            "SELECT id FROM user_groups WHERE name = %s AND oid = -1", (GROUP_NAME,)
        )
        result = cur.fetchone()

        if result:
            paid_user_group_id = result[0]
            print(f"Group '{GROUP_NAME}' already exists with ID: {paid_user_group_id}")
        else:
            # Create the group if it doesn't exist
            # Note: Using -1 for system owner.
            owner_id = -1

            paid_user_group_id = admin_create_user_group(
                name=GROUP_NAME,
                group_owner_id=owner_id,
                is_public=False,
                members_can_invite_others=False,
                is_org_managed=False,
            )
            print(f"Created '{GROUP_NAME}' group with ID: {paid_user_group_id}")

        if "paid_user_group_id" in locals():
            print("\n" + "=" * 80)
            print(
                f"IMPORTANT: Please set the environment variable PAID_USER_GROUP_ID={paid_user_group_id}"
            )
            print("=" * 80 + "\n")

            # Find all users in subscribed organizations
            # subscribed is a boolean in organization table
            cur.execute("""
                SELECT u.id 
                FROM users u
                JOIN organization o ON u.organization_id = o.id
                WHERE o.subscribed = TRUE
            """)
            paid_users = cur.fetchall()

            print(f"Found {len(paid_users)} users in subscribed organizations.")

            count = 0
            for (user_id,) in paid_users:
                # Assign user to the group
                # admin_assign_user_to_group handles duplicates gracefully usually, or we can check.
                # But typically assign functions are safe or we catch error.
                # Let's try assigning.
                try:
                    admin_assign_user_to_group(None, user_id, paid_user_group_id)
                    count += 1
                except Exception as e:
                    # It might fail if already exists or other issues.
                    # We'll assume silent success or log error.
                    print(f"Failed to assign user {user_id}: {e}")

            print(f"Added {count} users to the '{GROUP_NAME}' group.")
