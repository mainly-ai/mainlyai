-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `organization` (
	id 							INTEGER NOT NULL AUTO_INCREMENT,
	name 						VARCHAR(64) NOT NULL,
	`icon` 					varchar(255) NOT NULL DEFAULT 'https://mainly-web-assets.s3.eu-north-1.amazonaws.com/avatars/group_default.png',
	created_at 			TIMESTAMP NOT NULL DEFAULT NOW(),
	updated_at 			TIMESTAMP NOT NULL DEFAULT NOW(),
	creator_user_id INTEGER NOT NULL,
	stripe_cus_id 	VARCHAR(32),
	stripe_sub_id 	VARCHAR(32),
	subscribed      BOOLEAN NOT NULL DEFAULT FALSE,
	trial           BOOLEAN NOT NULL DEFAULT FALSE,
	is_free					BOOLEAN NOT NULL DEFAULT FALSE,
	trial_end       TIMESTAMP,
	credits         DECIMAL(36,18) NOT NULL DEFAULT 0.0,
	has_onboarded   BOOLEAN NOT NULL DEFAULT FALSE,
	org_team_group_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY (creator_user_id) REFERENCES users (id),
	FOREIGN KEY (org_team_group_id) REFERENCES user_groups (id)
)