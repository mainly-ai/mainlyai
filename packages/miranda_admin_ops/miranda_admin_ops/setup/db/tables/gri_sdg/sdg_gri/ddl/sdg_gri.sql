-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS sdg_gri (
    ID					INTEGER AUTO_INCREMENT PRIMARY KEY,
    SDGTarget			VARCHAR (20),
    GRIDisclosures		VARCHAR (500)
);