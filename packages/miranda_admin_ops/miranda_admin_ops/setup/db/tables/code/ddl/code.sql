-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS code (
    `ID`                        INTEGER auto_increment,
    `metadata_id`               INTEGER NOT NULL,
    `order`                     INTEGER DEFAULT 0,
    `code_type`                 ENUM ('PYTHON','RUST','C++','MIXED','JAVA','C#','OTHER','JAVASCRIPT','GO') DEFAULT 'PYTHON',
    `platform_dependency_version` INTEGER DEFAULT 0,
    `platform_dependency_type`  ENUM ('REQUIREMENTS','REPOSITORY','CONTAINER','SERVICE') DEFAULT 'REQUIREMENTS',
    `git`                       VARCHAR(255) DEFAULT '',
    `git_branch`                VARCHAR(40) DEFAULT 'main',
    `API`                       JSON,
    `body`                      LONGTEXT,
    `update_policy`             ENUM ('NEVER', 'NOTIFY', 'SUBSCRIBE') DEFAULT 'NOTIFY',
    `diffs`                     JSON,
    FULLTEXT(`body`),
    PRIMARY KEY (`ID`,`metadata_id`),
    FOREIGN KEY (`metadata_id`)
        REFERENCES metadata(`id`)
        ON DELETE CASCADE
)