CREATE DATABASE IF NOT EXISTS talentbridge_db;
USE talentbridge_db;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  password VARCHAR(255),
  role VARCHAR(50) DEFAULT 'user',
  provider VARCHAR(50) DEFAULT 'local',
  provider_id VARCHAR(255),
  is_verified TINYINT(1) DEFAULT 0,
  verify_token_hash VARCHAR(255),
  verify_token_expiry DATETIME,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS password_resets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  token_hash VARCHAR(255) NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ats_reports (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL,
  resume_name VARCHAR(255),
  score INT NOT NULL,
  level VARCHAR(50),
  keyword_match_percent FLOAT,
  breakdown_json LONGTEXT,
  section_status_json LONGTEXT,
  checklist_json LONGTEXT,
  issues_json LONGTEXT,
  fixes_json LONGTEXT,
  examples_json LONGTEXT,
  job_desc_snippet TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
