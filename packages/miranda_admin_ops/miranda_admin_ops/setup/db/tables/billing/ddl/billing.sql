-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS billing (
		id SERIAL PRIMARY KEY,
		user_id INTEGER NOT NULL,
		cents DECIMAL(10,3) NOT NULL,
		subject ENUM('PROCESSOR_DEBUG', 'PROCESSOR_DEPLOYMENT', 'VAULT', 'PROJECT') NOT NULL,
		subject_id INTEGER NOT NULL,
		stripe_inv_id VARCHAR(32),
		payment_state ENUM('OPEN', 'PROCESSING', 'SENT', 'PAID', 'PAST_DUE', 'DISCARDED') NOT NULL DEFAULT 'OPEN',
		created_at TIMESTAMP NOT NULL DEFAULT NOW(),
		billed_at TIMESTAMP,
		paid_at TIMESTAMP,
		FOREIGN KEY (user_id) REFERENCES users (id)
)
