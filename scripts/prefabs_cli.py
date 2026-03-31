import inquirer
from mirmod import miranda

sc = miranda.create_security_context(auth_from_config=True)

EVERYONE_GROUP_ID = 1

print(
    "\nThis script publishes all nodes in the selected workflows as prefabs. Start by selecting the user you want to publish prefabs from.\n"
)

users = []
with sc.connect() as con:
    with con.cursor(dictionary=True) as cur:
        cur.execute(
            "SELECT u.id, u.username, ud.first_name, ud.last_name, ud.email FROM users u JOIN users_details ud on u.id = ud.user_id WHERE ud.email NOT LIKE '%@crgs.mainly.ai'"
        )
        users = cur.fetchall()

selected_user = inquirer.prompt(
    [
        inquirer.List(
            "user",
            message="Select a user",
            choices=[
                (
                    f"{user['first_name']} {user['last_name']} <{user['email']}>",
                    user["id"],
                )
                for user in users
            ],
        )
    ]
)["user"]

with sc.connect() as con:
    with con.cursor(dictionary=True) as cur:
        cur.execute(
            """
        SELECT m.name, p.id, m.id as metadata_id FROM project p INNER JOIN metadata m ON p.metadata_id = m.id
        WHERE m.created_by_id = %s""",
            (selected_user,),
        )
        projects = cur.fetchall()

selected_project = inquirer.prompt(
    [
        inquirer.List(
            "project",
            message="Select a project",
            choices=[
                (
                    f"{project['name']} <{project['id']}:{project['metadata_id']}>",
                    project["metadata_id"],
                )
                for project in projects
            ],
        )
    ]
)["project"]

with sc.connect() as con:
    with con.cursor(dictionary=True) as cur:
        cur.execute(
            """
            SELECT m.name, ko.id, m.id as metadata_id
            FROM edges e
            INNER JOIN knowledge_object ko ON e.dest_id = ko.metadata_id
            INNER JOIN metadata m ON ko.metadata_id = m.id
            WHERE e.src_id = %s AND e.dest_type = 'KNOWLEDGE_OBJECT'
        """,
            (selected_project,),
        )
        knowledge_objects = cur.fetchall()


selected_knowledge_objects = inquirer.prompt(
    [
        inquirer.Checkbox(
            "knowledge_objects",
            message="Select workflows to publish (space to select, enter to confirm)",
            choices=[
                (f"{ko['name']} <{ko['id']}:{ko['metadata_id']}>", ko["metadata_id"])
                for ko in knowledge_objects
            ],
            validate=lambda _, result: len(result) >= 1,
        )
    ]
)["knowledge_objects"]

should_share = inquirer.prompt(
    [
        inquirer.List(
            "should_share",
            message="Share with everyone?",
            choices=[
                ("Add tags and share with everyone", True),
                ("Only add tags", False),
            ],
            default=True,
        )
    ]
)["should_share"]

for ko_id in selected_knowledge_objects:
    with sc.connect() as con:
        with con.cursor(dictionary=True) as cur:
            cur.execute(
                """
            SELECT m.name, c.id, m.id as metadata_id
            FROM edges e
            INNER JOIN code c ON e.dest_id = c.metadata_id
            INNER JOIN metadata m ON c.metadata_id = m.id
            WHERE e.src_id = %s AND e.dest_type = 'CODE'
            """,
                (ko_id,),
            )
            children = cur.fetchall()

            for child in children:
                if should_share:
                    cur.execute(
                        """
                        INSERT IGNORE INTO read_acl (wob_mid, gid, oid)
                        VALUES (%s, %s, -1)
                        """,
                        (child["metadata_id"], EVERYONE_GROUP_ID),
                    )
                cur.execute(
                    """
                    INSERT INTO tag2metadata (tag, wob_type, metadata_id, user_id)
                    VALUES (%s, %s, %s, -1)
                    ON DUPLICATE KEY UPDATE tag = VALUES(tag)
                    """,
                    ("miranda.prefab", "CODE", child["metadata_id"]),
                )
                print(
                    f"Published {child['name']} <{child['id']}:{child['metadata_id']}> with tag=miranda.prefab and share={should_share}"
                )
            con.commit()
