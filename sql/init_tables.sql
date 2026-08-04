-- PhotoStyle 建表 SQL
-- 适用于 MySQL 8+

CREATE TABLE IF NOT EXISTS `user` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `username` VARCHAR(64) NOT NULL COMMENT '用户名',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `photo_path` VARCHAR(500) NULL COMMENT '用户照片路径',
    `photo_mime_type` VARCHAR(100) NULL COMMENT '照片MIME类型',
    `face_analysis` JSON NULL COMMENT '人脸分析数据',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

CREATE TABLE IF NOT EXISTS `history` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    `user_id` BIGINT NOT NULL COMMENT '用户ID',
    `input_data` JSON NOT NULL COMMENT '输入数据',
    `output_data` JSON NOT NULL COMMENT '输出数据',
    `makeup_rating` INT NOT NULL DEFAULT 0 COMMENT '妆容评分',
    `outfit_rating` INT NOT NULL DEFAULT 0 COMMENT '穿搭评分',
    `pose_rating` INT NOT NULL DEFAULT 0 COMMENT '姿势评分',
    `feedback_comment` TEXT NULL COMMENT '点评内容',
    `reviewed` BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否已点评',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_history_user_id` (`user_id`),
    CONSTRAINT `fk_history_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='拍照风格历史记录表';

CREATE TABLE IF NOT EXISTS `user_persona` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '用户人格画像ID',
    `user_id` BIGINT NOT NULL COMMENT '关联用户ID',
    `semantic_axes` JSON NOT NULL COMMENT '用户语义偏好轴',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_persona_user_id` (`user_id`),
    CONSTRAINT `fk_user_persona_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户人格画像表';