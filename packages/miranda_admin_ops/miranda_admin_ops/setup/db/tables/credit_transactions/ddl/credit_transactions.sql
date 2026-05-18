-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `credit_transactions` (
	id 										INTEGER NOT NULL AUTO_INCREMENT,
	created_at 						TIMESTAMP NOT NULL DEFAULT NOW(),
	initiator_user_id 		INTEGER, /* NULL = mint credits */
	from_organization_id 	INTEGER, /* NULL = mint credits */
	to_organization_id		INTEGER, /* NULL = burn credits */
	amount 								DECIMAL(36,18) NOT NULL,
	statement 						VARCHAR(255) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY (initiator_user_id) REFERENCES users (id),
	FOREIGN KEY (from_organization_id) REFERENCES organization (id),
	FOREIGN KEY (to_organization_id) REFERENCES organization (id)
)