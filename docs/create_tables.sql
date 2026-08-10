-- MedDeviceAgent 建表语句，直接在 Navicat 里执行
-- 先在 med_device_agent 库上执行

-- 1. user
CREATE TABLE `user` (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL COMMENT '用户名',
    phone VARCHAR(20) UNIQUE COMMENT '手机号',
    email VARCHAR(128) UNIQUE COMMENT '邮箱',
    password_hash VARCHAR(256) NOT NULL COMMENT '密码哈希',
    role VARCHAR(32) NOT NULL DEFAULT 'user' COMMENT '角色',
    status INT NOT NULL DEFAULT 1 COMMENT '状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_role (role),
    INDEX idx_user_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. device
CREATE TABLE device (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_sn VARCHAR(64) NOT NULL UNIQUE COMMENT '设备序列号',
    device_type VARCHAR(64) NOT NULL COMMENT '设备型号',
    version VARCHAR(32) COMMENT '软件版本',
    user_id BIGINT NOT NULL COMMENT '所属用户',
    status VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '设备状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_device_type (device_type),
    INDEX idx_device_user_id (user_id),
    INDEX idx_device_user_type (user_id, device_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. warranty_record
CREATE TABLE warranty_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_sn VARCHAR(64) NOT NULL COMMENT '设备SN',
    user_id BIGINT NOT NULL COMMENT '所属用户',
    start_date DATE COMMENT '开始时间',
    end_date DATE COMMENT '结束时间',
    status VARCHAR(32) COMMENT '状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_warranty_device_sn (device_sn),
    INDEX idx_warranty_user_id (user_id),
    INDEX idx_warranty_ds_status (device_sn, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. repair_ticket
CREATE TABLE repair_ticket (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL COMMENT '用户',
    device_sn VARCHAR(64) NOT NULL COMMENT '设备SN',
    fault_desc TEXT NOT NULL COMMENT '故障描述',
    fault_category VARCHAR(64) COMMENT '故障分类',
    priority VARCHAR(16) NOT NULL DEFAULT 'medium' COMMENT '优先级',
    contact_name VARCHAR(64) COMMENT '联系人',
    contact_phone VARCHAR(20) COMMENT '联系电话',
    assigned_to BIGINT COMMENT '分配客服',
    status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '状态',
    created_by VARCHAR(32) NOT NULL DEFAULT 'agent' COMMENT '创建来源',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ticket_user_id (user_id),
    INDEX idx_ticket_device_sn (device_sn),
    INDEX idx_ticket_fault_category (fault_category),
    INDEX idx_ticket_assigned_to (assigned_to),
    INDEX idx_ticket_status (status),
    INDEX idx_ticket_user_status (user_id, status),
    INDEX idx_ticket_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. conversation
CREATE TABLE conversation (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL COMMENT '用户',
    session_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Agent Session',
    title VARCHAR(256) COMMENT '标题',
    status VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_conv_user_id (user_id),
    INDEX idx_conv_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. conversation_message
CREATE TABLE conversation_message (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL COMMENT '会话',
    role VARCHAR(16) NOT NULL COMMENT '角色',
    content TEXT NOT NULL COMMENT '内容',
    token_usage INT COMMENT 'Token数量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_msg_session_id (session_id),
    INDEX idx_msg_session_created (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. conversation_summary
CREATE TABLE conversation_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL COMMENT '用户',
    session_id VARCHAR(64) NOT NULL COMMENT '会话',
    summary TEXT NOT NULL COMMENT '摘要',
    version INT NOT NULL DEFAULT 1 COMMENT '版本',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cs_user_id (user_id),
    INDEX idx_cs_session_id (session_id),
    INDEX idx_cs_user_session (user_id, session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. user_memory
CREATE TABLE user_memory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL COMMENT '用户',
    memory_type VARCHAR(32) NOT NULL COMMENT '类型',
    content TEXT NOT NULL COMMENT '内容',
    status INT NOT NULL DEFAULT 1 COMMENT '状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_um_user_id (user_id),
    INDEX idx_um_user_type_status (user_id, memory_type, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. knowledge_document
CREATE TABLE knowledge_document (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(256) NOT NULL COMMENT '文档名称',
    device_type VARCHAR(64) NOT NULL COMMENT '设备类型',
    doc_type VARCHAR(32) NOT NULL COMMENT '文档类型',
    version VARCHAR(32) NOT NULL COMMENT '版本',
    permission VARCHAR(32) NOT NULL DEFAULT 'public' COMMENT '权限',
    status VARCHAR(32) NOT NULL DEFAULT 'processing' COMMENT '文档状态: processing/ready/failed',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_kd_device_type (device_type),
    INDEX idx_kd_doc_type (doc_type),
    INDEX idx_kd_device_doc_version (device_type, doc_type, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10. knowledge_chunk
CREATE TABLE knowledge_chunk (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id BIGINT NOT NULL COMMENT '所属文档',
    content TEXT NOT NULL COMMENT '文本内容',
    chunk_index INT NOT NULL COMMENT '分块序号',
    `metadata` JSON NOT NULL COMMENT '元数据',
    vector_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Qdrant向量ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_kc_document_id (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 11. agent_trace
CREATE TABLE agent_trace (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trace_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Trace ID',
    session_id VARCHAR(64) NOT NULL COMMENT '会话',
    user_id BIGINT NOT NULL COMMENT '用户',
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    total_latency FLOAT COMMENT '总耗时(ms)',
    status VARCHAR(32) NOT NULL DEFAULT 'running' COMMENT '状态',
    INDEX idx_trace_session_id (session_id),
    INDEX idx_trace_user_id (user_id),
    INDEX idx_trace_user_start (user_id, start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 12. agent_trace_node
CREATE TABLE agent_trace_node (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trace_id VARCHAR(64) NOT NULL COMMENT '链路ID',
    node_name VARCHAR(64) NOT NULL COMMENT '节点名称',
    input JSON COMMENT '输入',
    output JSON COMMENT '输出',
    latency FLOAT COMMENT '耗时(ms)',
    INDEX idx_tn_trace_id (trace_id),
    INDEX idx_tn_trace_node (trace_id, node_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 13. llm_call_record
CREATE TABLE llm_call_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trace_id VARCHAR(64) NOT NULL COMMENT '链路ID',
    task_type VARCHAR(32) NOT NULL COMMENT '任务类型',
    model_name VARCHAR(64) NOT NULL COMMENT '模型名称',
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    latency FLOAT COMMENT '耗时(ms)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_llm_trace_id (trace_id),
    INDEX idx_llm_task_model (task_type, model_name),
    INDEX idx_llm_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 14. role
CREATE TABLE role (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(32) NOT NULL UNIQUE COMMENT '角色名',
    description VARCHAR(256) COMMENT '描述',
    permissions JSON COMMENT '权限列表'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 15. user_role
CREATE TABLE user_role (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL COMMENT '用户',
    role_id BIGINT NOT NULL COMMENT '角色',
    UNIQUE KEY uk_user_role (user_id, role_id),
    INDEX idx_ur_user_id (user_id),
    INDEX idx_ur_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 16. knowledge_permission
CREATE TABLE knowledge_permission (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id BIGINT NOT NULL COMMENT '文档ID',
    role_id BIGINT NOT NULL COMMENT '角色ID',
    permission VARCHAR(16) NOT NULL DEFAULT 'read' COMMENT '权限',
    UNIQUE KEY uk_doc_role (document_id, role_id),
    INDEX idx_kp_document_id (document_id),
    INDEX idx_kp_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;